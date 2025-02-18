import re, serial, logging
from datetime import datetime
from time import sleep, time
import numpy as np
from pyqtgraph.Qt import QtCore
from TubeFurnaceController import GenericSerialDevice

class MFCControl():
    ''' Object that holds serial connection to MFC controller and communicates with it'''

    gas_ids = {
    'N2': 'A',
    'Ar': 'B',
    'O2': 'C',
    'FG': 'D',
    'H2S': 'E',
    'H2Se': 'F'
    }


    def __init__(self, logger, testing = False):

        self.connection = GenericSerialDevice(com_port=3, baudrate=19200, testing=testing, name='MFC Controller')
        self.logger = logger
        self.testing = testing


    def get_data(self,gas_id_letter) -> dict:
        if self.testing:
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
        
    @staticmethod
    def _process_mfc_response(response: str) -> dict:  # TODO confirm this works
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
        self.connection.ask(f'{gas_id_letter}S{sccm_value}')
        self.logger.debug(f'Setting {gas_id_str} to {sccm_value} sccm')

    def stop_all_gas_flows(self):
        for gas_name, gas_id_letter in self.gas_ids.items():
            self.set_sccm(gas_name, 0)
        self.logger.debug(f'Setting all gas flows to 0')


class PressureGauge():
    ''' Object that holds serial connection to pressure gauge and returns measured value'''

    def __init__(self, logger,testing = False):

        self.logger = logger
        self.testing = testing
        self.running = False

        self.connection = GenericSerialDevice(com_port = 6, testing = testing, name = 'Pressure Gauge')
    def getPressure(self):
        if self.testing:
            self.logger.info(f' testing: get Pressure\n')
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
    '''Object that holds serial connection to furnace and sends it messages '''

    def __init__(self,logger, testing = False):

        self.logger = logger
        self.testing = testing
        self.connection = GenericSerialDevice(com_port=4, parity=serial.PARITY_EVEN, testing=testing,
                                                          name='Temperature Controller')

    def getAllTemperatures(self):
        if self.testing:
            self.logger.info('testing: get All temps \n')
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
                    self.logger.info(f'Setting zone {zone_number} setpoint {i} to {setpoint}...{response}')
                    command = f'\x020{zone_number}010WWRD0{register+1},01,{time:04X}\x03\r'
                    response = self.connection.ask(command)
                    self.logger.info(f'Setting zone {zone_number} segment time {i} to {time}...{response}')
                register = register + 2
                i += 1

    def changeMode(self, mode: float):
        for zone_number in (1,2,3):
            command = f'\x020{zone_number}010WWRD0121,01,{mode:04X}\x03\r'
            response = self.connection.ask(command)
            self.logger.info(f'Setting zone {zone_number} to mode {mode}...{response}')

    def startFurnace(self):
        self.changeMode(1)
    def stopFurance(self):
        self.changeMode(0)

