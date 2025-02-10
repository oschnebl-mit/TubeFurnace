import re, serial, logging
from datetime import datetime
from time import sleep, time
import numpy as np
from pyqtgraph.Qt import QtCore
from TubeFurnaceController import GenericSerialDeivce

class MFCControl(QtCore.QThread):

    gas_ids = {
    'N2': 'A',
    'Ar': 'B',
    'O2': 'C',
    'FG': 'D',
    'H2S': 'E',
    'H2Se': 'F'
}
    new_Ar_data = QtCore.pyqtSignal(object)
    new_H2S_data = QtCore.pyqtSignal(object)

    def __init__(self, logger, delay = 30, testing = False):
        super().__init__()
        self.connection = GenericSerialDevice(com_port=3, baudrate=19200, testing=testing, name='MFC Controller')
        self.running = False
        self.logger = logger
        self.testing = testing
        self.delay = delay

    def run(self):
        self.running = True
        while self.running:
            ## normal running behavior reads sccm for active gases every [delay] seconds and sends to main
            Ar_sccm = self.get_data(self.gas_ids['Ar'])['sccm']
            H2S_sccm = self.get_data(self.gas_ids['H2S'])['sccm']
            self.new_Ar_data.emit(Ar_sccm)
            self.new_H2S_data.emit(H2S_sccm)
            QtCore.QThread.msleep(self.delay*1000)

            

    def get_data(self,gas_id_letter) -> dict:
        if self.testing:
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
        self.connection.ask(f'{gas_id_letter},S{sccm_value}')
        self.logger.debug(f'Setting {gas_id_str} to {sccm_value} sccm')

    def stop_all_gas_flows(self):
        for gas_name, gas_id_letter in self.gas_ids.items():
            self.set_sccm(gas_name, 0)


class PressureGauge(QtCore.QThread):
    new_pressure_data = QtCore.pyqtSignal(object)

    def __init__(self,logger, delay = 30, testing = False):
        super().__init__()
        self.logger = logger
        self.delay = delay
        self.testing = testing
        self.running = False

        self.connection = GenericSerialDeivce(com_port = 6, testing = testing, name = 'Pressure Gauge')

    def run(self):
        self.running = True
        while self.running:
            measured_pressure = self.getPressure()
            self.new_pressure_data.emit(measured_pressure)
            QtCore.QThread.msleep(self.delay*1e3)

    def getPressure(self):
        if self.testing:
            return 100.0
        else:
            try:
                response = self.connection.ask('p')
                return float(''.join(response.split()[:-1]))
            except Exception as ex:
                self.logger.warning(f'Exception occurred when reading gauge pressure')
                self.exception(ex)
                return -1
            
class FurnaceControl(QtCore.QThread):
    new_temp_data = QtCore.pyqtSignal(object) ## type is a list [z1, z2, z3]
    # new_zone2_data = QtCore.pyqtSignal(object)
    # new_zone3_data = QtCore.pyqtSignal(object)

    def __init__(self,logger,delay = 30, testing = False):
        super().__init__()
        self.logger = logger
        self.delay = delay
        self.testing = testing
        self.running = False

        self.connection = GenericSerialDevice(com_port=4, parity=serial.PARITY_EVEN, testing=testing,
                                                          name='Temperature Controller')
    
    def run(self):
        self.running = True
        while self.running:
            if self.testing:
                self.new_temp_data.emit([25,25,25])
            else:
                data = []
                for zone_number in (1,2,3):
                    response = self.connection.ask(f'\x020{zone_number}010WRDD0003,01\x03')
                    data.append(int(response.split('OK')[1][0:4],16))

                self.new_temp_data.emit(data)