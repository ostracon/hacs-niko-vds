"""Blocking Niko VDS client helpers."""

from __future__ import annotations

import base64
import http.client
import json
import os
import ssl
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from tempfile import TemporaryDirectory

import paho.mqtt.client as mqtt

from .const import (
    CONFIG_MQTT_PORT,
    CONFIG_MQTT_USERNAME,
    DISCOVERY_CACHE_SECONDS,
    LTS_PORT,
    REQUEST_TIMEOUT_SECONDS,
)
from .models import NikoVdsCoordinatorData, NikoVdsDevice

CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class NikoVdsError(Exception):
    """Base integration exception."""


class NikoVdsConnectionError(NikoVdsError):
    """Raised when the controller cannot be reached."""


class NikoVdsAuthError(NikoVdsError):
    """Raised when authentication fails."""


@dataclass(slots=True)
class NikoVdsClientConfig:
    """Static client configuration."""

    controller_ip: str
    cert_pem: str
    key_pem: str
    ca_cert_pem: str | None
    verify_tls: bool
    poll_interval: int
    manual_macs: list[str]


@dataclass(slots=True)
class NikoVdsProbeResult:
    """Connection probe result."""

    controller_id: str
    discovered_devices: int


def base32_crockford_encode(data: bytes) -> str:
    """Encode bytes using the Crockford base32 alphabet."""
    if not data:
        return ""

    index = 0
    current = data[index]
    index += 1
    bit_count = 8
    out: list[str] = []

    while bit_count > 0 or index < len(data):
        if bit_count < 5:
            if index < len(data):
                current <<= 8
                current |= data[index] & 0xFF
                index += 1
                bit_count += 8
            else:
                pad_bits = 5 - bit_count
                current <<= pad_bits
                bit_count += pad_bits
        alphabet_index = 0x1F & (current >> (bit_count - 5))
        bit_count -= 5
        out.append(CROCKFORD_ALPHABET[alphabet_index])
    return "".join(out)


def compute_client_identifier(machine_name: str) -> str:
    """Compute the controller client identifier used by LTS."""
    import hashlib

    digest = hashlib.sha256(machine_name.encode("utf-8")).digest()
    return base32_crockford_encode(digest)


def normalize_mac(mac_address: str) -> str:
    """Normalize a MAC-like controller address to lowercase hex."""
    return "".join(ch for ch in mac_address.lower() if ch in "0123456789abcdef")


def normalize_manual_macs(value: str | list[str] | None) -> list[str]:
    """Normalize manual MAC input from config or options."""
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = value.replace(",", "\n").splitlines()
    normalized: list[str] = []
    for item in items:
        mac = normalize_mac(item.strip())
        if len(mac) >= 8 and mac not in normalized:
            normalized.append(mac)
    return normalized


def decode_jwt_payload(token: str) -> dict[str, Any]:
    """Decode a JWT payload without verifying it."""
    try:
        _, payload_b64, _ = token.split(".", 2)
    except ValueError as err:
        raise NikoVdsAuthError("Controller returned an invalid JWT") from err
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except Exception as err:  # noqa: BLE001
        raise NikoVdsAuthError("Failed to decode controller JWT payload") from err


def guess_content_type(image_bytes: bytes) -> str:
    """Guess the content type for image bytes."""
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    return "application/octet-stream"


def _build_ssl_context(verify_tls: bool, ca_cert_pem: str | None) -> ssl.SSLContext:
    context = ssl.create_default_context()
    if verify_tls and ca_cert_pem:
        context.load_verify_locations(cadata=ca_cert_pem)
    if not verify_tls:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


def _extract_base64_from_result(result: Any) -> str | None:
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        for item in result:
            if isinstance(item, str):
                return item
            if isinstance(item, dict):
                for key in (
                    "Data",
                    "data",
                    "Image",
                    "image",
                    "Thumb",
                    "thumb",
                    "Thumbnail",
                    "thumbnail",
                    "Base64",
                    "base64",
                ):
                    value = item.get(key)
                    if isinstance(value, str):
                        return value
    if isinstance(result, dict):
        for key in (
            "$value",
            "Data",
            "data",
            "Image",
            "image",
            "Thumb",
            "thumb",
            "Thumbnail",
            "thumbnail",
            "Base64",
            "base64",
            "Payload",
            "payload",
            "Content",
            "content",
        ):
            value = result.get(key)
            if isinstance(value, str):
                return value
        for value in result.values():
            if isinstance(value, str):
                return value
    return None


class NikoVdsClient:
    """Blocking controller client for discovery and snapshots."""

    def __init__(self, config: NikoVdsClientConfig) -> None:
        self.config = config
        self._token: str | None = None
        self._token_expires: float = 0
        self._controller_id = config.controller_ip
        self._discovery_cache: dict[str, NikoVdsDevice] = {}
        self._discovery_cache_at = 0.0

    @property
    def controller_id(self) -> str:
        """Return the resolved controller identifier."""
        return self._controller_id

    def validate(self) -> NikoVdsProbeResult:
        """Validate controller connectivity and enumerate VDS endpoints."""
        token = self._get_lts_token(force_refresh=True)
        payload = decode_jwt_payload(token)
        controller_id = self._extract_controller_id(payload)
        self._controller_id = controller_id
        devices = self.discover_vds_devices(force_refresh=True)
        return NikoVdsProbeResult(
            controller_id=controller_id,
            discovered_devices=len(devices),
        )

    def fetch_state(self) -> NikoVdsCoordinatorData:
        """Fetch the latest discovery and snapshots."""
        devices = self.discover_vds_devices()
        images: dict[str, bytes] = {}
        content_types: dict[str, str] = {}
        errors: dict[str, str] = {}

        for mac_address in devices:
            try:
                image_bytes = self.download_snapshot(mac_address)
            except NikoVdsError as err:
                errors[mac_address] = str(err)
                continue
            images[mac_address] = image_bytes
            content_types[mac_address] = guess_content_type(image_bytes)

        return NikoVdsCoordinatorData(
            devices=devices,
            images=images,
            content_types=content_types,
            errors=errors,
        )

    def discover_vds_devices(self, *, force_refresh: bool = False) -> dict[str, NikoVdsDevice]:
        """Discover VDS devices from the controller config API."""
        now = time.monotonic()
        if not force_refresh and self._discovery_cache and (now - self._discovery_cache_at) < DISCOVERY_CACHE_SECONDS:
            return dict(self._discovery_cache)

        response = self._mqtt_rpc_call("AddressingApi.GetKnownDevices", {})
        devices: dict[str, NikoVdsDevice] = {}

        for item in self._extract_dotnet_list(response.get("result")):
            if "VdsDiscoveredDeviceInfo" not in str(item.get("$type", "")):
                continue

            mac_address = normalize_mac(
                item.get("macAddress")
                or item.get("address")
                or (item.get("traits") or {}).get("macAddress")
                or ""
            )
            if not mac_address:
                continue

            display_name = item.get("displayName")
            name = display_name.strip() if isinstance(display_name, str) and display_name.strip() else f"VDS {mac_address.upper()}"

            number_of_buttons = item.get("numberOfButtons") or (item.get("traits") or {}).get("numberOfButtons")
            try:
                buttons = int(number_of_buttons) if number_of_buttons is not None else None
            except (TypeError, ValueError):
                buttons = None

            internal_info = item.get("internalInfo") or {}
            devices[mac_address] = NikoVdsDevice(
                mac_address=mac_address,
                name=name,
                ip_address=item.get("ipAddress") or internal_info.get("ipAddress"),
                number_of_buttons=buttons,
                product_id=item.get("productId") or internal_info.get("productId"),
                software_version=item.get("softwareVersion") or (item.get("parameters") or {}).get("softwareVersion"),
            )

        for manual_mac in self.config.manual_macs:
            devices.setdefault(
                manual_mac,
                NikoVdsDevice(
                    mac_address=manual_mac,
                    name=f"VDS {manual_mac.upper()}",
                ),
            )

        self._discovery_cache = dict(devices)
        self._discovery_cache_at = now
        return devices

    def download_snapshot(self, mac_address: str) -> bytes:
        """Download the latest snapshot for a VDS MAC address."""
        response = self._mqtt_rpc_call(
            "AddressingApi.DownloadVdsData",
            {"macAddress": normalize_mac(mac_address)},
        )
        result = response.get("result")
        if result is None:
            raise NikoVdsConnectionError("Controller returned no snapshot result")

        data_b64 = _extract_base64_from_result(result)
        if not data_b64:
            raise NikoVdsConnectionError("Controller returned an unexpected snapshot payload")

        normalized = data_b64.strip()
        if "," in normalized and normalized.lower().startswith("data:"):
            normalized = normalized.split(",", 1)[1]
        normalized = normalized.replace("\n", "").replace("\r", "").replace(" ", "")
        normalized += "=" * (-len(normalized) % 4)

        try:
            return base64.b64decode(normalized, validate=False)
        except Exception as err:  # noqa: BLE001
            raise NikoVdsConnectionError("Failed to decode VDS snapshot payload") from err

    def _get_lts_token(self, *, force_refresh: bool = False) -> str:
        if not force_refresh and self._token and time.time() < (self._token_expires - 60):
            return self._token

        cert_pem = self.config.cert_pem.strip()
        key_pem = self.config.key_pem.strip()
        if not cert_pem:
            raise NikoVdsConnectionError("Client certificate PEM is empty")
        if not key_pem:
            raise NikoVdsConnectionError("Client key PEM is empty")

        context = _build_ssl_context(self.config.verify_tls, self.config.ca_cert_pem)

        machine_name = os.uname().nodename
        body = json.dumps(
            {"ClientIdentifier": compute_client_identifier(machine_name)}
        ).encode("utf-8")

        try:
            with TemporaryDirectory() as temp_dir:
                cert_path = Path(temp_dir) / "client.crt"
                key_path = Path(temp_dir) / "client.key"
                cert_path.write_text(cert_pem, encoding="utf-8")
                key_path.write_text(key_pem, encoding="utf-8")
                try:
                    context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
                except ssl.SSLError as err:
                    raise NikoVdsAuthError("Failed to load the client certificate or key") from err

                conn = http.client.HTTPSConnection(
                    self.config.controller_ip,
                    LTS_PORT,
                    context=context,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                conn.request(
                    "POST",
                    "/lts/v1/credentials",
                    body=body,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                )
                resp = conn.getresponse()
                payload = resp.read()
                conn.close()
        except ssl.SSLCertVerificationError as err:
            raise NikoVdsConnectionError("TLS verification failed for the controller certificate") from err
        except OSError as err:
            raise NikoVdsConnectionError("Failed to connect to the controller LTS endpoint") from err

        if resp.status != 200:
            raise NikoVdsAuthError(f"LTS authentication failed with HTTP {resp.status}")

        try:
            data = json.loads(payload.decode("utf-8"))
        except Exception as err:  # noqa: BLE001
            raise NikoVdsAuthError("Controller returned an invalid LTS response") from err

        token = data.get("Token") or data.get("token")
        if not token:
            raise NikoVdsAuthError("Controller LTS response did not contain a token")

        jwt_payload = decode_jwt_payload(token)
        self._controller_id = self._extract_controller_id(jwt_payload)

        exp_value = jwt_payload.get("exp")
        if isinstance(exp_value, (int, float)):
            self._token_expires = float(exp_value)
        else:
            expires_on = data.get("ExpiresOn") or data.get("expiresOn")
            if isinstance(expires_on, str):
                try:
                    expires_dt = datetime.strptime(expires_on, "%Y-%m-%dT%H:%M:%S%z")
                    self._token_expires = expires_dt.timestamp()
                except ValueError:
                    self._token_expires = time.time() + 300
            else:
                self._token_expires = time.time() + 300

        self._token = token
        return token

    def _extract_controller_id(self, payload: dict[str, Any]) -> str:
        aud = payload.get("aud")
        if isinstance(aud, list) and aud:
            return str(aud[0])
        if isinstance(aud, str):
            return aud
        issuer = payload.get("iss")
        if isinstance(issuer, str) and issuer:
            return issuer
        return self.config.controller_ip

    def _mqtt_rpc_call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = f"req-{uuid.uuid4().hex}"
        response_topic = f"config/rsp-{request_id}"
        payload = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )

        token = self._get_lts_token()
        tls_context = _build_ssl_context(self.config.verify_tls, self.config.ca_cert_pem)

        done = threading.Event()
        state: dict[str, Any] = {
            "response": None,
            "connect_error": None,
            "publish_error": None,
        }

        callback_version = getattr(mqtt, "CallbackAPIVersion", None)
        if callback_version is not None:
            client = mqtt.Client(
                callback_version.VERSION2,
                client_id=f"niko-vds-{uuid.uuid4().hex[:12]}",
                protocol=mqtt.MQTTv311,
            )
        else:
            client = mqtt.Client(
                client_id=f"niko-vds-{uuid.uuid4().hex[:12]}",
                protocol=mqtt.MQTTv311,
            )
        client.username_pw_set(CONFIG_MQTT_USERNAME, token)
        client.tls_set_context(tls_context)

        def on_connect(
            mqtt_client: mqtt.Client,
            _userdata: Any,
            _flags: Any,
            reason_code: Any,
            _properties: Any = None,
        ) -> None:
            normalized_reason = getattr(reason_code, "value", reason_code)
            if int(normalized_reason) != 0:
                state["connect_error"] = f"Config MQTT connect failed: rc={int(normalized_reason)}"
                done.set()
                return
            mqtt_client.subscribe(response_topic, qos=1)
            info = mqtt_client.publish("config/cmd", payload, qos=1)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                state["publish_error"] = f"Config MQTT publish failed: rc={info.rc}"
                done.set()

        def on_message(
            mqtt_client: mqtt.Client,
            _userdata: Any,
            msg: mqtt.MQTTMessage,
        ) -> None:
            try:
                state["response"] = json.loads(msg.payload.decode("utf-8", errors="replace"))
            except Exception as err:  # noqa: BLE001
                state["publish_error"] = f"Invalid JSON-RPC response: {err}"
            finally:
                done.set()
                mqtt_client.disconnect()

        client.on_connect = on_connect
        client.on_message = on_message

        try:
            client.connect(self.config.controller_ip, CONFIG_MQTT_PORT, keepalive=60)
        except OSError as err:
            raise NikoVdsConnectionError("Failed to connect to config MQTT") from err

        client.loop_start()
        try:
            if not done.wait(REQUEST_TIMEOUT_SECONDS):
                raise NikoVdsConnectionError(f"Timed out waiting for {method}")
        finally:
            try:
                client.disconnect()
            except Exception:  # noqa: BLE001
                pass
            client.loop_stop()

        if state["connect_error"]:
            raise NikoVdsConnectionError(state["connect_error"])
        if state["publish_error"]:
            raise NikoVdsConnectionError(state["publish_error"])
        response = state["response"]
        if not isinstance(response, dict):
            raise NikoVdsConnectionError("Controller returned an empty config MQTT response")
        if response.get("error"):
            raise NikoVdsConnectionError(json.dumps(response["error"]))
        return response

    def _extract_dotnet_list(self, value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            values = value.get("$values")
            if isinstance(values, list):
                return [item for item in values if isinstance(item, dict)]
        return []
