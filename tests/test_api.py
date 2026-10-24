"""Tests for the soundbar API client against a fake soundbar."""

import asyncio
import sys
import unittest
from pathlib import Path

from aiohttp import web
from aiohttp.test_utils import TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "samsung_soundbar_ip"))

import aiohttp
import pytest
from api import (  # noqa: E402
    SoundbarApiError,
    SoundbarClient,
    SoundbarConnectionError,
    parse_upnp_description,
)

# The fake soundbar is a real local HTTP server; HA's test plugin blocks sockets by default
pytestmark = pytest.mark.enable_socket

UPNP_XML = """<?xml version="1.0"?>
<root xmlns="urn:samsung.com:device-1-0">
  <device>
    <deviceType>urn:samsung.com:device:IPControlServer:1</deviceType>
    <friendlyName>Q990D</friendlyName>
    <modelName>HW-Q990D</modelName>
    <serialNumber>SERIAL123</serialNumber>
    <UDN>uuid:00000000-aaaa-bbbb-cccc-dddddddddddd</UDN>
  </device>
</root>"""


class FakeSoundbar:
    """Mimics the JSON-RPC API of a HW-Q990D."""

    def __init__(self, *, volume_control=True, mute_control=True, power=True):
        self.volume = 10
        self.muted = False
        self.power = power
        self.source = "E_ARC"
        self.sound_mode = "ADAPTIVE"
        self.volume_control = volume_control
        self.mute_control = mute_control
        self.tokens: set[str] = set()
        self.token_counter = 0
        self.calls: list[str] = []
        self.in_flight = 0
        self.max_in_flight = 0

    def drop_tokens(self):
        self.tokens.clear()

    async def handle(self, request: web.Request) -> web.Response:
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0.005)
            body = await request.json()
            return web.json_response(self.dispatch(body["method"], body.get("params", {})))
        finally:
            self.in_flight -= 1

    def dispatch(self, method, params):
        self.calls.append(method)
        if method == "createAccessToken":
            self.token_counter += 1
            token = f"tok{self.token_counter}"
            self.tokens.add(token)
            return {"jsonrpc": "2.0", "id": "1", "result": {"AccessToken": token}}
        if params.get("AccessToken") not in self.tokens:
            return {"code": -32700, "message": "Parse error"}
        value = {k: v for k, v in params.items() if k != "AccessToken"}
        ok = {"jsonrpc": "2.0", "id": "1", "result": {"success": True}}

        def result(**r):
            return {"jsonrpc": "2.0", "id": "1", "result": r}

        if method == "powerControl":
            if "power" in value:
                self.power = value["power"] == "powerOn"
                return ok
            return result(power="powerOn" if self.power else "powerOff")
        if method == "getVolume":
            return result(volume=str(self.volume))
        if method == "getMute":
            return result(mute=self.muted)
        if method == "volumeControl" and self.volume_control:
            if "volume" in value:
                if not 0 <= value["volume"] <= 100:
                    return result(success=False)
                self.volume = value["volume"]
                return ok
            return result(volume=str(self.volume))
        if method == "muteControl" and self.mute_control:
            if "mute" in value:
                self.muted = value["mute"]
                return ok
            return result(mute=self.muted)
        if method == "remoteKeyControl":
            key = value["remoteKey"]
            if key == "VOL_UP":
                self.volume += 1
            elif key == "VOL_DOWN":
                self.volume -= 1
            elif key == "MUTE":
                self.muted = not self.muted
            return ok
        if method == "inputSelectControl":
            if "inputSource" in value:
                self.source = value["inputSource"]
                return ok
            return result(inputSource=self.source)
        if method == "soundModeControl":
            if "soundMode" in value:
                self.sound_mode = value["soundMode"]
                return ok
            return result(soundMode=self.sound_mode)
        if method == "getCodec":
            return result(codec="MAT_PCM")
        if method == "getIdentifier":
            return result(identifier="22_AV_HW-Q990D")
        return {"jsonrpc": "2.0", "id": "1", "error": {"code": -32601, "message": "Method not found"}}


class ClientTestCase(unittest.IsolatedAsyncioTestCase):
    fake_kwargs: dict = {}

    async def asyncSetUp(self):
        self.fake = FakeSoundbar(**self.fake_kwargs)
        app = web.Application()
        app.router.add_post("/", self.fake.handle)
        app.router.add_get("/ip_control", self._upnp_description)
        self.server = TestServer(app)
        await self.server.start_server()
        self.session = aiohttp.ClientSession()
        self.client = SoundbarClient("127.0.0.1", self.session, port=self.server.port, upnp_port=self.server.port)
        # The fake serves plain HTTP on one port
        self.client._url = f"http://127.0.0.1:{self.server.port}/"

    @staticmethod
    async def _upnp_description(request):
        return web.Response(text=UPNP_XML, content_type="text/xml")

    async def asyncTearDown(self):
        await self.session.close()
        await self.server.close()


class TestTokens(ClientTestCase):
    async def test_token_is_created_once_and_reused(self):
        await self.client.get_volume()
        await self.client.get_volume()
        self.assertEqual(self.fake.calls.count("createAccessToken"), 1)

    async def test_dropped_token_is_renewed_and_call_retried(self):
        self.assertEqual(await self.client.get_volume(), 10)
        self.fake.drop_tokens()
        self.fake.volume = 12
        self.assertEqual(await self.client.get_volume(), 12)
        self.assertEqual(self.fake.calls.count("createAccessToken"), 2)

    async def test_persistent_parse_error_raises_instead_of_looping(self):
        self.fake.dispatch_orig = self.fake.dispatch
        self.fake.dispatch = lambda m, p: (
            self.fake.dispatch_orig(m, p) if m == "createAccessToken" else {"code": -32700, "message": "Parse error"}
        )
        with self.assertRaises(SoundbarApiError) as ctx:
            await self.client.get_volume()
        self.assertEqual(ctx.exception.code, -32700)


class TestState(ClientTestCase):
    async def test_full_state_when_on(self):
        state = await self.client.get_state()
        self.assertTrue(state.power)
        self.assertEqual(state.volume, 10)
        self.assertFalse(state.muted)
        self.assertEqual(state.source, "E_ARC")
        self.assertEqual(state.sound_mode, "ADAPTIVE")
        self.assertEqual(state.codec, "MAT_PCM")

    async def test_only_power_is_read_when_off(self):
        self.fake.power = False
        state = await self.client.get_state()
        self.assertFalse(state.power)
        self.assertIsNone(state.volume)
        self.assertNotIn("getVolume", self.fake.calls)

    async def test_requests_are_serialized(self):
        await asyncio.gather(*(self.client.get_state() for _ in range(5)))
        self.assertEqual(self.fake.max_in_flight, 1)

    async def test_info_combines_upnp_and_identifier(self):
        info = await self.client.get_info()
        self.assertEqual(info.model, "HW-Q990D")
        self.assertEqual(info.name, "Q990D")
        self.assertEqual(info.serial_number, "SERIAL123")
        self.assertEqual(info.udn, "00000000-aaaa-bbbb-cccc-dddddddddddd")
        self.assertEqual(info.identifier, "22_AV_HW-Q990D")


class TestVolume(ClientTestCase):
    async def test_set_volume_is_one_request(self):
        await self.client.set_volume(85)
        self.assertEqual(self.fake.volume, 85)
        self.assertNotIn("remoteKeyControl", self.fake.calls)

    async def test_rejected_value_raises(self):
        with self.assertRaises(ValueError):
            await self.client.set_volume(101)
        self.fake.volume_control = True
        self.fake.volume = 10
        with self.assertRaises(SoundbarApiError):
            await self.client._set("volumeControl", volume=150)


class TestVolumeFallback(ClientTestCase):
    fake_kwargs = {"volume_control": False}

    async def test_steps_when_volume_control_is_missing_and_remembers(self):
        await self.client.set_volume(13)
        self.assertEqual(self.fake.volume, 13)
        self.assertEqual(self.fake.calls.count("remoteKeyControl"), 3)
        await self.client.set_volume(11)
        self.assertEqual(self.fake.volume, 11)
        self.assertEqual(self.fake.calls.count("volumeControl"), 1)


class TestMute(ClientTestCase):
    async def test_set_mute_directly(self):
        await self.client.set_muted(True)
        self.assertTrue(self.fake.muted)
        await self.client.set_muted(True)
        self.assertTrue(self.fake.muted)
        self.assertNotIn("remoteKeyControl", self.fake.calls)


class TestMuteFallback(ClientTestCase):
    fake_kwargs = {"mute_control": False}

    async def test_toggle_only_when_state_differs(self):
        await self.client.set_muted(False)
        self.assertFalse(self.fake.muted)
        self.assertNotIn("remoteKeyControl", self.fake.calls)
        await self.client.set_muted(True)
        self.assertTrue(self.fake.muted)
        await self.client.set_muted(True)
        self.assertTrue(self.fake.muted)


class TestConnection(unittest.IsolatedAsyncioTestCase):
    async def test_unreachable_soundbar_raises_connection_error(self):
        async with aiohttp.ClientSession() as session:
            client = SoundbarClient("127.0.0.1", session, port=1, timeout=1)
            client._url = "http://127.0.0.1:1/"
            with self.assertRaises(SoundbarConnectionError):
                await client.get_volume()


class TestUpnpParsing(unittest.TestCase):
    def test_missing_fields_are_none(self):
        info = parse_upnp_description('<root xmlns="urn:x"><device><modelName>HW-S60D</modelName></device></root>')
        self.assertEqual(info.model, "HW-S60D")
        self.assertIsNone(info.udn)


if __name__ == "__main__":
    unittest.main()
