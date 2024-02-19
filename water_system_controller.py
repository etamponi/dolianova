import json
import os
import time
from datetime import datetime, timedelta

from gpiozero import DigitalInputDevice, DigitalOutputDevice


class WaterSystemController:
  def __init__(
          self, sensor_pins_config, pump_pins_config, pump_settings=None,
          state_file='water_system_state.json'):
    self.sensor_pins = {
        'tank1_full': DigitalInputDevice(sensor_pins_config['tank1_full']),
        'tank1_empty': DigitalInputDevice(sensor_pins_config['tank1_empty']),
        'tank2_full': DigitalInputDevice(sensor_pins_config['tank2_full']),
        'tank2_empty': DigitalInputDevice(sensor_pins_config['tank2_empty']),
    }
    self.pump_pins = {
        'pump1': DigitalOutputDevice(pump_pins_config['pump1']),
        'pump2': DigitalOutputDevice(pump_pins_config['pump2']),
    }
    if pump_settings is None:
      pump_settings = {
          'pump1': {'max_duration': 30 * 60, 'cooldown': 5 * 60 * 60},
          'pump2': {'wait_time': 12 * 60 * 60},
      }
    self.pump_settings = pump_settings
    self.state_file = state_file
    self.state = self.read_state()

  def read_state(self):
    if os.path.exists(self.state_file):
      with open(self.state_file, 'r') as file:
        return json.load(file)
    else:
      return {'pump1_last_on': None, 'pump2_last_on': None,
              'pump1_running': False, 'pump2_running': False,
              'pump1_start_time': None, 'pump2_start_time': None,
              'tank1_state': 'emptying'}

  def write_state(self):
    with open(self.state_file, 'w') as file:
      json.dump(self.state, file)

  def start_pump(self, pump):
    self.pump_pins[pump].on()
    if self.state[f'{pump}_running']:
      return
    self.state[f'{pump}_running'] = True
    self.state[f'{pump}_start_time'] = datetime.now().isoformat()
    self.state[f'{pump}_last_on'] = None
    self.write_state()

  def stop_pump(self, pump):
    self.pump_pins[pump].off()
    if not self.state[f'{pump}_running']:
      return
    self.state[f'{pump}_running'] = False
    self.state[f'{pump}_start_time'] = None
    self.state[f'{pump}_last_on'] = datetime.now().isoformat()
    self.write_state()

  def check_pump_duration(self):
    now = datetime.now()
    for pump, settings in self.pump_settings.items():
      if settings['max_duration']:
        start_time = datetime.fromisoformat(self.state[f'{pump}_start_time'])
        if (now - start_time).seconds >= settings['max_duration']:
          self.stop_pump(pump)

  def transfer_water_to_tank1(self):
    if self.state['tank1_state'] != 'filling':
      return
    now = datetime.now()
    if self.state['pump1_last_on']:
      last_on = datetime.fromisoformat(self.state['pump1_last_on'])
      if now - last_on < timedelta(seconds=self.pump_settings['pump1']['cooldown']):
        return
    if not self.sensor_pins['tank1_full'].is_active:
      self.start_pump('pump1')
    if self.sensor_pins['tank1_full'].is_active:
      self.state['tank1_state'] = 'emptying'
      self.stop_pump('pump1')

  def transfer_water_to_tank2(self):
    if self.state['tank1_state'] != 'emptying':
      return
    if self.state['pump1_last_on'] is None:
      raise Exception(
        'Pump 1 should have been running if we are in the emptying state.')
    now = datetime.now()
    tank1_filled_at = datetime.fromisoformat(self.state['pump1_last_on'])
    if now - tank1_filled_at < timedelta(seconds=self.pump_settings['pump2']['wait_time']):
      return
    if not self.sensor_pins['tank2_full'].is_active:
      self.start_pump('pump2')
    if self.sensor_pins['tank1_empty'].is_active:
      self.state['tank1_state'] = 'filling'
      self.stop_pump('pump2')

  def main_loop(self):
    try:
      while True:
        self.transfer_water_to_tank1()
        self.transfer_water_to_tank2()
        self.check_pump_duration()
        time.sleep(1)  # Short sleep to prevent high CPU usage
    except KeyboardInterrupt:
      pass  # Cleanup is handled automatically by gpiozero


if __name__ == '__main__':
  sensor_pins_config = {'tank1_full': 17,
                        'tank1_empty': 18,
                        'tank2_full': 27,
                        'tank2_empty': 22}
  pump_pins_config = {'pump1': 23, 'pump2': 24}
  controller = WaterSystemController(sensor_pins_config, pump_pins_config)
  controller.main_loop()
