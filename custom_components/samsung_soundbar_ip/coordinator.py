"""Data update coordinator for the soundbar state."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SoundbarClient, SoundbarError, SoundbarInfo, SoundbarState
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN, FAILURES_BEFORE_UNAVAILABLE

_LOGGER = logging.getLogger(__name__)


class SoundbarCoordinator(DataUpdateCoordinator[SoundbarState]):
    """Polls the soundbar and holds its latest state."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: SoundbarClient,
        info: SoundbarInfo,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {client.host}",
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self.info = info
        self._failures = 0

    async def _async_update_data(self) -> SoundbarState:
        try:
            state = await self.client.get_state()
        except SoundbarError as err:
            self._failures += 1
            # Ride out short blips with the last known state instead of
            # flapping to unavailable (which automations may react to)
            if self.data is not None and self._failures < FAILURES_BEFORE_UNAVAILABLE:
                _LOGGER.debug("Poll %s failed (%s), keeping last state", self._failures, err)
                return self.data
            raise UpdateFailed(str(err)) from err
        self._failures = 0
        return state

    def apply(self, **changes: Any) -> None:
        """Publish the result of a command right away; the next poll confirms it."""
        if self.data is not None:
            self.async_set_updated_data(replace(self.data, **changes))
