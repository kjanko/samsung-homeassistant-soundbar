"""Tests for setup, entities and commands."""

from datetime import timedelta

import pytest
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
)
from homeassistant.components.media_player import (
    DOMAIN as MP_DOMAIN,
)
from homeassistant.const import CONF_HOST, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.samsung_soundbar_ip.api import SoundbarConnectionError, SoundbarState
from custom_components.samsung_soundbar_ip.const import DOMAIN

from .conftest import HOST, UDN

MP = "media_player.q990d"


@pytest.fixture
async def entry(hass, client):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=UDN, data={CONF_HOST: HOST}, title="Q990D")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _poll(hass):
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()


async def test_entities_are_created(hass, entry):
    state = hass.states.get(MP)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.1
    assert state.attributes[ATTR_INPUT_SOURCE] == "eARC"
    assert state.attributes[ATTR_SOUND_MODE] == "Adaptive"
    assert hass.states.get("sensor.q990d_audio_format").state == "MAT_PCM"
    assert hass.states.get("button.q990d_woofer_up") is not None
    assert hass.states.get("button.q990d_woofer_down") is not None


async def test_volume_set_is_exact_and_shows_immediately(hass, entry, client):
    await hass.services.async_call(
        MP_DOMAIN, "volume_set", {"entity_id": MP, ATTR_MEDIA_VOLUME_LEVEL: 0.29}, blocking=True
    )
    client.set_volume.assert_awaited_once_with(29)
    assert hass.states.get(MP).attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.29


async def test_volume_steps_by_one(hass, entry, client):
    await hass.services.async_call(MP_DOMAIN, "volume_up", {"entity_id": MP}, blocking=True)
    client.volume_up.assert_awaited_once()
    assert hass.states.get(MP).attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.11


async def test_mute_sets_rather_than_toggles(hass, entry, client):
    await hass.services.async_call(
        MP_DOMAIN, "volume_mute", {"entity_id": MP, ATTR_MEDIA_VOLUME_MUTED: True}, blocking=True
    )
    client.set_muted.assert_awaited_once_with(True)
    assert hass.states.get(MP).attributes[ATTR_MEDIA_VOLUME_MUTED] is True


async def test_source_and_sound_mode_use_api_codes(hass, entry, client):
    await hass.services.async_call(
        MP_DOMAIN, "select_source", {"entity_id": MP, ATTR_INPUT_SOURCE: "Optical"}, blocking=True
    )
    client.set_source.assert_awaited_once_with("D_IN")
    await hass.services.async_call(
        MP_DOMAIN, "select_sound_mode", {"entity_id": MP, ATTR_SOUND_MODE: "Clear voice"}, blocking=True
    )
    client.set_sound_mode.assert_awaited_once_with("CLEARVOICE")
    assert hass.states.get(MP).attributes[ATTR_INPUT_SOURCE] == "Optical"


async def test_woofer_button(hass, entry, client):
    await hass.services.async_call("button", "press", {"entity_id": "button.q990d_woofer_up"}, blocking=True)
    client.woofer_up.assert_awaited_once()


async def test_off_soundbar_is_off_not_unavailable(hass, entry, client):
    client.get_state.return_value = SoundbarState(power=False)
    await _poll(hass)
    state = hass.states.get(MP)
    assert state.state == STATE_OFF
    assert ATTR_MEDIA_VOLUME_LEVEL not in state.attributes


async def test_short_blips_keep_last_state(hass, entry, client):
    client.get_state.side_effect = SoundbarConnectionError("timeout")
    await _poll(hass)
    await _poll(hass)
    assert hass.states.get(MP).state == STATE_ON
    assert hass.states.get(MP).attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.1
    await _poll(hass)
    assert hass.states.get(MP).state == STATE_UNAVAILABLE
    client.get_state.side_effect = None
    await _poll(hass)
    assert hass.states.get(MP).state == STATE_ON


async def test_diagnostics_redacts_ids(hass, entry):
    from custom_components.samsung_soundbar_ip.diagnostics import async_get_config_entry_diagnostics

    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["device"]["serial_number"] == "**REDACTED**"
    assert diag["state"]["volume"] == 10


async def test_rejected_sound_mode_is_hidden_and_reported(hass, entry, client):
    from homeassistant.components.media_player import ATTR_SOUND_MODE_LIST
    from homeassistant.exceptions import HomeAssistantError

    from custom_components.samsung_soundbar_ip.api import SoundbarRejectedError

    client.set_sound_mode.side_effect = SoundbarRejectedError("soundModeControl rejected")
    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            MP_DOMAIN, "select_sound_mode", {"entity_id": MP, ATTR_SOUND_MODE: "Movie"}, blocking=True
        )
    assert exc.value.translation_key == "sound_mode_not_supported"
    assert "Movie" not in hass.states.get(MP).attributes[ATTR_SOUND_MODE_LIST]
    assert "Surround" in hass.states.get(MP).attributes[ATTR_SOUND_MODE_LIST]
    # Remembered in the entry, without reloading the integration
    assert entry.data["unsupported_sound_modes"] == ["MOVIE"]
    assert entry.state.name == "LOADED"
    assert hass.states.get(MP).state == STATE_ON


async def test_hidden_sound_modes_survive_a_reload(hass, entry):
    from homeassistant.components.media_player import ATTR_SOUND_MODE_LIST

    hass.config_entries.async_update_entry(entry, data={**entry.data, "unsupported_sound_modes": ["CLEARVOICE"]})
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert "Clear voice" not in hass.states.get(MP).attributes[ATTR_SOUND_MODE_LIST]


async def test_failed_command_is_a_readable_error(hass, entry, client):
    from homeassistant.exceptions import HomeAssistantError

    client.set_volume.side_effect = SoundbarConnectionError("timed out")
    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            MP_DOMAIN, "volume_set", {"entity_id": MP, ATTR_MEDIA_VOLUME_LEVEL: 0.5}, blocking=True
        )
    assert exc.value.translation_key == "command_failed"
    assert hass.states.get(MP).attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.1


async def test_failed_button_press_is_a_readable_error(hass, entry, client):
    from homeassistant.exceptions import HomeAssistantError

    client.woofer_up.side_effect = SoundbarConnectionError("timed out")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("button", "press", {"entity_id": "button.q990d_woofer_up"}, blocking=True)


async def test_changing_options_still_reloads(hass, entry, client):
    from custom_components.samsung_soundbar_ip.const import CONF_SCAN_INTERVAL

    calls_before = client.get_info.await_count
    hass.config_entries.async_update_entry(entry, options={CONF_SCAN_INTERVAL: 5})
    await hass.async_block_till_done()
    assert client.get_info.await_count == calls_before + 1
