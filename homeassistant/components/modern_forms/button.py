"""Support for Modern Forms identify buttons."""

from typing import override

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import modernforms_exception_handler
from .coordinator import ModernFormsConfigEntry, ModernFormsDataUpdateCoordinator
from .entity import ModernFormsDeviceEntity, strip_device_name_prefix


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ModernFormsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Modern Forms buttons based on a config entry."""
    coordinator = config_entry.runtime_data

    if not coordinator.data.has_identify():
        return

    async_add_entities(
        ModernFormsIdentifyLightButton(
            config_entry.entry_id, coordinator, light.address
        )
        for light in coordinator.data.state.light_fixtures
    )


class ModernFormsIdentifyLightButton(ModernFormsDeviceEntity, ButtonEntity):
    """Defines a Modern Forms light fixture identify button."""

    _attr_device_class = ButtonDeviceClass.IDENTIFY
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        entry_id: str,
        coordinator: ModernFormsDataUpdateCoordinator,
        # Always a real address: this class is only constructed for Gen4
        # fixtures (has_identify() is Gen4-only), which never have address=None.
        light_address: int,
    ) -> None:
        """Initialize the fixture identify button."""
        super().__init__(entry_id=entry_id, coordinator=coordinator)
        self._address = light_address
        mac_address = self.coordinator.data.info.mac_address
        self._attr_unique_id = f"{mac_address}_{light_address}_identify"
        self._attr_translation_key = "identify_light"
        self._attr_translation_placeholders = {"fixture_name": self._light_name}

    @property
    def _light_name(self) -> str:
        """Return this fixture's current name."""
        device_name = self.coordinator.data.info.device_name
        for light in self.coordinator.data.state.light_fixtures:
            if light.address == self._address:
                return strip_device_name_prefix(device_name, light.name)
        return ""

    @modernforms_exception_handler
    @override
    async def async_press(self) -> None:
        """Trigger this fixture's physical identify signal."""
        await self.coordinator.modern_forms.light_fixture(self._address, identify=True)
