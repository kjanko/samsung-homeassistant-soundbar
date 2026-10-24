"""Constants for the Samsung Soundbar (IP control) integration."""

DOMAIN = "samsung_soundbar_ip"

PLATFORMS = ["button", "media_player", "sensor"]

CONF_SCAN_INTERVAL = "scan_interval"
# Sound mode codes this soundbar has refused; kept in the entry so they stay hidden
CONF_UNSUPPORTED_SOUND_MODES = "unsupported_sound_modes"
DEFAULT_SCAN_INTERVAL = 3  # seconds; one poll is ~6 requests of ~50 ms
MIN_SCAN_INTERVAL = 1
MAX_SCAN_INTERVAL = 60

# A single missed poll is common on Wi-Fi; only go unavailable after this many
FAILURES_BEFORE_UNAVAILABLE = 3

# API input codes -> names shown in Home Assistant
SOURCES = {
    "E_ARC": "eARC",
    "ARC": "ARC",
    "HDMI_IN1": "HDMI 1",
    "HDMI_IN2": "HDMI 2",
    "D_IN": "Optical",
    "BT": "Bluetooth",
    "WIFI_IDLE": "Wi-Fi",
}

# API sound mode codes -> names shown in Home Assistant
SOUND_MODES = {
    "ADAPTIVE": "Adaptive",
    "STANDARD": "Standard",
    "SURROUND": "Surround",
    "GAME": "Game",
    "MOVIE": "Movie",
    "MUSIC": "Music",
    "CLEARVOICE": "Clear voice",
    "DTS_VIRTUAL_X": "DTS Virtual:X",
}
