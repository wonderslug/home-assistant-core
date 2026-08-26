"""Tests for the Modern Forms button platform."""

from unittest.mock import patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration, init_integration_gen4

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_no_identify_buttons_on_legacy_fan(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test identify buttons aren't created for Gen 1/2/3 fans."""
    await init_integration(hass, aioclient_mock)

    assert hass.states.get("button.modernformsfan_identify") is None


async def test_identify_buttons_gen4(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the creation of identify buttons for a multi-fixture Gen4 fan."""
    await init_integration_gen4(hass, aioclient_mock)

    state = hass.states.get("button.modernformsfan_identify")
    assert state
    entry = entity_registry.async_get("button.modernformsfan_identify")
    assert entry
    assert entry.unique_id == "AA:BB:CC:00:11:22_identify"

    state = hass.states.get("button.modernformsfan_identify_uplight")
    assert state
    entry = entity_registry.async_get("button.modernformsfan_identify_uplight")
    assert entry
    assert entry.unique_id == "AA:BB:CC:00:11:22_2_identify"

    state = hass.states.get("button.modernformsfan_identify_downlight")
    assert state
    entry = entity_registry.async_get("button.modernformsfan_identify_downlight")
    assert entry
    assert entry.unique_id == "AA:BB:CC:00:11:22_3_identify"


async def test_identify_fan_button_press(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test pressing the device-level identify button."""
    await init_integration_gen4(hass, aioclient_mock)

    with patch("aiomodernforms.ModernFormsDevice.fan") as fan_mock:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.modernformsfan_identify"},
            blocking=True,
        )
        await hass.async_block_till_done()
        fan_mock.assert_called_once_with(identify=True)


async def test_identify_light_button_press(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test pressing a per-fixture identify button."""
    await init_integration_gen4(hass, aioclient_mock)

    with patch("aiomodernforms.ModernFormsDevice.light_fixture") as light_fixture_mock:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.modernformsfan_identify_uplight"},
            blocking=True,
        )
        await hass.async_block_till_done()
        light_fixture_mock.assert_called_once_with(2, identify=True)
