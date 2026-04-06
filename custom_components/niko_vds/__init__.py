"""The Niko VDS integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import NikoVdsClient, NikoVdsClientConfig
from .const import (
    CONF_CA_CERT_PEM,
    CONF_CERT_PEM,
    CONF_CONTROLLER_IP,
    CONF_KEY_PEM,
    CONF_MANUAL_MACS,
    CONF_POLL_INTERVAL,
    CONF_VERIFY_TLS,
    PLATFORMS,
)
from .coordinator import NikoVdsCoordinator
from .models import NikoVdsRuntimeData

LOGGER = logging.getLogger(__name__)


def _read_text_if_exists(path_value: str | None) -> str | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old path-based config entries to PEM text."""
    if entry.version > 2:
        return False

    if entry.version < 2:
        new_data = dict(entry.data)
        cert_path = new_data.pop("cert_path", None)
        key_path = new_data.pop("key_path", None)
        ca_cert_path = new_data.pop("ca_cert_path", None)

        cert_pem = new_data.get(CONF_CERT_PEM) or _read_text_if_exists(cert_path)
        key_pem = new_data.get(CONF_KEY_PEM) or _read_text_if_exists(key_path)
        ca_cert_pem = new_data.get(CONF_CA_CERT_PEM) or _read_text_if_exists(ca_cert_path)

        if cert_pem is not None:
            new_data[CONF_CERT_PEM] = cert_pem
        if key_pem is not None:
            new_data[CONF_KEY_PEM] = key_pem
        if ca_cert_pem is not None:
            new_data[CONF_CA_CERT_PEM] = ca_cert_pem

        hass.config_entries.async_update_entry(entry, data=new_data, version=2)
        LOGGER.debug("Migrated Niko VDS entry %s to version 2", entry.entry_id)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Niko VDS from a config entry."""
    merged = {
        **entry.data,
        **entry.options,
    }
    client = NikoVdsClient(
        NikoVdsClientConfig(
            controller_ip=merged[CONF_CONTROLLER_IP],
            cert_pem=merged[CONF_CERT_PEM],
            key_pem=merged[CONF_KEY_PEM],
            ca_cert_pem=merged.get(CONF_CA_CERT_PEM),
            verify_tls=merged[CONF_VERIFY_TLS],
            poll_interval=merged[CONF_POLL_INTERVAL],
            manual_macs=merged.get(CONF_MANUAL_MACS, []),
        )
    )
    coordinator = NikoVdsCoordinator(hass, client, merged[CONF_POLL_INTERVAL])
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:  # noqa: BLE001
        LOGGER.exception(
            "Failed to set up Niko VDS entry for controller %s",
            merged[CONF_CONTROLLER_IP],
        )
        raise ConfigEntryNotReady(str(err)) from err

    entry.runtime_data = NikoVdsRuntimeData(
        client=client,
        coordinator=coordinator,
        controller_id=client.controller_id,
    )
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload an entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
