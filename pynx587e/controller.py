# Standard library imports
import queue
import time
from threading import Thread

# Related third party imports.
import serial

# Local application imports
from pynx587e.serialreader import Serialreader
from pynx587e.flexdevice import FlexDevice

ZONE_ELEMENTS = [
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

PARTITION_ELEMENTS = [
    'ready',
    'armed',
    'stay',
    'chime',
    'entryDelay',
    'exitPeriod',
    'previousAlarm',
    'siren'
    ]

NX_MESSAGE_TYPES={
    "ZN":ZONE_ELEMENTS,
    "PA":PARTITION_ELEMENTS
}   

NX_MAX_DEVICES={
    "ZN":48,
    "PA":2,
}

class nx857e:
    
    def __init__(self, port, max_zone, cb):
        # TODO: PEP8 review
        self._port = port
        self._max_zone = max_zone
        self.callbackf = cb
        START_UP_OPTIONS='taliPZn'
        self._run_flag = True

        # Quues for thread communication
        self._command_q = queue.Queue(maxsize=0)
        self._raw_event_q = queue.Queue(maxsize=0)
        self._consumer_q = queue.Queue(maxsize=0)
        

        # Create deviceBank from NX_MAX_DEVICIES definition to represent
        # the defined number of devices (e.g. Zones and Partitions)
        self.deviceBank = {}
        for device, max_item in NX_MAX_DEVICES.items():
            self.deviceBank[device] = []
            i = 0
            while i < max_item:
                self.deviceBank[device].append(FlexDevice(NX_MESSAGE_TYPES[device]))
                i = i+1

        ## Delete below
        #self.zoneBank = []

        # Zone state array
        #i = 0
        #while i < self._max_zone:
        #    zone = FlexDevice(ZONE_ELEMENTS)
        #    self.zoneBank.append(zone)
        #    i = i+1

        # Delete above

        # NOTE: Thread creation happens in _control
        self._control()
        self.configure_nx587e(START_UP_OPTIONS)


    def configure_nx587e(self, options):
        """
        Add NX587E configuration options to the command queue
        for execution. Typically called during NX587E instantiation 
        """

        try:
            self._command_q.put_nowait(options)
        except serial.SerialException as e:
            print(e)
        # FIXME: Give some time for the _serial_writer thread to process
        time.sleep(0.25)
    

    def _processEvent(self,raw_event):
        for key_nxMsgtypes in NX_MESSAGE_TYPES:
        #for key_nxMsgtypes, value_nxMsgtypes in NX_MESSAGE_TYPES.items():
            if raw_event[0:2] == key_nxMsgtypes:
                # ID
                if raw_event[2:5].isnumeric():
                    # 3 digit ID
                    string_id = raw_event[2:5]
                    id = int(string_id)
                    start_char = 5
                elif raw_event[2:3].isnumeric():
                    # 2 digit ID
                    string_id = raw_event[2:3]
                    id = int(string_id)
                    start_char = 3

                #Construct a dictionary to represent the msg
                NXMessage = {}
                for i, v in enumerate(raw_event[start_char:len(raw_event)-1]):
                    NXMessage[NX_MESSAGE_TYPES[key_nxMsgtypes][i]] = v.isupper()
                
                # Iterate through the NXMessage items (current message)
                # and compare each item value with that of previous message in
                # zoneBank that maintains state.

                # Message ID is within defined range
                if id <= NX_MAX_DEVICES[key_nxMsgtypes]:
                    for msg_key, msg_value in NXMessage.items():
                        if self.deviceBank[key_nxMsgtypes][id-1].get(msg_key) != msg_value:
                            self.deviceBank[key_nxMsgtypes][id-1].set(msg_key, msg_value)
                            event = {"event":key_nxMsgtypes,
                                    "id":id,
                                    "tag":msg_key,
                                    "value":msg_value,
                                    "time": self.deviceBank[key_nxMsgtypes][id-1].get(str(msg_key+'_time'))
                                    }
                            # call back function
                            self.callbackf(event)
                        else:
                            # Message not supported
                            pass
                else:
                    # Recieved a message with an ID > MAX devices, ignore message
                    pass

    def _serial_writer(self,serial_conn,command_q):
        """
        Consumer thread that reads the command_q queue and writes
        commands to the serial device. Designed to run as a daemonic
        thread
        """
        
        while True:
            try:
                # ensure a blocking mechanism is used to reduce CPU
                # usage i.e do not use get_no_wait()
                command = command_q.get()
            except queue.Empty:
                pass
            else:
                b = bytearray()
                b.extend(command.encode())
                serial_conn.write(b)

    def _serial_reader(self,serial_conn,raw_event_q):
        """
        Producer thread that reads lines from the serial device and
        adds these to the raw_event_q queue.  Designed to run as a 
        daemonic thread
        """
        # seralreader is wrapper for pyserial that provides a 
        # higher-performance readline function
        # DO NOT use read_until or readline from the pyserial 
        serial_reader = Serialreader(serial_conn)

        while True:
            # NX587E outputs an event starting with a line feed and 
            # terminating with a charater break
            try:
                raw_line = serial_reader.readline().decode().strip()
            except serial.SerialException:
                pass
                # manage a hot-unplug here
            else:
                if (raw_line):
                    raw_event_q.put(raw_line)

    def _event_producer(self,serial_conn, raw_event_q, consumer_q):
        while self._run_flag:
            time.sleep(0.01)
            try:
                raw_event = raw_event_q.get_nowait()
            except queue.Empty:
                pass
            else:
                # process the raw event
                self._processEvent(raw_event)
                

    def _control(self):
        try:
            serial_conn = serial.Serial(port=self._port)
        except serial.SerialException as e:
            print(e)
        else:
            # Threads
            serial_writer_thread = Thread(
                target=self._serial_writer,
                args=(serial_conn,
                      self._command_q,
                     ),
                daemon=True
                )

            serial_reader_thread = Thread(
                target=self._serial_reader,
                args=(serial_conn,
                      self._raw_event_q,
                     ),
                daemon=True
                )

            event_producer_thread = Thread(
                target=self._event_producer,
                args=(serial_conn,
                      self._raw_event_q,
                      self._consumer_q,
                     ),
                )

            # Start threads
            serial_writer_thread.start()
            serial_reader_thread.start()
            event_producer_thread.start()
   

    def stop(self):
        self._run_flag = False