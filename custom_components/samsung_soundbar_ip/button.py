"""Woofer level buttons for the soundbar."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SoundbarConfigEntry
from .api import SoundbarClient
from .coordinator import SoundbarCoordinator
from .entity import SoundbarEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SoundbarButtonDescription(ButtonEntityDescription):
    press: Callable[[SoundbarClient], Awaitable[None]]


BUTTONS = (
    SoundbarButtonDescription(
        key="woofer_up",
        translation_key="woofer_up",
        entity_category=EntityCategory.CONFIG,
        press=lambda client: client.woofer_up(),
    ),
    SoundbarButtonDescription(
        key="woofer_down",
        translation_key="woofer_down",
        entity_category=EntityCategory.CONFIG,
        press=lambda client: client.woofer_down(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SoundbarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(SoundbarButton(entry.runtime_data, description) for description in BUTTONS)


class SoundbarButton(SoundbarEntity, ButtonEntity):
    """Presses a woofer key. The API can't read the woofer level back."""

    entity_description: SoundbarButtonDescription

    def __init__(self, coordinator: SoundbarCoordinator, description: SoundbarButtonDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        await self.entity_description.press(self.coordinator.client)
