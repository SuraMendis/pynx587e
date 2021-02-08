# Define the highest addressable ZN/PN in the alarm system
_NX_DEFAULT_NODES = {
    "ZN": 48,
    "PA": 2,
}


# A Zone Status Message syntax is like: ZN002FttBaillb where:
#  ZN = Zone Identifer
#  002 = The Zone Number/ID
#  FttBaillb = each character relates to the definition
#  (upper case true; else false)
#  in the _ZONE_TOPICS list below (order is important)
_ZONE_TOPICS = [
    'fault',
    'tamper',
    'trouble',
    'bypass',
    'alarmMemory',
    'inhibit',
    'lowBattery',
    'lost',
    'memoryBypass',
]

# A Partition Status Message syntax is like: PA1RasCeEps where:
#  PN = Partition Identifer
#  1 = The Partition Number/ID
#  RasCeEps = each character relates to the definition
#  (upper case true; else false) in the _PARTITION_ELEMENTS list
#  below (order is important)
_PARTITION_TOPICS = [
    'ready',
    'armed',
    'stay',
    'chime',
    'entryDelay',
    'exitPeriod',
    'previousAlarm',
    'siren',
]

# _NX_MESSAGE_TYPES is a dictionary that defines supported
# message types. The key is the message type and the value
# is the previously defined elements (e.g _PARTITION_ELEMENTS)
_NX_EVENT_TYPES = {
    "ZN": _ZONE_TOPICS,
    "PA": _PARTITION_TOPICS,
}

_keymap_au_nz = {
    "partial": "K",  # Sending K does a partial/stay arm
    "chime": "C",
    "exit": "E",
    "bypass": "B",
    "on": "S",  # Sending 'S' quick-arm
    "fire": "F",
    "medical": "M",
    "hold_up": "H",
    "nx_quick_arm": "S",
    "nx_stay": "K",
}

# The NX587E default supported keymap
_keymap_usa = {
    "stay": "S",
    "chime": "C",
    "exit": "E",
    "bypass": "B",
    "cancel": "K",
    "fire": "F",
    "medical": "M",
    "hold_up": "H",
    "nx_quick_arm": "E",
    "nx_stay": "S",
}

# The NX-587E emulates function buttons from the USA version
# of the NX-148E keypad. Hills Reliance NX alarm panels
# (Australian and New Zealand market) respond differently to
# these emulated function buttons.
_supported_keymaps = {
    "AUNZ": _keymap_au_nz,
    "USA": _keymap_usa
}

# Configuration string for NX-587E, used on start up
_setup_options = 'taliPZn'
