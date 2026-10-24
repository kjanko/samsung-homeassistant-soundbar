"""Media player entity for the soundbar."""

from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SoundbarConfigEntry
from .const import SOUND_MODES, SOURCES
from .coordinator import SoundbarCoordinator
from .entity import SoundbarEntity

PARALLEL_UPDATES = 1

_SOURCE_CODES = {name: code for code, name in SOURCES.items()}
_SOUND_MODE_CODES = {name: code for code, name in SOUND_MODES.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SoundbarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([SoundbarMediaPlayer(entry.runtime_data)])


class SoundbarMediaPlayer(SoundbarEntity, MediaPlayerEntity):
    """The soundbar: power, volume, mute, input and sound mode."""

    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )
    _attr_source_list = list(SOURCES.values())
    _attr_sound_mode_list = list(SOUND_MODES.values())
    _attr_volume_step = 0.01

    def __init__(self, coordinator: SoundbarCoordinator) -> None:
        super().__init__(coordinator, None)

    @property
    def state(self) -> MediaPlayerState:
        return MediaPlayerState.ON if self.coordinator.data.power else MediaPlayerState.OFF

    @property
    def volume_level(self) -> float | None:
        volume = self.coordinator.data.volume
        return None if volume is None else volume / 100

    @property
    def is_volume_muted(self) -> bool | None:
        return self.coordinator.data.muted

    @property
    def source(self) -> str | None:
        code = self.coordinator.data.source
        # Unknown inputs are shown as the raw code rather than hidden
        return SOURCES.get(code, code) if code else None

    @property
    def sound_mode(self) -> str | None:
        code = self.coordinator.data.sound_mode
        return SOUND_MODES.get(code, code) if code else None

    async def async_turn_on(self) -> None:
        await self.coordinator.client.set_power(True)
        # Volume, input etc. are only read while the soundbar is on
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        await self.coordinator.client.set_power(False)
        self.coordinator.apply(power=False)

    async def async_set_volume_level(self, volume: float) -> None:
        level = round(volume * 100)
        await self.coordinator.client.set_volume(level)
        self.coordinator.apply(volume=level)

    async def async_volume_up(self) -> None:
        await self.coordinator.client.volume_up()
        self._apply_volume_step(+1)

    async def async_volume_down(self) -> None:
        await self.coordinator.client.volume_down()
        self._apply_volume_step(-1)

    def _apply_volume_step(self, delta: int) -> None:
        if self.coordinator.data.volume is not None:
            self.coordinator.apply(volume=max(0, min(100, self.coordinator.data.volume + delta)))

    async def async_mute_volume(self, mute: bool) -> None:
        await self.coordinator.client.set_muted(mute)
        self.coordinator.apply(muted=mute)

    async def async_select_source(self, source: str) -> None:
        code = _SOURCE_CODES.get(source, source)
        await self.coordinator.client.set_source(code)
        self.coordinator.apply(source=code)

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        code = _SOUND_MODE_CODES.get(sound_mode, sound_mode)
        await self.coordinator.client.set_sound_mode(code)
        self.coordinator.apply(sound_mode=code)
