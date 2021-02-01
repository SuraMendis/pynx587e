# Standard library imports
import queue
import time
from threading import Thread

# Related third party imports.
import serial

# Application imports
import model
import serialreader
import flexdevice


class NXSystemError(Exception):
    '''Basic Exception for errors raised with NXSystem'''


class KeyMapError(NXSystemError):
    ''' Keymap should be US or AUNZ '''


class GetStatusError(NXSystemError):
    ''' Invalid query or device ID '''


class ConnectionError(NXSystemError):
    ''' Connection already established '''


class NXController:
    ''' Automation interface for NX-series alarm systems using the NX-587E
    virtual keypad module.

    :param port: Serial port (COM1 /dev/ttyUSB0 or similar)
    :type port: string

    :param keymap: USA or AUNZ (Australian / NZ systems should use AUNZ)
    :type keympa: string

    :raises pynx587e.nx587e.KeyMapError: keymap must be USA or AUNZ
    '''
    def __init__(self, port, keymap):
        self._port = port

        # Refer to model._supported_keymaps comments for purpose
        if keymap in model._supported_keymaps:
            self._keymap = keymap
        else:
            raise KeyMapError("Unsupported keymap")

        # Instance variables
        self._run_threads = False
        self._connection_requested = False
        self._last_config_time = 0

    def connect(self):
        '''
        Connect to the NX-587E device
        '''
        if self._run_threads is False:
            # Start the Serial Connection Manager thread
            self._connection_requested = True
            connection_mgr_thread = Thread(target=self._connection_manager,
                                           daemon=True)
            connection_mgr_thread.start()
        else:
            raise ConnectionError("Active connection already exists")

    def disconnect(self):
        '''
        Disconnect from the NX-587E device
        '''
        if self._run_threads:
            self._connection_requested = False
            self._stop_threads()
            self.serial_conn.close()
        else:
            raise ConnectionError("Not connected")

    def _decode_event(self, raw_event):
        '''
        Return a dictionary representation of raw_event

        :param raw_event: A transition status message from the NX-587E
        :type raw_event: string
        '''
        NXEvent = None
        # First two characters of raw_event indicate message type
        # Compare message type against supported types contained
        # in NX_MESSAGE_TYPES
        key_nxMsgtypes = raw_event[0:2]
        if key_nxMsgtypes in model._NX_MESSAGE_TYPES:
            # ID is one or more consecutive digits following the
            # two-character message type.
            id_start_char = 2
            status_position = id_start_char
            num_char = id_start_char + 1
            while raw_event[2:num_char].isnumeric():
                id = int(raw_event[2:num_char])
                num_char += 1
                # ID can be one or more digits in length, advance the
                # status_position indicator
                status_position += 1

            # NXStatus list represents the characters contained in raw_event
            # positioned after the id.
            # UPPER CASE characters represent 'TRUE',
            # lower case characters represent 'False'.
            NXStatus = {}
            for i, v in enumerate(
                    raw_event[status_position:len(raw_event)]
                    ):
                NXStatus[
                    model._NX_MESSAGE_TYPES[
                        key_nxMsgtypes][i]] = v.isupper()

            NXEvent = {'event': key_nxMsgtypes, 'id': id, "status": NXStatus}

        return NXEvent

    def _update_state(self, event):
        ''' Update the individual element state with those contained in
        'event' trigger the callback self.on_event

        .. note: If the existing element value is -1 then this
        is the first update to the element and the callback function
        is skipped.

        :param event: An NXEvent object
        :type NXEvent
        '''
        event_type = event.get('event')
        id = event.get('id')
        status_list = event.get('status')

        if id <= model._NX_MAX_DEVICES[event_type]:
            # id is within range
            for msg_key, msg_value in status_list.items():
                # Get the tracked element value
                previous_element_value = self.deviceBank[
                    event_type][id-1].get(msg_key)
                # An event has changed state if the current value
                # does not equal the prevenous value
                skip_callback = False
                if previous_element_value != msg_value:
                    # -1 indicates an update has yet to occur.
                    # This is the first update, to be trigged by this
                    # class to establish state.
                    if previous_element_value == -1:
                        # skip the callback function to whilst the state is
                        # being established.
                        skip_callback = True
                    else:
                        pass

                    # Update element status
                    self.deviceBank[
                        event_type][id-1].set(msg_key, msg_value)

                    # Construct an event dictionary to
                    # represent the latest element state
                    event = {"event": event_type,
                             "id": id,
                             "tag": msg_key,
                             "value": msg_value,
                             "time": self.deviceBank[
                                    event_type][
                                        id-1].get(str(msg_key+'_time')),
                             }
                    # Execute the callback function with the
                    # latest event state that changed.
                    if skip_callback is False:
                        if self.on_event is not None:
                            self.on_event(event)
                else:
                    # Message type not supported
                    pass
        else:
            # Received a message with an ID > MAX devices,
            # ignore message
            pass

    def getStatus(self, query_type, id, element):
        ''' Returns state and time for 'element' in
        'query_type' as a List

        :param query_type: Query type as defined in _NX_MESSAGE_TYPES
        :type query_type: string

        :param id: ID relating to the query type.
        :type id: int

        .. note:: Supported elements are defined in _NX_MESSAGE_TYPES
           For example: getStatus('ZN',1,fault) could return
           [true,2021-01-05 16:00:29.689725] which means:
            - status of Zone 1's fault (tripped) is TRUE;
            - and the associated event time.

        :return: List [element, element_time] for invalid requests
        :rtype: List
        '''
        if self._run_threads:
            # Check if the query_type is valid as defined in
            # _NX_MESSAGE_TYPES
            if query_type in model._NX_MESSAGE_TYPES:
                # Check if the id is valid as defined in _NX_MAX_DEVICES
                if id <= model._NX_MAX_DEVICES[query_type]:
                    cached_attribute = self.deviceBank[
                        query_type][id-1].get(element)
                    cached_attribute_time = self.deviceBank[
                        query_type][id-1].get(element+'_time')
                    status = [cached_attribute, cached_attribute_time]
                else:
                    raise GetStatusError("ID out of range")

            else:
                raise GetStatusError("Invalid query type")
        else:
            raise ConnectionError("Not connected")

        return status

    def _direct_query(self, query_type, id):
        '''Directly query the Zone or Partition status from the
        NX-587E. Results are processed by _event_process.

        :param query_type: Query type as defined in _MX_MESSAGE_TYPES
        :type query_type: string

        :raises serial.SerialException: If serial port error occurs

        .. note:: _direct_query is for internal use module use. Users of
        pyNX587E should use getStatus rather than _direct_query.
        '''
        # Check if the query_type is valid as defined in
        # _NX_MESSAGE_TYPES
        if query_type in model._NX_MESSAGE_TYPES:
            # Check if the id is valid as defined in _NX_MAX_DEVICES
            if id <= model._NX_MAX_DEVICES[query_type]:
                # Construct a query based on the NX-587E Specification
                # Q001 to Q192 is for Zone Queries (Zone 1-192)
                # Q193 to Q200 is for Partition  Queries (1-9)
                if query_type == "PA":
                    query = "Q"+str(192+id)
                elif query_type == "ZN":
                    query = "Q"+str(id).zfill(3)
                # Put the query into the _command_q
                # which will be processed by the serial writer thread
                try:
                    self._command_q.put_nowait(query)
                except serial.SerialException as e:
                    print(e)
                    self._stop_threads()

    def send(self, in_command):
        ''''Sends an alarm panel command or user code via the NX-587E
        interface.

        :param in_command: An NX-148E function command or user code
        :type in_command: string

        :raises serial.SerialException: If serial port error occurs

        .. note::
           AU/NZ installations support the following commands
           partial, chime, exit, bypass, on, fire, medical, hold_up,
           or a 4 or 6 digit user code

        .. note::
           Non-AU/NZ installations support the following commands
           stay, chime, exit, bypass, cancel, fire, medical, hold_up,
           or a 4 or 6 digit user code.
        '''

        # Set supported_commands
        if self._keymap in model._supported_keymaps:
            supported_commands = model._supported_keymaps[self._keymap]
        # A 4 or 6 digit code is also a valid input
        # This typically arms/disarms the panel
        if in_command.isnumeric() and (
                len(in_command) == 4 or len(in_command == 6)):
            command = in_command
        # or check if it is a function command in the keymap
        elif in_command in supported_commands:
            command = supported_commands[in_command]
        # or check if it is the nd587_setup command
        elif in_command == "nx587_setup":
            command = model._setup_options
            self._last_config_time = time.time()

        # Send the command to the _command_q Queue
        if command != "":
            try:
                self._command_q.put_nowait(command)
            except serial.SerialException as e:
                print(e)
                self._stop_threads()

    def _serial_writer(self, serial_conn, command_q):
        ''' Reads command from queue and writes to the serial port.

        :param serial_conn: An instance of serial.Serial from
        pySerial.
        :type serial_conn: serial.Serial

        :param command_q: Queue to read commands from
        :type command_q: Queue

        .. note:: Designed to run as a daemonic thread
        '''
        while self._run_threads:
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

    def _serial_reader(self, serial_conn, raw_event_q):
        ''' Reads message from serial port and writes it to a Queue
        for further processing.

        :param serial_conn: An instance of serial.Serial from
        pySerial.
        :type serial_conn: serial.Serial

        :param raw_event_q: Queue to write serial message to
        :type command_q: Queue

        .. note:: Designed to run as a daemonic thread
        '''
        # seralreader is wrapper for pyserial that provides a
        # higher-performance readline function
        # DO NOT use read_until or readline from the pyserial
        serial_reader = serialreader.Serialreader(serial_conn)

        while self._run_threads:
            # NX-587E outputs an event starting with a line feed and
            # terminating with a charater break
            try:
                raw_line = serial_reader.readline().decode().strip()
            except Exception:
                # manage a hot-unplug of serial port
                # e.g. USB converter removed
                self._stop_threads()
            else:
                if (raw_line):
                    raw_event_q.put(raw_line)

    def _event_producer(self, serial_conn, raw_event_q):
        ''' Reads message from raw_event_q and sends message for decoding.

        :param serial_conn: An instance of serial.Serial from
         pySerial.
        :type serial_conn: serial.Serial

        :param raw_event_q: Queue to read messages from.
        :type command_q: Queue

        '''
        while self._run_threads:
            time.sleep(0.01)
            try:
                raw_event = raw_event_q.get_nowait()
            except queue.Empty:
                pass
            else:
                # convert the raw event to NXEvent object
                event = self._decode_event(raw_event)
                # update event state, event == None means unknown msg
                if(event is not None):
                    self._update_state(event)

    def _connect_and_process(self):
        ''' Establish a connection to the NX-587E, create
        consumer and producer threads to handle messages and commands
        '''
        try:
            self.serial_conn = serial.Serial(baudrate=9600, port=self._port)
        except serial.SerialException as e:
            print(e)
            self._stop_threads()
        else:
            # Queues for outbound commands and inbound events
            self._command_q = queue.Queue(maxsize=0)
            self._raw_event_q = queue.Queue(maxsize=0)

            # Queue up command to set NX-587 reporting options
            self.send("nx587_setup")

            # Create deviceBank from NX_MAX_DEVICES definition to represent
            # the defined number of devices (e.g. Zones and Partitions)
            self.deviceBank = {}
            for device, max_item in model._NX_MAX_DEVICES.items():
                self.deviceBank[device] = []
                i = 0
                while i < max_item:
                    self.deviceBank[device].append(
                        flexdevice.FlexDevice(model._NX_MESSAGE_TYPES[device]))
                    self._direct_query(device, i+1)
                    i = i+1

            # Define threads
            serial_writer_thread = Thread(
                target=self._serial_writer,
                args=(self.serial_conn,
                      self._command_q,
                      ),
                daemon=True
                )

            serial_reader_thread = Thread(
                target=self._serial_reader,
                args=(self.serial_conn,
                      self._raw_event_q,
                      ),
                daemon=True
                )

            event_producer_thread = Thread(
                target=self._event_producer,
                args=(self.serial_conn,
                      self._raw_event_q,
                      ),
                )

            # Thread control flag
            self._run_threads = True

            # Start communications threads
            serial_writer_thread.start()
            serial_reader_thread.start()
            event_producer_thread.start()

    def _connection_manager(self):
        '''
        Periodically monitor the serial interface. When the interface is
        available, (re)establish a connection to the NX-587E if a connect()
        has been issued (i.e self._connection_requested is True)
        '''
        while self._connection_requested:
            if (self._last_config_time == 0) or (
                 int(time.time()) > self._last_config_time + 30):

                # print("last config value", self._last_config_time)
                ready_to_connect = self._serial_is_available()
                if ready_to_connect:
                    # (re)establish read/write/process threads
                    # print("port available")
                    self._connect_and_process()
                else:
                    # Serial Interface not available for new connections
                    # Reason 1: Interface physically not available (removed)
                    # Reason 2: Interface already in use
                    #
                    # Send reconfig every 60 seconds regardless of status
                    self.send("nx587_setup")
                    # print("port unavailable")

                    # Slow thread execution
                    time.sleep(30)

    def _stop_threads(self):
        '''
        Stop instance by setting _run_flag to False
        '''
        self._run_threads = False

    def _serial_is_available(self):
        '''
        Periodically test if the serial interface (e.g. USB RS232 adaptor)
        is available.

        :return: True if serial interface is available for use, false otherwise
        :rtype: Boolean
        '''
        ret = False
        test = serial.Serial(baudrate=9600, timeout=0, writeTimeout=0)
        test.port = self._port
        try:
            test.open()
            if test.is_open:
                test.close()
                ret = True
        except serial.serialutil.SerialException:
            pass
        return ret
