"""Coordinator for Niko VDS data."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NikoVdsClient, NikoVdsError
from .const import DOMAIN
from .models import NikoVdsCoordinatorData

LOGGER = logging.getLogger(__name__)


class NikoVdsCoordinator(DataUpdateCoordinator[NikoVdsCoordinatorData]):
    """Coordinate discovery and snapshot polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: NikoVdsClient,
        poll_interval: int,
    ) -> None:
        super().__init__(
            hass,
            logger=LOGGER,
            name=f"{DOMAIN}-{client.config.controller_ip}",
            update_interval=timedelta(seconds=poll_interval),
        )
        self.client = client

    async def _async_update_data(self) -> NikoVdsCoordinatorData:
        try:
            return await self.hass.async_add_executor_job(self.client.fetch_state)
        except NikoVdsError as err:
            raise UpdateFailed(str(err)) from err
