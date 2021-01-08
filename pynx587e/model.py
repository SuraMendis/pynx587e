# A Zone Status Message syntax is like: ZN002FttBaillb where:
#  ZN = Zone Identifer
#  002 = The Zone Number/ID
#  FttBaillb = each character relates to the definition
#  (upper case true; else false)
#  in the _ZONE_ELEMENTS list below (order is important)
_ZONE_ELEMENTS = [
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
#  (upper case true; else false) in the _ZONE_ELEMENTS list
#  below (order is important)
_PARTITION_ELEMENTS = [
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
_NX_MESSAGE_TYPES={
    "ZN":_ZONE_ELEMENTS,
    "PA":_PARTITION_ELEMENTS,
}   

_keymap_au_nz = {
    "partial":"K", # Sending K does a partial/stay arm
    "chime":"C",
    "exit":"E",
    "bypass":"B",
    "on":"S", # Sending 'S' quick-arm 
    "fire":"F",
    "medical":"M",
    "hold_up":"H",
}
        
# The NX587E default supported keymap
_keymap_usa = {
    "stay":"S",
    "chime":"C",
    "exit":"E",
    "bypass":"B",
    "cancel":"K",
    "fire":"F",
    "medical":"M",
    "hold_up":"H",
}

_supported_keymaps = {
    "AUNZ":_keymap_au_nz,
    "USA":_keymap_usa
}