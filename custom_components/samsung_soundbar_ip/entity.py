"""Base entity for the soundbar."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import SoundbarError
from .const import DOMAIN
from .coordinator import SoundbarCoordinator


def soundbar_command[E: "SoundbarEntity", **P](
    func: Callable[Concatenate[E, P], Awaitable[None]],
) -> Callable[Concatenate[E, P], Coroutine[Any, Any, None]]:
    """Report a failed command as a readable error instead of a traceback."""

    @wraps(func)
    async def wrapper(self: E, *args: P.args, **kwargs: P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except SoundbarError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    return wrapper


class SoundbarEntity(CoordinatorEntity[SoundbarCoordinator]):
    """Ties every entity to the one soundbar device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SoundbarCoordinator, key: str | None) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        info = coordinator.info
        self._attr_unique_id = f"{entry.unique_id}_{key}" if key else entry.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            manufacturer="Samsung",
            model=info.model,
            model_id=info.identifier,
            name=info.name or info.model or "Samsung Soundbar",
            serial_number=info.serial_number,
        )
