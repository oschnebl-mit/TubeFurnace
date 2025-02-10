import serial
from datetime import datetime
from time import sleep, time
from pathlib import Path
from threading import Thread, Lock
import logging
# import pandas as pd
import numpy as np
# from IPython.display import display
# import plotly.graph_objects as go
# from tqdm.notebook import tqdm


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

gas_ids = {
    'N2': 'A',
    'Ar': 'B',
    'O2': 'C',
    'FG': 'D',
    'H2S': 'E',
    'H2Se': 'F'
}


class GenericSerialDevice:
    def __init__(self, com_port=0, baudrate=9600, timeout=0.1, parity=serial.PARITY_NONE, bytesize=serial.EIGHTBITS,
                 testing=False, name='serial device'):
        self.testing = testing
        self.max_number_of_attempts_per_read = 5
        self.min_ms_between_successive_reads = 50
        self.com_lock = Lock()
        self.com_port = com_port
        self.serial_baudrate = baudrate
        self.serial_timeout = timeout
        self.serial_parity = parity
        self.serial_bytesize = bytesize
        self.name = name

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

    def _write(self, message_str: str):
        if not message_str.endswith('\r'):
            message_str = message_str + '\r'

        if self.testing:
            print(f'would write {message_str}')
        else:
            self._serial_connection.write(bytes(message_str, 'ascii'))
            logger.debug(f'wrote {message_str} to {self.name}')

    def write(self, message_str: str):
        with self.com_lock:
            self._write(message_str)

    def _read(self, accept_empty_response=False) -> str:
        if self.testing:
            return ''

        for i in range(self.max_number_of_attempts_per_read):
            sleep(self.min_ms_between_successive_reads / 1000)
            response = self._serial_connection.readline()

            try:
                str_response = response.decode()
                logger.debug(f'received response: {str_response} from {self.name}')
                if accept_empty_response or (str_response != ""):
                    return str_response  # successful read, so exit for-loop

            except Exception as ex:
                logger.warning(f'Read attempt {i + 1}: failed to decode response of "{response}" from {self.name}')
                logger.exception(ex)

        logger.warning(f'{self.name} failed to perform read after {self.max_number_of_attempts_per_read} tries')
        return ""

    def read(self, accept_empty_response=False) -> str:
        with self.com_lock:
            return self._read(accept_empty_response)

    def ask(self, message, accept_empty_response=False):
        with self.com_lock:
            self._write(message)
            return self._read(accept_empty_response)


class ProcessController:
    def __init__(self, log_path: Path, testing=False):
        self.testing = testing
        self.mfc = GenericSerialDevice(com_port=3, baudrate=19200, testing=testing, name='MFC Controller')
        self.pressure_gauge = GenericSerialDevice(com_port=6, testing=testing, name='Pressure Gauge')
        self.temperature_controller = GenericSerialDevice(com_port=4, parity=serial.PARITY_EVEN, testing=testing,
                                                          name='Temperature Controller')
        self.temperature_controller.min_ms_between_successive_reads = 200

        self.overpressure_limit = 800

        self.fill_initial_sccm = 100
        self.fill_flow_sccm = 1000
        self.fill_approach_sccm = 100

        self._logging_start_time = None
        self.log_path = log_path
        self._logging_active = False
        self._logging_thread = None
        self.logging_interval = 10
        self.gases_to_show_on_plot = ['H2S', 'Ar']
        self._logging_traces = dict()
        self._logging_figure = go.Figure()

    def _set_sccm_for_gas(self, gas_id_letter: str, sccm: int):  # TODO confirm this works
        self.mfc.ask(f'{gas_id_letter}S{sccm}')  # using 'ask' here instead of 'write' to flush response from mfc
        logger.debug(f'setting gas "{gas_id_letter}" to {sccm}sccm')

    @property
    def logging_is_active(self):
        return self._logging_active

    def set_N2_sccm(self, sccm: int):
        self._set_sccm_for_gas(gas_ids['N2'], sccm)

    def set_Ar_sccm(self, sccm: int):
        self._set_sccm_for_gas(gas_ids['Ar'], sccm)

    def set_forming_gas_sccm(self, sccm: int):
        self._set_sccm_for_gas(gas_ids['FG'], sccm)

    def set_H2S_sccm(self, sccm: int):
        self._set_sccm_for_gas(gas_ids['H2S'], sccm)

    def set_H2Se_sccm(self, sccm: int):
        self._set_sccm_for_gas(gas_ids['H2Se'], sccm)

    def stop_all_gas_flows(self):
        self.set_N2_sccm(0)
        self.set_Ar_sccm(0)
        self.set_forming_gas_sccm(0)
        self.set_H2S_sccm(0)
        self.set_H2Se_sccm(0)

    @staticmethod
    def _process_mfc_response(response: str) -> dict:  # TODO confirm this works
        numeric_cols = ['PSIA', 'flow_temp', 'vol_flow_ccm', 'sccm', 'sccm_setpoint']
        all_cols = ['ID', 'PSIA', 'flow_temp', 'vol_flow_ccm', 'sccm', 'sccm_setpoint', 'gas_name']
        received_values = response.split()
        if len(received_values) < len(all_cols):  # want to preserve same output dict structure if read fails
            logger.warning(f'Received unexpected mfc response: {response}. Treating as NaNs')
            return {key: np.nan for key in all_cols}

        return {
            key: (float(value) if key in numeric_cols else value)
            for key, value in zip(
                all_cols,
                received_values
            )
        }

    def get_data_for_gas(self, gas_id_letter) -> dict:
        if self.testing:
            return {
                key: -1
                for key in ['ID', 'PSIA', 'flow_temp', 'vol_flow_ccm', 'sccm', 'sccm_setpoint', 'gas_name']
            }

        else:
            response = self.mfc.ask(f'{gas_id_letter}')
            return self._process_mfc_response(response)

    def get_tube_pressure_torr(self) -> float:
        if self.testing:
            return 100.0

        else:
            response = None
            try:
                response = self.pressure_gauge.ask('p')
                return float(
                    ''.join(response.split()[:-1])
                )
            except Exception as ex:
                logger.warning(f'Exception occurred when reading gauge pressure! response = {response}')
                logger.exception(ex)
                return -1

    def get_zone_temperature_setpoint(self, zone_number):
        if self.testing:
            return 25

        else:
            command = f'\x020{zone_number}010WRDD0003,01\x03'
            response = self.temperature_controller.ask(command)
            return int(response.split('OK')[1][0:4], 16)

    def get_zone_temperature(self, zone_number: int) -> float:
        if self.testing:
            return 25

        else:
            command = f'\x020{zone_number}010WRDD0002,01\x03'
            response = self.temperature_controller.ask(command)
            return int(response.split('OK')[1][0:4], 16)

    def set_zone_temperature(self, zone_number: int, temperature: float):
        command = f'\x020{zone_number}010WWRD0114,01,{temperature:04X}\x03\r'
        # after sending command, need to read response to clear acknowledgement from output buffer
        response = self.temperature_controller.ask(command)
        if 'OK' not in response:
            logger.warning(f'setting {zone_number} temperature to {temperature} returned: {response}')

    def set_all_zone_temperatures(self, temperature: float):
        for i in (1, 2, 3):
            self.set_zone_temperature(i, temperature)

    def _get_data(self) -> dict:
        timestamp = datetime.now()
        data_dict = {
            'timestamp': timestamp,
            'hours': (
                (datetime.now() - self._logging_start_time).total_seconds() / 3600
                if self._logging_start_time
                else -1
            ),
            'tube_torr': self.get_tube_pressure_torr(),
            'zone_1_temperature_C': self.get_zone_temperature(1),
            'zone_2_temperature_C': self.get_zone_temperature(2),
            'zone_3_temperature_C': self.get_zone_temperature(3),
            'zone_1_setpoint_C': self.get_zone_temperature_setpoint(1),
            'zone_2_setpoint_C': self.get_zone_temperature_setpoint(2),
            'zone_3_setpoint_C': self.get_zone_temperature_setpoint(3),
        }
        for gas_name, gas_id_letter in gas_ids.items():
            data_dict |= {
                f'{gas_name}_{parameter_name}': parameter_value
                for parameter_name, parameter_value in self.get_data_for_gas(gas_id_letter).items()
            }

        return data_dict

    def __del__(self):
        self.close_connections()

    def close_connections(self):
        for o in [self.mfc, self.pressure_gauge, self.temperature_controller]:
            o.close_connection()

    def _plot_purge_data_and_wait(self, tube_pressure, t0):
        t = time() - t0
        add_data_to_trace(self._purge_sccm_trace, t, self.get_data_for_gas(gas_ids.get('Ar'))['sccm'])
        add_data_to_trace(self._purge_torr_trace, t, tube_pressure)
        sleep(0.5)

    def bring_to_atmospheric_pressure(self, approach_pressure=675, final_pressure=755):
        if self.testing:
            return

        if self.get_tube_pressure_torr() > final_pressure:
            return

        self._init_purge_figure(approach_pressure, final_pressure)
        t0 = time()
        try:
            logger.info(f'Flowing {self.fill_initial_sccm}sccm Ar . . .')
            self.set_Ar_sccm(self.fill_initial_sccm)
            # flow at fill_initial_sccm for first 5 seconds to avoid big initial puff of gas
            while (tube_pressure := self.get_tube_pressure_torr()) < approach_pressure and (time() - t0) < 5:
                self._plot_purge_data_and_wait(tube_pressure, t0)

            logger.info(f'Flowing {self.fill_flow_sccm}sccm Ar. . .')
            self.set_Ar_sccm(self.fill_flow_sccm)
            while (tube_pressure := self.get_tube_pressure_torr()) < approach_pressure:
                self._plot_purge_data_and_wait(tube_pressure, t0)

            logger.info(f'Reached {approach_pressure}Torr. Lowering flow to {self.fill_approach_sccm}sccm')
            self.set_Ar_sccm(self.fill_approach_sccm)
            while (tube_pressure := self.get_tube_pressure_torr()) < final_pressure:
                self._plot_purge_data_and_wait(tube_pressure, t0)

            self.set_Ar_sccm(0)
            logger.info(f'Reached {final_pressure}Torr, stopping Ar flow')
            for i in range(10):  # plot just a few more points for piece of mind
                self._plot_purge_data_and_wait(self.get_tube_pressure_torr(), t0)

        except KeyboardInterrupt:
            self.set_Ar_sccm(0)
            print('Caught KeyboardInterrupt! Set Ar flow to 0sccm.')

        except Exception as ex:
            self.set_Ar_sccm(0)
            print('Caught Exeption! Set Ar flow to 0sccm.')
            logger.exception(ex)
            raise ex

    def _init_purge_figure(self, approach_pressure, final_pressure):
        fig = go.FigureWidget()
        fig.update_layout(
            width=1000, height=400,
            yaxis_title='SCCM',
            yaxis2=dict(overlaying='y', side='right', title='Torr'),
            template='simple_white',
            legend_orientation='h'
        )
        fig.add_scatter(x=[], y=[], yaxis='y2', name='Torr')
        self._purge_torr_trace = fig.data[-1]
        fig.add_scatter(x=[], y=[], name='Ar SCCM')
        self._purge_sccm_trace = fig.data[-1]
        fig.add_hline(y=approach_pressure, line_dash='dot', line_color='grey', yref='y2', line_width=2)
        fig.add_hline(y=final_pressure, line_dash='solid', line_color='grey', yref='y2', line_width=2)
        display(fig)

    def _init_logging_figure(self):
        ## What I would change: temperature, then gas, then pressure, all in a row, make yscale on torr wider
        fig = go.FigureWidget()
        fig.set_subplots(
            rows=2, cols=2, shared_xaxes='all',
            horizontal_spacing=0.15,
            specs=[[{}, {}],
                   [{"colspan": 2}, None]]
        )
        fig.update_xaxes(mirror=True, automargin=True)
        fig.update_yaxes(mirror=True, automargin=True, title_font_size=12)
        fig.update_layout(
            height=600,
            template='simple_white',
            xaxis3_title='time',
            yaxis_title='SCCM',
            yaxis2_title="Torr",
            yaxis3_title="Temperature",
            legend_orientation='h',
            legend_y=1.1,
            legend_yanchor='bottom',
        )

        fig.add_scatter(x=[], y=[], name='Torr', yaxis='y2', xaxis='x2')
        self._logging_traces['torr'] = fig.data[-1]
        for gas in self.gases_to_show_on_plot:
            fig.add_scatter(
                x=[], y=[], name=f'{gas} flow', yaxis='y', xaxis='x'
            )
            self._logging_traces[gas] = fig.data[-1]

        for zone in (1, 2, 3):
            fig.add_scatter(
                x=[], y=[], name=f'zone {zone} T',
                yaxis='y3', xaxis='x3', line_color='grey', mode='lines'
            )
            self._logging_traces[f'T {zone}'] = fig.data[-1]

        self._logging_figure = fig
        display(fig)

    def _log_data_row(self):
        data_dict = self._get_data()
        df = pd.DataFrame([data_dict])
        df.to_csv(
            self.log_path,
            mode='a' if self.log_path.exists() else 'w',
            header=not self.log_path.exists(),
            index=False
        )
        return data_dict

    def _add_log_data_to_plot(self, data_dict):
        t = data_dict['timestamp']
        with self._logging_figure.batch_update():
            add_data_to_trace(self._logging_traces['torr'], t, data_dict['tube_torr'])
            for zone in (1, 2, 3):
                add_data_to_trace(
                    self._logging_traces[f'T {zone}'], t, data_dict[f'zone_{zone}_temperature_C']
                )

            for gas in self.gases_to_show_on_plot:
                add_data_to_trace(
                    self._logging_traces[gas], t, data_dict[f'{gas}_sccm']
                )
            ## potential addition to highlight the zone you are waiting on, otherwise can't tell between them
            # if self.track_zone!=None:
            #     fig.update_traces(patch={"line": {"color": "black", "dash": 'dot'}}, selector={'name': f'zone {track_zone} T'}) 

    def abort(self):
        self.stop_all_gas_flows()
        self.set_all_zone_temperatures(20)

    def _check_for_overpressure_condition(self):
        if self.get_tube_pressure_torr() > self.overpressure_limit:
            self.abort()
            logger.critical(f'OVERPRESSURE ALERT. All gas flows stopped, temperatures set to 20C')

    def _logging_loop(self):
        while self._logging_active:
            try:
                self._check_for_overpressure_condition()
                data_dict = self._log_data_row()
                self._add_log_data_to_plot(data_dict)
            except Exception as ex:
                logger.warning(f'{Exception} in logging loop')
                logger.exception(ex)

            sleep(self.logging_interval)

    def start_data_logging(self):
        self._init_logging_figure()
        self._logging_start_time = datetime.now()
        self._logging_active = True
        self._logging_thread = Thread(target=self._logging_loop, name='LogThread')
        self._logging_thread.start()
        logger.info('starting data logging thread')

    def stop_data_logging(self, save_fig=True):
        self._logging_active = False
        logger.info('stopping data logging thread')
        if save_fig:
            self._logging_figure.to_html(f'{self.log_path.stem}_fig.html')
            self._logging_figure.write_image(f'{self.log_path.stem}_fig.png', scale=2)

    @staticmethod
    def wait(seconds_to_wait, interval=0.1, show_progress=False, progress_label=None):
        """helper function to break long sleeps into small intervals. Allows KeyboardInterrupt"""
        if show_progress:
            pbar = tqdm(desc=progress_label, total=seconds_to_wait, unit='s')
            t0 = time()
            while time() - t0 < seconds_to_wait:
                pbar.n = round(time() - t0, 2)
                pbar.refresh()
                sleep(interval)
            pbar.n = seconds_to_wait
            pbar.close()

        else:
            t0 = time()
            while time() - t0 < seconds_to_wait:
                sleep(interval)

    def wait_for_temperature(self, T, zone='all', condition='equal', interval=30):
        """helper function to wait for a temperature condition. 
        zone=1, 2, 3, or 'all'
        condition='equal', 'lower', 'higher'"""
        valid_zones = (1, 2, 3, 'all')
        if zone not in valid_zones:
            raise ValueError(f'Invalid zone parameter. Expected one of {valid_zones}; received {zone}')

        get_temps = lambda: [self.get_zone_temperature(i) for i in (1, 2, 3)] if zone == 'all' else [
            self.get_zone_temperature(zone)]

        if condition == 'lower':
            get_delta = lambda temps: max([t - T for t in temps])

        elif condition == 'higher':
            get_delta = lambda temps: max([T - t for t in temps])

        elif condition == 'equal':
            get_delta = lambda temps: max([abs(T - t) for t in temps])

        else:
            raise ValueError(f'Invalid condition: {condition}. Should be "lower", "higher", or "equal".')

        initial_Ts = get_temps()
        initial_delta = get_delta(initial_Ts)
        if initial_delta <= 0:
            return
        pbar = tqdm(desc=f'Waiting for {T}', total=initial_delta, unit='C')
        while True:
            current_temps = get_temps()
            current_delta = get_delta(current_temps)
            if current_delta <= 0:
                break
            pbar.n = initial_delta - current_delta
            pbar.refresh()
            self.wait(interval)

        pbar.n = initial_delta
        pbar.close()


# def add_data_to_trace(trace: go.Scatter, x, y):
#     trace.update(x=np.append(trace.x, x), y=np.append(trace.y, y))

if __name__ == "__main__":
    tctrl = GenericSerialDevice(com_port=5,parity=serial.PARITY_EVEN,testing=False,name='Temperature Controller')
    response = tctrl.ask(f'\x0202010WRDD004,01\x03\r')
    print(response)