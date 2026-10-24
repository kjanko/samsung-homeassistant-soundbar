"""Async client for the Samsung soundbar IP control API (JSON-RPC on port 1516).

Behaviour observed on a HW-Q990D (firmware 2026):
  - Every call except createAccessToken needs an AccessToken param.
  - The soundbar keeps only ~5-6 tokens and silently drops the least recently
    used one when another client creates a new token. A dropped or invalid
    token gets a top-level {"code": -32700, "message": "Parse error"} reply
    with no "result" key, so the client renews the token and retries once.
  - Unknown methods return {"error": {"code": -32601, "message": "Method not found"}}.
  - "<x>Control" methods read a value when called without params and set it
    when called with one; a rejected value comes back as {"success": false}.
  - The server misbehaves with concurrent requests, so calls are serialized.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree

import aiohttp

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 1516
UPNP_PORT = 9110
UPNP_DESCRIPTION_PATH = "/ip_control"
# Tizen device info (the soundbar runs Tizen); open, read-only
TIZEN_PORT = 8001
TIZEN_INFO_PATH = "/api/v2/"

METHOD_NOT_FOUND = -32601
PARSE_ERROR = -32700

POWER_ON = "powerOn"
POWER_OFF = "powerOff"


class SoundbarError(Exception):
    """Base error for the soundbar client."""


class SoundbarConnectionError(SoundbarError):
    """The soundbar could not be reached."""


class SoundbarApiError(SoundbarError):
    """The soundbar answered with an error."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class SoundbarRejectedError(SoundbarApiError):
    """The soundbar refused a value ({"success": false}), e.g. a sound mode this model lacks."""


@dataclass
class SoundbarState:
    """One snapshot of the soundbar's state."""

    power: bool
    volume: int | None = None
    muted: bool | None = None
    source: str | None = None
    sound_mode: str | None = None
    codec: str | None = None


@dataclass
class SoundbarInfo:
    """Static device details, from the API, the UPnP description and Tizen device info."""

    model: str | None = None
    identifier: str | None = None
    name: str | None = None
    serial_number: str | None = None
    udn: str | None = None
    firmware: str | None = None


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() in ("true", "on", "1")
    return bool(value)


def parse_upnp_description(xml_text: str) -> SoundbarInfo:
    """Read model, name, serial number and UDN from the UPnP device description."""
    root = ElementTree.fromstring(xml_text)
    info = SoundbarInfo()
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        text = (element.text or "").strip() or None
        if tag == "modelName" and info.model is None:
            info.model = text
        elif tag == "friendlyName" and info.name is None:
            info.name = text
        elif tag == "serialNumber" and info.serial_number is None:
            info.serial_number = text
        elif tag == "UDN" and info.udn is None:
            info.udn = text.removeprefix("uuid:") if text else None
    return info


class SoundbarClient:
    """Talks to one soundbar. Safe to share between entities."""

    def __init__(
        self,
        host: str,
        session: aiohttp.ClientSession,
        *,
        port: int = DEFAULT_PORT,
        upnp_port: int = UPNP_PORT,
        tizen_port: int = TIZEN_PORT,
        timeout: float = 5,
    ) -> None:
        self.host = host
        self._upnp_url = f"http://{host}:{upnp_port}{UPNP_DESCRIPTION_PATH}"
        self._tizen_url = f"http://{host}:{tizen_port}{TIZEN_INFO_PATH}"
        self._session = session
        self._url = f"https://{host}:{port}/"
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._token: str | None = None
        self._lock = asyncio.Lock()
        # Flipped off the first time a model answers "Method not found"
        self._volume_control_supported = True
        self._mute_control_supported = True

    # ------------------ transport ------------------
    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw = json.dumps(payload, separators=(",", ":"))
        try:
            async with self._session.post(
                self._url,
                data=raw,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                ssl=False,
                timeout=self._timeout,
            ) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError, ValueError) as err:
            raise SoundbarConnectionError(f"{self.host}: {err!r}") from err

    async def _request(self, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "id": 1}
        if params:
            payload["params"] = params
        return await self._post(payload)

    async def _create_token(self) -> str:
        data = await self._request("createAccessToken", None)
        try:
            self._token = data["result"]["AccessToken"]
        except (KeyError, TypeError) as err:
            raise SoundbarApiError(f"No access token in reply: {data}") from err
        return self._token

    async def call(self, method: str, **params: Any) -> dict[str, Any]:
        """Call a method and return its "result", renewing the token once if needed."""
        async with self._lock:
            for attempt in range(2):
                if self._token is None:
                    await self._create_token()
                data = await self._request(method, {**params, "AccessToken": self._token})
                if "result" in data:
                    return data["result"]
                error = data.get("error", data)
                code = error.get("code") if isinstance(error, dict) else None
                if code == PARSE_ERROR and attempt == 0:
                    # The soundbar dropped our token; get a fresh one and retry
                    _LOGGER.debug("Token rejected by %s, renewing", self.host)
                    self._token = None
                    continue
                message = error.get("message") if isinstance(error, dict) else str(error)
                raise SoundbarApiError(f"{method}: {message}", code)
        raise AssertionError("unreachable")

    async def _set(self, method: str, **params: Any) -> None:
        result = await self.call(method, **params)
        if isinstance(result, dict) and result.get("success") is False:
            raise SoundbarRejectedError(f"{method} rejected {params}")

    # ------------------ reads ------------------
    async def get_power(self) -> bool:
        return (await self.call("powerControl"))["power"] == POWER_ON

    async def get_volume(self) -> int:
        return int((await self.call("getVolume"))["volume"])

    async def get_muted(self) -> bool:
        return _as_bool((await self.call("getMute"))["mute"])

    async def get_source(self) -> str:
        return (await self.call("inputSelectControl"))["inputSource"]

    async def get_sound_mode(self) -> str:
        return (await self.call("soundModeControl"))["soundMode"]

    async def get_codec(self) -> str | None:
        return (await self.call("getCodec")).get("codec") or None

    async def get_identifier(self) -> str | None:
        return (await self.call("getIdentifier")).get("identifier")

    async def get_state(self) -> SoundbarState:
        """Read everything. When the soundbar is off, only power is read."""
        if not await self.get_power():
            return SoundbarState(power=False)
        return SoundbarState(
            power=True,
            volume=await self.get_volume(),
            muted=await self.get_muted(),
            source=await self.get_source(),
            sound_mode=await self.get_sound_mode(),
            codec=await self._get_optional(self.get_codec),
        )

    async def _get_optional(self, getter):
        try:
            return await getter()
        except SoundbarApiError:
            return None

    async def get_info(self) -> SoundbarInfo:
        """Device details. The UPnP description and Tizen info are best-effort."""
        info = SoundbarInfo()
        try:
            async with self._session.get(self._upnp_url, timeout=self._timeout) as resp:
                resp.raise_for_status()
                info = parse_upnp_description(await resp.text())
        except (TimeoutError, aiohttp.ClientError, ElementTree.ParseError) as err:
            _LOGGER.debug("No UPnP description from %s: %r", self.host, err)
        info.firmware = await self._get_firmware()
        info.identifier = await self.get_identifier()
        if info.model is None and info.identifier:
            # "22_AV_HW-Q990D" -> "HW-Q990D"
            info.model = info.identifier.rsplit("_", 1)[-1]
        return info

    async def _get_firmware(self) -> str | None:
        try:
            async with self._session.get(self._tizen_url, timeout=self._timeout) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError, ValueError) as err:
            _LOGGER.debug("No Tizen device info from %s: %r", self.host, err)
            return None
        device = data.get("device") if isinstance(data, dict) else None
        if not isinstance(device, dict):
            return None
        return device.get("firmwareVersion") or None

    # ------------------ commands ------------------
    async def set_power(self, on: bool) -> None:
        await self._set("powerControl", power=POWER_ON if on else POWER_OFF)

    async def volume_up(self) -> None:
        await self._set("remoteKeyControl", remoteKey="VOL_UP")

    async def volume_down(self) -> None:
        await self._set("remoteKeyControl", remoteKey="VOL_DOWN")

    async def set_volume(self, level: int) -> None:
        """Set an absolute volume (0-100) in one request where the model allows it."""
        if not 0 <= level <= 100:
            raise ValueError("Volume has to be in range 0-100")
        if self._volume_control_supported:
            try:
                await self._set("volumeControl", volume=level)
                return
            except SoundbarApiError as err:
                if err.code != METHOD_NOT_FOUND:
                    raise
                self._volume_control_supported = False
        # Older models: step there with key presses
        current = await self.get_volume()
        while current != level:
            if current < level:
                await self.volume_up()
                current += 1
            else:
                await self.volume_down()
                current -= 1

    async def set_muted(self, muted: bool) -> None:
        if self._mute_control_supported:
            try:
                await self._set("muteControl", mute=muted)
                return
            except SoundbarApiError as err:
                if err.code != METHOD_NOT_FOUND:
                    raise
                self._mute_control_supported = False
        # Older models only have a toggle key: read first so it can't invert
        if await self.get_muted() != muted:
            await self._set("remoteKeyControl", remoteKey="MUTE")

    async def set_source(self, source: str) -> None:
        await self._set("inputSelectControl", inputSource=source)

    async def set_sound_mode(self, sound_mode: str) -> None:
        await self._set("soundModeControl", soundMode=sound_mode)

    async def woofer_up(self) -> None:
        await self._set("remoteKeyControl", remoteKey="WOOFER_PLUS")

    async def woofer_down(self) -> None:
        await self._set("remoteKeyControl", remoteKey="WOOFER_MINUS")
