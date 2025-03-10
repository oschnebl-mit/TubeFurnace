import re, serial, logging
from datetime import datetime
from time import sleep, time
import numpy as np
from pyqtgraph.Qt import QtCore


class GenericSerialDevice:
    def __init__(self, logger, com_port=0, baudrate=9600, timeout=0.1, parity=serial.PARITY_NONE, bytesize=serial.EIGHTBITS,
                 testing=False, name='serial device'):
        self.testing = testing
        self.max_number_of_attempts_per_read = 5
        self.min_ms_between_successive_reads = 50
        self.com_lock = QtCore.QMutex()
        self.com_port = com_port
        self.serial_baudrate = baudrate
        self.serial_timeout = timeout
        self.serial_parity = parity
        self.serial_bytesize = bytesize
        self.name = name
        self.logger = logger

        self._serial_connection = self._generate_serial_connection()
        if not self.connection_is_open():
            self.open_connection()

    def __del__(self):
        self.close_connection()

    def _generate_serial_connection(self):
        if self.testing:
            return None

        return serial.Serial(
            port=f'COM{self.com_port}',
            baudrate=self.serial_baudrate,
            timeout=self.serial_timeout,
            parity=self.serial_parity,
            bytesize=self.serial_bytesize
        )

    def connection_is_open(self):
        if self.testing:
            return False

        return self._serial_connection.is_open

    def open_connection(self):
        if self.testing:
            return

        self._serial_connection.open()

    def close_connection(self):
        if self.testing:
            return

        self._serial_connection.close()

    def write(self, message_str: str):
        if not message_str.endswith('\r'):
            message_str = message_str + '\r'

        if self.testing:
            self.logger.debug(f'would write {message_str}')
        else:
            self._serial_connection.write(bytes(message_str, 'ascii'))
            self.logger.debug(f'wrote {message_str} to {self.name}')


    def read(self, accept_empty_response=False) -> str:
        if self.testing:
            return ''

        for i in range(self.max_number_of_attempts_per_read):
            sleep(self.min_ms_between_successive_reads / 1000)
            response = self._serial_connection.readline()

            try:
                str_response = response.decode()
                self.logger.debug(f'received response: {str_response} from {self.name}')
                if accept_empty_response or (str_response != ""):
                    return str_response  # successful read, so exit for-loop

            except Exception as ex:
                self.logger.warning(f'Read attempt {i + 1}: failed to decode response of "{response}" from {self.name}')
                self.logger.exception(ex)

        self.logger.warning(f'{self.name} failed to perform read after {self.max_number_of_attempts_per_read} tries')
        return ""

    def ask(self, message, accept_empty_response=False):
        with self.com_lock: ## note the com_lock (mutex)!
            self.write(message)
            return self.read(accept_empty_response)


class MFCControl():
    ''' Object that holds serial connection to MFC controller and communicates with it'''

    mutex = QtCore.QMutex()
    
    gas_ids = {
    'N2': 'A',
    'Ar': 'B',
    'O2': 'C',
    'FG': 'D',
    'H2S': 'E',
    'H2Se': 'F'
    }
    # new_Ar_data = QtCore.pyqtSignal(object)
    # new_H2S_data = QtCore.pyqtSignal(object)

    def __init__(self, logger, delay = 30, testing = False):
        self.connection = GenericSerialDevice(logger, com_port=3, baudrate=19200, testing=testing, name='MFC Controller')
        self.logger = logger
        self.testing = testing
        self.delay = delay

    def get_data(self,gas_id_letter) -> dict:
        if self.testing:
            ## just for testing allow Ar and H2S to display separately on plot
            if gas_id_letter == self.gas_ids['Ar']:
                return{
                    key: -2 for key in ['ID', 'PSIA', 'flow_temp', 'vol_flow_ccm', 'sccm', 'sccm_setpoint', 'gas_name']
                }
            else:
                return {
                    key: -1
                    for key in ['ID', 'PSIA', 'flow_temp', 'vol_flow_ccm', 'sccm', 'sccm_setpoint', 'gas_name']
                }

        else:
            response = self.connection.ask(f'{gas_id_letter}')
            return self._process_mfc_response(response)

        
    # @staticmethod
    def _process_mfc_response(self,response: str) -> dict:  # TODO confirm this works
        numeric_cols = ['PSIA', 'flow_temp', 'vol_flow_ccm', 'sccm', 'sccm_setpoint']
        all_cols = ['ID', 'PSIA', 'flow_temp', 'vol_flow_ccm', 'sccm', 'sccm_setpoint', 'gas_name']
        received_values = response.split()
        if len(received_values) < len(all_cols):  # want to preserve same output dict structure if read fails
            self.logger.warning(f'Received unexpected mfc response: {response}. Treating as NaNs')
            return {key: np.nan for key in all_cols}

        return {
            key: (float(value) if key in numeric_cols else value)
            for key, value in zip(
                all_cols,
                received_values
            )
        }
    
    def set_sccm(self, gas_id_str, sccm_value):
        ## gas id str is 'H2S', 'Ar', or other plumbed gas, sccm_value is flow rate
        gas_id_letter = self.gas_ids[gas_id_str]
        response = self.connection.ask(f'{gas_id_letter}S{sccm_value}')
        self.logger.debug(f'Setting {gas_id_str} to {sccm_value} sccm... received {response}')

    def stop_all_gas_flows(self):
        self.logger.info(f'Setting all gas flows to 0')
        for gas_name, gas_id_letter in self.gas_ids.items():
            self.set_sccm(gas_name, 0)
            # sleep(1)



class PressureGauge():
    def __init__(self,logger, delay = 30, testing = False):
        # super().__init__()
        self.logger = logger
        self.delay = delay
        self.testing = testing
        self.running = False
        self.connection = GenericSerialDevice(logger, com_port = 6, testing = testing, name = 'Pressure Gauge')


    def getPressure(self):
        if self.testing:
            self.logger.debug(f' testing: get Pressure\n')
            return 100.0
        else:
            try:
                response = self.connection.ask('p')
                return float(''.join(response.split()[:-1]))
            except Exception as ex:
                self.logger.warning(f'Exception occurred when reading gauge pressure')
                self.exception(ex)
                return -1
            
class FurnaceControl():

    def __init__(self,logger,delay = 30, testing = False):
        # super().__init__()
        self.logger = logger
        self.delay = delay
        self.testing = testing
        self.running = False

        self.connection = GenericSerialDevice(logger, com_port=4, parity=serial.PARITY_EVEN, testing=testing,
                                                          name='Temperature Controller')

    def getAllTemperatures(self):
        if self.testing:
            self.logger.debug('testing: get All temps \n')
            return list([20,25,23])
        else:
            data = []
            for zone_number in (1,2,3):
                response = self.connection.ask(f'\x020{zone_number}010WRDD0002,01\x03')
                data.append(int(response.split('OK')[1][0:4],16))
            return data


    def programFurnace(self,*args):
        ## args should be tuples (setpoint, segment time)
        if len(args) > 16:
            self.logger.exception(f'Too many segments')
            return -1
        else:
            register = 229
            i = 1
            for (setpoint,time) in args[0]:
                # print(setpoint,time)
                for zone_number in (1,2,3):
                    command = f'\x020{zone_number}010WWRD0{register},01,{setpoint:04X}\x03\r'
                    response = self.connection.ask(command)
                    self.logger.debug(f'Setting zone {zone_number} setpoint {i} to {setpoint}...{response}')
                    command = f'\x020{zone_number}010WWRD0{register+1},01,{time:04X}\x03\r'
                    response = self.connection.ask(command)
                    self.logger.debug(f'Setting zone {zone_number} segment time {i} to {time}...{response}')
                register = register + 2
                i += 1

    def changeMode(self, mode: float):
        for zone_number in (1,2,3):
            command = f'\x020{zone_number}010WWRD0121,01,{mode:04X}\x03\r'
            response = self.connection.ask(command)
            self.logger.debug(f'Setting zone {zone_number} to mode {mode}...{response}')

    def startFurnace(self):
        self.changeMode(1)
    def stopFurance(self):
        self.changeMode(0)

