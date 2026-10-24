"""Samsung Soundbar (IP control) integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SoundbarClient, SoundbarError
from .const import PLATFORMS
from .coordinator import SoundbarCoordinator

type SoundbarConfigEntry = ConfigEntry[SoundbarCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SoundbarConfigEntry) -> bool:
    """Set up a soundbar from a config entry."""
    client = SoundbarClient(entry.data[CONF_HOST], async_get_clientsession(hass, verify_ssl=False))
    try:
        info = await client.get_info()
    except SoundbarError as err:
        raise ConfigEntryNotReady(f"Soundbar at {client.host} is not reachable: {err}") from err

    coordinator = SoundbarCoordinator(hass, entry, client, info)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options_change))
    return True


async def _async_reload_on_options_change(hass: HomeAssistant, entry: SoundbarConfigEntry) -> None:
    # Entry data also changes when a sound mode is marked unsupported; that needs no reload
    if dict(entry.options) != entry.runtime_data.options_at_setup:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SoundbarConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
