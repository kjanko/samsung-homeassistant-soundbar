"""Diagnostics for the soundbar (Settings → Devices → Download diagnostics)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import SoundbarConfigEntry

TO_REDACT = {"serial_number", "udn"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: SoundbarConfigEntry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    client = coordinator.client
    return {
        "entry": {"data": dict(entry.data), "options": dict(entry.options)},
        "device": async_redact_data(asdict(coordinator.info), TO_REDACT),
        "state": asdict(coordinator.data) if coordinator.data else None,
        "last_update_success": coordinator.last_update_success,
        "volume_control_supported": client._volume_control_supported,
        "mute_control_supported": client._mute_control_supported,
    }
