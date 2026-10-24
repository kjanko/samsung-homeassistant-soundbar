"""Config flow for Samsung Soundbar (IP control)."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .api import SoundbarClient, SoundbarError, SoundbarInfo
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _unique_id(info: SoundbarInfo, host: str) -> str:
    # The UPnP UDN survives IP changes; the host is a last resort
    return info.udn or info.serial_number or host


class SoundbarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a soundbar by IP address or from SSDP discovery."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._info: SoundbarInfo | None = None

    async def _async_get_info(self, host: str) -> SoundbarInfo:
        client = SoundbarClient(host, async_get_clientsession(self.hass, verify_ssl=False))
        return await client.get_info()

    def _title(self) -> str:
        assert self._info is not None
        return self._info.name or self._info.model or self._host or "Samsung Soundbar"

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                self._info = await self._async_get_info(host)
            except SoundbarError as err:
                _LOGGER.debug("Cannot connect to %s: %s", host, err)
                errors["base"] = "cannot_connect"
            else:
                self._host = host
                # A pending discovery of the same soundbar must not block manual setup
                await self.async_set_unique_id(_unique_id(self._info, host), raise_on_progress=False)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(title=self._title(), data={CONF_HOST: host})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_ssdp(self, discovery_info: SsdpServiceInfo) -> ConfigFlowResult:
        host = urlparse(discovery_info.ssdp_location or "").hostname
        if not host:
            return self.async_abort(reason="cannot_connect")
        udn = (discovery_info.ssdp_udn or "").removeprefix("uuid:")
        if udn:
            # Known soundbar on a new IP: update it without asking
            await self.async_set_unique_id(udn)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self._async_abort_entries_match({CONF_HOST: host})

        try:
            self._info = await self._async_get_info(host)
        except SoundbarError:
            # IP control is switched off in the SmartThings app
            return self.async_abort(reason="cannot_connect")
        self._host = host
        await self.async_set_unique_id(_unique_id(self._info, host))
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self.context["title_placeholders"] = {"name": self._title()}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title=self._title(), data={CONF_HOST: self._host})
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"name": self._title(), "host": self._host or ""},
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                info = await self._async_get_info(host)
            except SoundbarError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(_unique_id(info, host), raise_on_progress=False)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(entry, data_updates={CONF_HOST: host})
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SoundbarOptionsFlow()


class SoundbarOptionsFlow(OptionsFlow):
    """Poll interval."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                    )
                }
            ),
        )
