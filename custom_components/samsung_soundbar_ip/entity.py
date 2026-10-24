"""Base entity for the soundbar."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SoundbarCoordinator


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
