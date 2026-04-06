"""Camera entities for Niko VDS snapshots."""

from __future__ import annotations

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import NikoVdsCoordinatorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Niko VDS camera entities."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    entities: dict[str, NikoVdsCamera] = {}

    @callback
    def sync_entities() -> None:
        new_entities: list[NikoVdsCamera] = []
        for mac_address in coordinator.data.devices:
            if mac_address in entities:
                continue
            entity = NikoVdsCamera(coordinator, runtime.controller_id, mac_address)
            entities[mac_address] = entity
            new_entities.append(entity)
        if new_entities:
            async_add_entities(new_entities)

    sync_entities()
    entry.async_on_unload(coordinator.async_add_listener(sync_entities))


class NikoVdsCamera(NikoVdsCoordinatorEntity, Camera):
    """Representation of a Niko VDS preview image."""

    _attr_should_poll = False

    def __init__(self, coordinator, controller_id: str, mac_address: str) -> None:
        super().__init__(coordinator, controller_id, mac_address)
        self._attr_unique_id = f"{controller_id}:{mac_address}:camera"

    @property
    def name(self) -> str | None:
        device = self.coordinator.data.devices.get(self._mac_address)
        return device.name if device else f"VDS {self._mac_address.upper()}"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._mac_address in self.coordinator.data.images

    @property
    def content_type(self) -> str:
        return self.coordinator.data.content_types.get(self._mac_address, "image/jpeg")

    @property
    def extra_state_attributes(self) -> dict[str, str | int]:
        device = self.coordinator.data.devices.get(self._mac_address)
        attributes: dict[str, str | int] = {
            "controller_ip": self.coordinator.client.config.controller_ip,
            "mac_address": self._mac_address,
        }
        if not device:
            return attributes
        if device.ip_address:
            attributes["vds_ip_address"] = device.ip_address
        if device.product_id:
            attributes["product_id"] = device.product_id
        if device.software_version:
            attributes["software_version"] = device.software_version
        if device.number_of_buttons is not None:
            attributes["number_of_buttons"] = device.number_of_buttons
        error = self.coordinator.data.errors.get(self._mac_address)
        if error:
            attributes["last_error"] = error
        return attributes

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        return self.coordinator.data.images.get(self._mac_address)
