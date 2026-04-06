"""Shared entity helpers for Niko VDS."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NikoVdsCoordinator


class NikoVdsCoordinatorEntity(CoordinatorEntity[NikoVdsCoordinator]):
    """Base coordinator-backed entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NikoVdsCoordinator, controller_id: str, mac_address: str) -> None:
        super().__init__(coordinator)
        self._controller_id = controller_id
        self._mac_address = mac_address

    @property
    def device_info(self) -> DeviceInfo:
        device = self.coordinator.data.devices.get(self._mac_address)
        model = "Video Door Station"
        if device and device.product_id:
            model = device.product_id
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._controller_id}:{self._mac_address}")},
            manufacturer="Niko",
            model=model,
            name=device.name if device else f"VDS {self._mac_address.upper()}",
            sw_version=device.software_version if device else None,
            configuration_url=f"https://{self.coordinator.client.config.controller_ip}",
        )
