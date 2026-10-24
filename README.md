# Samsung Soundbar (IP control) — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Local control of Samsung soundbars (2022+ models such as the HW-Q990D) through the soundbar's own IP control API. No cloud, no SmartThings account.

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kjanko&repository=samsung-homeassistant-soundbar&category=integration)

1. Open HACS in Home Assistant
2. Click the three dots in the top right → **Custom repositories**
3. Add `https://github.com/kjanko/samsung-homeassistant-soundbar` with category **Integration**
4. Search for "Samsung Soundbar (IP control)" and install it
5. Restart Home Assistant

### Manual

Copy the `custom_components/samsung_soundbar_ip` folder into your Home Assistant config directory:

```
<ha-config>/custom_components/samsung_soundbar_ip/
```

Restart Home Assistant.

## Setup

1. Turn on IP control: SmartThings app → your soundbar → ⋮ → **Settings** → **IP control**.
2. Give the soundbar a fixed IP address (DHCP reservation) in your router.
3. Home Assistant discovers the soundbar on its own and shows it under **Settings → Devices & services**. To add it by hand, use **Add integration → Samsung Soundbar (IP control)** and enter its IP address.

## Features

| Entity | What it does |
|---|---|
| Media player | Power, volume, mute, input and sound mode |
| Audio format sensor | Incoming format as the soundbar reports it, e.g. `MAT_PCM` (Dolby Atmos over eARC) |
| Woofer up / down buttons | Step the subwoofer level (the API can't read the level back) |

- **Instant volume.** Volume is set in one request (~80 ms) instead of one key press per step, and Home Assistant shows the new level immediately.
- **Mute sets, never toggles,** so it can't end up inverted.
- **Off is off.** When the soundbar is off, only its power state is read and the entity shows *off*, not *unavailable*.
- **Rides out Wi-Fi blips.** Up to two missed polls keep the last state; the entity goes unavailable only after the third.
- **Recovers by itself.** The soundbar keeps only a few access tokens and silently drops old ones; the integration renews its token and retries.
- **Follows IP changes.** The soundbar is identified by its UPnP ID, so discovery updates its address if it changes.
- **Adjustable poll interval** (1–60 s, default 3 s) under **Configure**. One poll takes about 0.15 s.
- Diagnostics download, and **Reconfigure** to change the IP by hand.

Older models without the `volumeControl` or `muteControl` methods fall back to key presses automatically.

## Not available locally

Night mode, voice enhancement, bass boost and sound grouping aren't part of the soundbar's local API. They can only be changed through the SmartThings cloud.

## Development

```bash
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python pytest-homeassistant-custom-component
.venv/bin/python -m pytest
```
