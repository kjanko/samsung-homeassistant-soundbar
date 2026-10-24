"""Audio format sensor for the soundbar."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SoundbarConfigEntry
from .coordinator import SoundbarCoordinator
from .entity import SoundbarEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SoundbarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([SoundbarAudioFormatSensor(entry.runtime_data)])


class SoundbarAudioFormatSensor(SoundbarEntity, SensorEntity):
    """The incoming audio format, as the soundbar reports it (e.g. MAT_PCM for Atmos over eARC)."""

    _attr_translation_key = "audio_format"

    def __init__(self, coordinator: SoundbarCoordinator) -> None:
        super().__init__(coordinator, "audio_format")

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.codec
