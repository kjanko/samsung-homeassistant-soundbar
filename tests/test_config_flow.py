"""Tests for the config flow."""

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.samsung_soundbar_ip.api import SoundbarConnectionError
from custom_components.samsung_soundbar_ip.const import CONF_SCAN_INTERVAL, DOMAIN

from .conftest import HOST, UDN


def _ssdp(host=HOST, udn=UDN):
    return SsdpServiceInfo(
        ssdp_usn=f"uuid:{udn}::urn:samsung.com:device:IPControlServer:1",
        ssdp_st="urn:samsung.com:device:IPControlServer:1",
        ssdp_location=f"http://{host}:9110/ip_control",
        ssdp_udn=f"uuid:{udn}",
        upnp={"deviceType": "urn:samsung.com:device:IPControlServer:1", "friendlyName": "Q990D"},
    )


async def test_user_flow_creates_entry(hass, client):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: f" {HOST} "})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Q990D"
    assert result["data"] == {CONF_HOST: HOST}
    assert result["result"].unique_id == UDN


async def test_user_flow_cannot_connect_then_recovers(hass, client):
    client.get_info.side_effect = SoundbarConnectionError("down")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})
    assert result["errors"] == {"base": "cannot_connect"}
    client.get_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_ssdp_discovery_asks_to_confirm(hass, client):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=_ssdp()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: HOST}


async def test_manual_setup_works_while_discovery_is_pending(hass, client):
    discovered = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=_ssdp()
    )
    assert discovered["step_id"] == "confirm"
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_ssdp_updates_ip_of_known_soundbar(hass, client):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=UDN, data={CONF_HOST: "192.168.50.99"})
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=_ssdp()
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == HOST


async def test_ssdp_aborts_when_ip_control_is_off(hass, client):
    client.get_info.side_effect = SoundbarConnectionError("refused")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=_ssdp()
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_options_flow_sets_poll_interval(hass, client):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=UDN, data={CONF_HOST: HOST})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_SCAN_INTERVAL: 1})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SCAN_INTERVAL] == 1
