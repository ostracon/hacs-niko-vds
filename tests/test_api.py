"""Unit tests for the Niko VDS API helpers."""

from __future__ import annotations

from custom_components.niko_vds.api import NikoVdsClient, NikoVdsClientConfig, normalize_manual_macs


def make_client() -> NikoVdsClient:
    """Create a client with test-only static values."""
    return NikoVdsClient(
        NikoVdsClientConfig(
            controller_ip="192.0.2.1",
            cert_pem="-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----",
            key_pem="-----BEGIN RSA PRIVATE KEY-----\nTEST\n-----END RSA PRIVATE KEY-----",
            ca_cert_pem=None,
            verify_tls=False,
            poll_interval=10,
            manual_macs=[],
        )
    )


def test_normalize_manual_macs_deduplicates_and_filters() -> None:
    """Manual MAC parsing should normalize and deduplicate values."""
    assert normalize_manual_macs("00:11:2A:65:3D:81\n00112A653D81\nbad\n00112A653D84") == [
        "00112a653d81",
        "00112a653d84",
    ]


def test_extract_dotnet_list_handles_dotnet_shape() -> None:
    """Dotnet list wrappers should be flattened into Python dictionaries."""
    client = make_client()
    payload = {
        "$type": "System.Collections.Generic.List`1[[Example]]",
        "$values": [{"macAddress": "00112a653d81"}],
    }
    assert client._extract_dotnet_list(payload) == [{"macAddress": "00112a653d81"}]


def test_discover_vds_devices_uses_manual_fallback() -> None:
    """Manual MACs should be added if discovery does not return them."""
    client = NikoVdsClient(
        NikoVdsClientConfig(
            controller_ip="192.0.2.1",
            cert_pem="cert",
            key_pem="key",
            ca_cert_pem=None,
            verify_tls=False,
            poll_interval=10,
            manual_macs=["00112a653d84"],
        )
    )
    client._mqtt_rpc_call = lambda method, params: {  # type: ignore[method-assign]
        "result": {
            "$values": [
                {
                    "$type": "Niko.Config.Coco.Model.Addressing.VdsDiscoveredDeviceInfo, Niko.Config.Coco.Model",
                    "macAddress": "00112a653d81",
                    "numberOfButtons": "1",
                    "internalInfo": {"ipAddress": "10.0.0.10", "productId": "550-22001"},
                    "parameters": {"softwareVersion": "3.2.13+8000"},
                }
            ]
        }
    }

    devices = client.discover_vds_devices(force_refresh=True)

    assert sorted(devices) == ["00112a653d81", "00112a653d84"]
    assert devices["00112a653d81"].ip_address == "10.0.0.10"
    assert devices["00112a653d81"].software_version == "3.2.13+8000"
    assert devices["00112a653d84"].name == "VDS 00112A653D84"
