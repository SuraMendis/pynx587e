# Standard library imports
from datetime import datetime


class FlexDevice:
    def __init__(self, fd_elements):
        self._flexDeviceState = {}
        # Construct all the key/value elements for a device
        # For element, also create a element_time key/value
        for item in fd_elements:
            item_time = item+'_time'
            self._flexDeviceState[item] = -1
            self._flexDeviceState[item_time] = -1

    def get(self, item):
        return self._flexDeviceState[item]

    def set(self,  item, value):
        item_time = item+'_time'
        self._flexDeviceState[item] = value
        self._flexDeviceState[item_time] = datetime.now()
