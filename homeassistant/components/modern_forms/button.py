"""Support for Modern Forms identify buttons."""

from typing import override

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import modernforms_exception_handler
from .coordinator import ModernFormsConfigEntry, ModernFormsDataUpdateCoordinator
from .entity import ModernFormsDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ModernFormsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Modern Forms buttons based on a config entry."""
    coordinator = config_entry.runtime_data

    if not coordinator.data.has_identify():
        return

    entities: list[ModernFormsDeviceEntity] = [
        ModernFormsIdentifyFanButton(config_entry.entry_id, coordinator)
    ]
    entities.extend(
        ModernFormsIdentifyLightButton(
            config_entry.entry_id, coordinator, light.address
        )
        for light in coordinator.data.state.light_fixtures
    )

    async_add_entities(entities)


class ModernFormsIdentifyFanButton(ModernFormsDeviceEntity, ButtonEntity):
    """Defines a Modern Forms fan identify button."""

    _attr_device_class = ButtonDeviceClass.IDENTIFY
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, entry_id: str, coordinator: ModernFormsDataUpdateCoordinator
    ) -> None:
        """Initialize the identify button."""
        super().__init__(entry_id=entry_id, coordinator=coordinator)
        self._attr_unique_id = f"{self.coordinator.data.info.mac_address}_identify"

    @modernforms_exception_handler
    @override
    async def async_press(self) -> None:
        """Trigger the fan's physical identify signal."""
        await self.coordinator.modern_forms.fan(identify=True)


class ModernFormsIdentifyLightButton(ModernFormsDeviceEntity, ButtonEntity):
    """Defines a Modern Forms light fixture identify button."""

    _attr_device_class = ButtonDeviceClass.IDENTIFY
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        entry_id: str,
        coordinator: ModernFormsDataUpdateCoordinator,
        light_address: int,
    ) -> None:
        """Initialize the fixture identify button."""
        super().__init__(entry_id=entry_id, coordinator=coordinator)
        self._address = light_address
        mac_address = self.coordinator.data.info.mac_address
        self._attr_unique_id = f"{mac_address}_{light_address}_identify"
        self._attr_name = f"Identify {self._light_name}"

    @property
    def _light_name(self) -> str:
        """Return this fixture's current name."""
        for light in self.coordinator.data.state.light_fixtures:
            if light.address == self._address:
                return light.name
        return ""

    @modernforms_exception_handler
    @override
    async def async_press(self) -> None:
        """Trigger this fixture's physical identify signal."""
        await self.coordinator.modern_forms.light_fixture(self._address, identify=True)
