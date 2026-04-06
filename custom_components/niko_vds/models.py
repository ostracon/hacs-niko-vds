"""Data models for the Niko VDS integration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class NikoVdsDevice:
    """A discovered Niko VDS endpoint."""

    mac_address: str
    name: str
    ip_address: str | None = None
    number_of_buttons: int | None = None
    product_id: str | None = None
    software_version: str | None = None


@dataclass(slots=True)
class NikoVdsCoordinatorData:
    """Coordinator state for all discovered VDS entities."""

    devices: dict[str, NikoVdsDevice]
    images: dict[str, bytes]
    content_types: dict[str, str]
    errors: dict[str, str]


@dataclass(slots=True)
class NikoVdsRuntimeData:
    """Runtime data attached to the config entry."""

    client: object
    coordinator: object
    controller_id: str
