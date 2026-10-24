# Samsung Soundbar (IP control) — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A custom Home Assistant integration for Samsung soundbars. It talks to the soundbar directly over your local network using the soundbar's IP control API, so it works without the internet or a SmartThings account.

Tested with the HW-Q990D. It should also work with other recent Samsung soundbars that have the IP control setting, such as the HW-Q930D, HW-Q800D, HW-S800D and HW-S60D.

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
3. Home Assistant discovers the soundbar automatically and offers it under **Settings → Devices & services**. You can also add it yourself with **Add integration → Samsung Soundbar (IP control)** and its IP address.

## Features

### Media player

| Feature | Details |
|---|---|
| Power | Turn on and off |
| Volume | Set any level from 0 to 100%, or step up and down by 1 |
| Mute | Mute and unmute |
| Input | eARC, ARC, HDMI 1, HDMI 2, Optical, Bluetooth, Wi-Fi |
| Sound mode | Adaptive, Standard, Surround, Game, Movie, Music, Clear voice, DTS Virtual:X |

Volume, mute, input and sound mode changes appear in Home Assistant as soon as the command is sent. Changes made with the soundbar's remote, its buttons or through the TV appear at the next poll.

### Sensor

**Audio format**: the format of the incoming audio as the soundbar reports it, for example `MAT_PCM` for Dolby Atmos over eARC.

### Buttons

**Woofer up** and **Woofer down** raise or lower the subwoofer level by one step.

### Device

The soundbar is added as one device with its model, model ID and serial number. Discovery recognises it by its UPnP ID, so if it gets a new IP address Home Assistant updates the address by itself.

## Configuration

**Configure** on the integration lets you set the poll interval: how often Home Assistant reads the soundbar's state (1–60 s, default 3 s). One poll takes about 0.15 s.

**Reconfigure** lets you change the IP address by hand.

## Behaviour

- When the soundbar is off, the media player shows **off**, and volume, input and sound mode are empty until it's turned on.
- If the soundbar doesn't answer, the entities keep their last state for two polls and become **unavailable** from the third.
- The soundbar issues access tokens for its API and discards old ones when other apps request new ones. The integration requests a new token whenever its own is discarded.
- On models without the direct volume and mute commands, the integration uses the remote control's volume and mute keys instead.

## Limitations

- Night mode, voice enhancement, bass boost and sound grouping aren't part of the soundbar's local API, so this integration can't control them.
- The woofer level can be changed but not read.

## Troubleshooting

- **Can't connect:** check that IP control is on in the SmartThings app and that Home Assistant can reach the soundbar's IP address. The API listens on port 1516.
- **Diagnostics:** Settings → Devices & services → Samsung Soundbar (IP control) → ⋮ → **Download diagnostics**.

## Development

```bash
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python pytest-homeassistant-custom-component
.venv/bin/python -m pytest
```
