import json
import os
import time
from datetime import datetime, timedelta

from gpiozero import DigitalInputDevice, DigitalOutputDevice

class WaterSystemController:
    def __init__(self, sensor_pins_config, pump_pins_config, state_file='water_system_state.json'):
        self.sensor_pins = {
            'tank1_full': DigitalInputDevice(sensor_pins_config['tank1_full']),
            'tank1_empty': DigitalInputDevice(sensor_pins_config['tank1_empty']),
            'tank2_full': DigitalInputDevice(sensor_pins_config['tank2_full']),
            'tank2_empty': DigitalInputDevice(sensor_pins_config['tank2_empty'])
        }
        self.pump_pins = {
            'pump1': DigitalOutputDevice(pump_pins_config['pump1']),
            'pump2': DigitalOutputDevice(pump_pins_config['pump2'])
        }
        self.state_file = state_file
        self.state = self.read_state()

    def read_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as file:
                return json.load(file)
        else:
            return {'pump1_last_on': None, 'pump2_last_on': None,
                    'pump1_running': False, 'pump2_running': False,
                    'pump1_start_time': None, 'pump2_start_time': None}

    def write_state(self):
        with open(self.state_file, 'w') as file:
            json.dump(self.state, file)

    def start_pump(self, pump):
        self.pump_pins[pump].on()
        self.state[f'{pump}_running'] = True
        self.state[f'{pump}_start_time'] = datetime.now().isoformat()
        self.write_state()

    def stop_pump(self, pump):
        self.pump_pins[pump].off()
        self.state[f'{pump}_running'] = False
        self.state[f'{pump}_start_time'] = None
        if pump == 'pump1':
            self.state['pump1_last_on'] = datetime.now().isoformat()
        else:
            self.state['pump2_last_on'] = datetime.now().isoformat()
        self.write_state()

    def check_pump_duration(self):
        now = datetime.now()
        for pump in ['pump1', 'pump2']:
            if self.state[f'{pump}_running']:
                start_time = datetime.fromisoformat(self.state[f'{pump}_start_time'])
                if pump == 'pump1' and (now - start_time).seconds >= 40*60:
                    self.stop_pump(pump)
                elif pump == 'pump2' and (now - start_time).seconds >= 60*60:  # Assume 1 hour to fill tank2
                    self.stop_pump(pump)

    def check_and_pump_water_from_well(self):
        now = datetime.now()
        if self.state['pump1_last_on']:
            last_on = datetime.fromisoformat(self.state['pump1_last_on'])
            if now - last_on < timedelta(hours=5):
                return  # Waiting period not over
        if not self.sensor_pins['tank1_full'].is_active and not self.state['pump1_running']:
            self.start_pump('pump1')

    def transfer_water_to_tank2(self):
        now = datetime.now()
        if self.state['pump2_last_on']:
            last_on = datetime.fromisoformat(self.state['pump2_last_on'])
            if now - last_on < timedelta(hours=12):
                return  # Water settling period not over
        if self.sensor_pins['tank1_full'].is_active and not self.sensor_pins['tank2_full'].is_active and not self.state['pump2_running']:
            self.start_pump('pump2')

    def main_loop(self):
        try:
            while True:
                self.check_and_pump_water_from_well()
                self.transfer_water_to_tank2()
                self.check_pump_duration()
                time.sleep(1)  # Short sleep to prevent high CPU usage
        except KeyboardInterrupt:
            pass  # Cleanup is handled automatically by gpiozero

if __name__ == '__main__':
    sensor_pins_config = {'tank1_full': 17, 'tank1_empty': 18, 'tank2_full': 27, 'tank2_empty': 22}
    pump_pins_config = {'pump1': 23, 'pump2': 24}
    controller = WaterSystemController(sensor_pins_config, pump_pins_config)
    controller.main_loop()
