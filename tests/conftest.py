"""Fixtures for the Home Assistant tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.samsung_soundbar_ip.api import SoundbarInfo, SoundbarState

pytest_plugins = "pytest_homeassistant_custom_component"

HOST = "192.168.50.238"
UDN = "00000000-1111-2222-3333-444444444444"
INFO = SoundbarInfo(
    model="HW-Q990D", identifier="22_AV_HW-Q990D", name="Q990D", serial_number="SERIAL123", udn=UDN,
    firmware="SAT-MT8532D24WWC-1072.1"
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def client():
    """A mocked SoundbarClient used by both setup and the config flow."""
    mock = MagicMock()
    mock.host = HOST
    mock.get_info = AsyncMock(return_value=INFO)
    mock.get_state = AsyncMock(
        return_value=SoundbarState(
            power=True, volume=10, muted=False, source="E_ARC", sound_mode="ADAPTIVE", codec="MAT_PCM"
        )
    )
    for name in (
        "set_power", "set_volume", "volume_up", "volume_down", "set_muted",
        "set_source", "set_sound_mode", "woofer_up", "woofer_down",
    ):
        setattr(mock, name, AsyncMock())
    mock._volume_control_supported = True
    mock._mute_control_supported = True
    with (
        patch("custom_components.samsung_soundbar_ip.SoundbarClient", return_value=mock),
        patch("custom_components.samsung_soundbar_ip.config_flow.SoundbarClient", return_value=mock),
    ):
        yield mock
