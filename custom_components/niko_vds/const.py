"""Constants for the Niko VDS integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "niko_vds"
PLATFORMS: list[Platform] = [Platform.CAMERA]

CONF_CA_CERT_PEM = "ca_cert_pem"
CONF_CERT_PEM = "cert_pem"
CONF_CONTROLLER_IP = "controller_ip"
CONF_KEY_PEM = "key_pem"
CONF_MANUAL_MACS = "manual_macs"
CONF_POLL_INTERVAL = "poll_interval"
CONF_VERIFY_TLS = "verify_tls"

DEFAULT_POLL_INTERVAL = 10
MIN_POLL_INTERVAL = 5
DEFAULT_VERIFY_TLS = False

DISCOVERY_CACHE_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 20
LTS_PORT = 4443
CONFIG_MQTT_PORT = 8883
CONFIG_MQTT_USERNAME = "c516c66a-4970-4a45-817b-d912871e9033"
