"""Config flow for Niko VDS."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .api import NikoVdsAuthError, NikoVdsClient, NikoVdsClientConfig, NikoVdsConnectionError, normalize_manual_macs
from .const import (
    CONF_CA_CERT_PEM,
    CONF_CERT_PEM,
    CONF_CONTROLLER_IP,
    CONF_KEY_PEM,
    CONF_MANUAL_MACS,
    CONF_POLL_INTERVAL,
    CONF_VERIFY_TLS,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_VERIFY_TLS,
    DOMAIN,
    MIN_POLL_INTERVAL,
)

LOGGER = logging.getLogger(__name__)


def _build_schema(defaults: dict[str, Any]) -> vol.Schema:
    pem_selector = selector.TextSelector(
        selector.TextSelectorConfig(
            multiline=True,
            type=selector.TextSelectorType.TEXT,
        )
    )
    return vol.Schema(
        {
            vol.Required(CONF_CONTROLLER_IP, default=defaults.get(CONF_CONTROLLER_IP, "")): str,
            vol.Required(CONF_CERT_PEM, default=defaults.get(CONF_CERT_PEM, "")): pem_selector,
            vol.Required(CONF_KEY_PEM, default=defaults.get(CONF_KEY_PEM, "")): pem_selector,
            vol.Optional(CONF_CA_CERT_PEM, default=defaults.get(CONF_CA_CERT_PEM, "")): pem_selector,
            vol.Required(CONF_VERIFY_TLS, default=defaults.get(CONF_VERIFY_TLS, DEFAULT_VERIFY_TLS)): bool,
            vol.Required(CONF_POLL_INTERVAL, default=defaults.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)): vol.All(
                vol.Coerce(int), vol.Range(min=MIN_POLL_INTERVAL)
            ),
            vol.Optional(CONF_MANUAL_MACS, default=defaults.get(CONF_MANUAL_MACS, "")): pem_selector,
        }
    )


def _normalize_user_input(user_input: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(user_input)
    ca_cert_pem = (normalized.get(CONF_CA_CERT_PEM) or "").strip() or None
    normalized[CONF_CA_CERT_PEM] = ca_cert_pem
    normalized[CONF_CONTROLLER_IP] = normalized[CONF_CONTROLLER_IP].strip()
    normalized[CONF_CERT_PEM] = normalized[CONF_CERT_PEM].strip()
    normalized[CONF_KEY_PEM] = normalized[CONF_KEY_PEM].strip()
    normalized[CONF_MANUAL_MACS] = normalize_manual_macs(normalized.get(CONF_MANUAL_MACS))
    return normalized


def _display_manual_macs(value: Any) -> str:
    return "\n".join(normalize_manual_macs(value))


class NikoVdsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Niko VDS."""

    VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            normalized = _normalize_user_input(user_input)
            client = NikoVdsClient(NikoVdsClientConfig(**normalized))
            try:
                result = await self.hass.async_add_executor_job(client.validate)
            except NikoVdsAuthError:
                LOGGER.warning(
                    "Niko VDS authentication failed during config flow for controller %s",
                    normalized[CONF_CONTROLLER_IP],
                    exc_info=True,
                )
                errors["base"] = "invalid_auth"
            except NikoVdsConnectionError:
                LOGGER.warning(
                    "Niko VDS connection failed during config flow for controller %s",
                    normalized[CONF_CONTROLLER_IP],
                    exc_info=True,
                )
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception(
                    "Unexpected Niko VDS error during config flow for controller %s",
                    normalized[CONF_CONTROLLER_IP],
                )
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(result.controller_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Niko VDS {normalized[CONF_CONTROLLER_IP]}",
                    data=normalized,
                )

        defaults = {
            CONF_VERIFY_TLS: DEFAULT_VERIFY_TLS,
            CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
            CONF_MANUAL_MACS: "",
        }
        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(defaults),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return NikoVdsOptionsFlow(config_entry)


class NikoVdsOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Niko VDS."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            normalized = _normalize_user_input(user_input)
            client = NikoVdsClient(
                NikoVdsClientConfig(
                    **{
                        **self.config_entry.data,
                        **normalized,
                    }
                )
            )
            try:
                await self.hass.async_add_executor_job(client.validate)
            except NikoVdsAuthError:
                LOGGER.warning(
                    "Niko VDS authentication failed during options flow for controller %s",
                    normalized[CONF_CONTROLLER_IP],
                    exc_info=True,
                )
                errors["base"] = "invalid_auth"
            except NikoVdsConnectionError:
                LOGGER.warning(
                    "Niko VDS connection failed during options flow for controller %s",
                    normalized[CONF_CONTROLLER_IP],
                    exc_info=True,
                )
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception(
                    "Unexpected Niko VDS error during options flow for controller %s",
                    normalized[CONF_CONTROLLER_IP],
                )
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(data=normalized)

        current = {
            key: self.config_entry.options.get(key, self.config_entry.data.get(key))
            for key in (
                CONF_CONTROLLER_IP,
                CONF_CERT_PEM,
                CONF_KEY_PEM,
                CONF_CA_CERT_PEM,
                CONF_VERIFY_TLS,
                CONF_POLL_INTERVAL,
                CONF_MANUAL_MACS,
            )
        }
        current[CONF_MANUAL_MACS] = _display_manual_macs(current.get(CONF_MANUAL_MACS))
        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(current),
            errors=errors,
        )
