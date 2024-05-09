import json
import os
import time
from datetime import datetime, timedelta

from gpiozero import Button, DigitalOutputDevice


class WaterSystemController:
  def __init__(self, config):
    self.sensor_pins = {
        'tank1_min_level': Button(config['pins']['tank1_min_level']),
        'tank1_max_level': Button(config['pins']['tank1_max_level']),
        'tank2_min_level': Button(config['pins']['tank2_min_level']),
        'tank2_max_level': Button(config['pins']['tank2_max_level']),
    }
    self.pump_pins = {
        'pump1': DigitalOutputDevice(config['pins']['pump1']),
        'pump2': DigitalOutputDevice(config['pins']['pump2']),
    }
    self.pump_settings = config['pump_settings']
    self.state_file = config['state_file']
    self.state = self.read_state()

  def read_state(self):
    if os.path.exists(self.state_file):
      with open(self.state_file, 'r') as file:
        return json.load(file)
    else:
      return {'pump1_last_on': None, 'pump2_last_on': None,
              'pump1_running': False, 'pump2_running': False,
              'pump1_start_time': None, 'pump2_start_time': None,
              'tank1_state': 'filling'}

  def write_state(self):
    with open(self.state_file, 'w') as file:
      json.dump(self.state, file, indent=2, sort_keys=True)

  def print_state(self):
    now = datetime.now()
    if self.sensor_pins['tank1_max_level'].is_active:
      print('Tank1 is full')
    elif self.sensor_pins['tank1_min_level'].is_active:
      print('Tank1 is half full')
    elif not self.sensor_pins['tank1_min_level'].is_active:
      print('Tank1 is empty')

    if self.sensor_pins['tank2_max_level'].is_active:
      print('Tank2 is full')
    elif self.sensor_pins['tank2_min_level'].is_active:
      print('Tank2 is half full')
    elif not self.sensor_pins['tank2_min_level'].is_active:
      print('Tank2 is empty')

    if self.state['pump1_running'] != self.pump_pins['pump1'].is_active:
      print('WARNING: pump1 state is inconsistent')
    if self.state['pump2_running'] != self.pump_pins['pump2'].is_active:
      print('WARNING: pump2 state is inconsistent')

    if self.state['tank1_state'] not in ['filling', 'emptying']:
      print(f'WARNING: tank1 state is invalid ({self.state["tank1_state"]})')

    if self.state['tank1_state'] == 'filling':
      print('Filling tank1')
      if self.sensor_pins['tank1_max_level'].is_active:
        print('WARNING: Tank1 should not be filling while it is full')
      if self.state['pump2_running']:
        print(f'WARNING: pump2 should not be running while tank1 is filling')
      if self.state['pump1_running']:
        pump1_start_time = datetime.fromisoformat(self.state['pump1_start_time'])
        duration = now - pump1_start_time
        max_duration = timedelta(seconds=self.pump_settings['pump1']['max_duration'])
        print(f'Pump1 is running for {minutes(duration)} minutes (since {pump1_start_time})')
        print(f'Pump1 will be turned off in {minutes(max_duration - duration)} minutes')
      elif self.state['pump1_last_on'] is not None:
        pump1_last_on = datetime.fromisoformat(self.state['pump1_last_on'])
        duration = now - pump1_last_on
        cooldown = timedelta(seconds=self.pump_settings['pump1']['cooldown'])
        print(f'Pump1 was turned off {minutes(duration)} minutes ago (at {pump1_last_on})')
        print(f'Pump1 will be turned on again in {minutes(cooldown - duration)} minutes')
      else:
        print('Pump1 is off')

    if self.state['tank1_state'] == 'emptying':
      print('Filling tank2')
      if self.sensor_pins['tank2_max_level'].is_active and self.state['pump2_running']:
        print('WARNING: Pump2 should not be running while tank2 is full')
      if self.state['pump1_running']:
        print('WARNING: pump1 should not be running while tank2 is filling')
      tank1_filled_at = datetime.fromisoformat(self.state['pump1_last_on'])
      wait_time = timedelta(seconds=self.pump_settings['pump2']['wait_time'])
      elapsed_time = now - tank1_filled_at
      if now - tank1_filled_at < wait_time:
        if self.state['pump2_running']:
          print(f'WARNING: pump2 should not be running if tank1 was filled less than {minutes(wait_time)} minutes ago')
        else:
          print(f'Tank1 was filled {minutes(now - tank1_filled_at)} minutes ago (at {tank1_filled_at})')
          print(f'Pump2 will be turned on in {minutes(wait_time - elapsed_time)} minutes (at {tank1_filled_at + wait_time})')
      elif self.state['pump2_running']:
        print('Pump2 is running')
      else:
        print('Pump2 is off')
    print()

  def start_pump(self, pump, why=None):
    self.pump_pins[pump].on()
    if self.state[f'{pump}_running']:
      return
    self.state[f'{pump}_running'] = True
    self.state[f'{pump}_start_time'] = datetime.now().isoformat()
    self.state[f'{pump}_last_on'] = None
    if why:
      print(f'Starting {pump} because {why}')
    self.write_state()

  def stop_pump(self, pump, why=None):
    self.pump_pins[pump].off()
    if not self.state[f'{pump}_running']:
      return
    self.state[f'{pump}_running'] = False
    self.state[f'{pump}_start_time'] = None
    self.state[f'{pump}_last_on'] = datetime.now().isoformat()
    if why:
      print(f'Stopping {pump} because {why}')
    self.write_state()

  def check_pump_duration(self):
    now = datetime.now()
    for pump, settings in self.pump_settings.items():
      if 'max_duration' in settings and self.state[f'{pump}_start_time']:
        start_time = datetime.fromisoformat(self.state[f'{pump}_start_time'])
        duration = now - start_time
        max_duration = timedelta(seconds=self.pump_settings['pump1']['max_duration'])
        if duration >= max_duration:
          self.stop_pump(pump, f'it has been running for {minutes(duration)} minutes')

  def transfer_water_to_tank1(self):
    if self.state['tank1_state'] != 'filling':
      return
    now = datetime.now()
    if self.state['pump1_last_on']:
      last_on = datetime.fromisoformat(self.state['pump1_last_on'])
      elapsed = now - last_on
      cooldown = timedelta(seconds=self.pump_settings['pump1']['cooldown'])
      if elapsed < cooldown:
        return
    if not self.sensor_pins['tank1_max_level'].is_active:
      self.start_pump('pump1', 'tank1 is not full')
    if self.sensor_pins['tank1_max_level'].is_active:
      self.set_tank1_state('emptying', 'tank1 is full')
      self.stop_pump('pump1', 'tank1 is full')

  def transfer_water_to_tank2(self):
    if self.state['tank1_state'] != 'emptying':
      return
    if self.state['pump1_last_on'] is None:
      raise Exception(
        'Pump 1 should have been running if we are in the emptying state.')
    now = datetime.now()
    tank1_filled_at = datetime.fromisoformat(self.state['pump1_last_on'])
    elapsed = now - tank1_filled_at
    wait_time = timedelta(seconds=self.pump_settings['pump2']['wait_time'])
    if elapsed < wait_time:
      return
    if not self.sensor_pins['tank2_max_level'].is_active:
      self.start_pump('pump2', 'tank2 is not full')
    if self.sensor_pins['tank2_max_level'].is_active:
      self.stop_pump('pump2', 'tank2 is full')
    if not self.sensor_pins['tank1_min_level'].is_active:
      self.set_tank1_state('filling', 'tank1 is empty')
      self.stop_pump('pump2', 'tank1 is empty')

  def set_tank1_state(self, state, why=None):
    if state not in ['filling', 'emptying']:
      raise ValueError('Invalid state')
    if state == self.state['tank1_state']:
      return
    self.state['tank1_state'] = state
    if why:
      print(f'Setting tank1_state to "{state}" because {why}')
    self.write_state()

  def step(self):
    print(f'Time: {datetime.now()}')
    self.transfer_water_to_tank1()
    self.transfer_water_to_tank2()
    # Call it again because the state might have changed.
    self.transfer_water_to_tank1()
    self.check_pump_duration()
    self.print_state()

  def main_loop(self):
    self.stop_pump('pump1', 'initialization')
    self.stop_pump('pump2', 'initialization')
    try:
      while True:
        self.step()
        time.sleep(1)  # Short sleep to prevent high CPU usage
    except KeyboardInterrupt:
      print(f'Exiting at {datetime.now()}')
      self.stop_pump('pump1', 'shutdown')
      self.stop_pump('pump2', 'shutdown')
      pass  # Cleanup is handled automatically by gpiozero


def minutes(a):
  return round(a / timedelta(minutes=1), 3)


if __name__ == '__main__':
  with open('water_system_config.json', 'r') as file:
    config = json.load(file)
  controller = WaterSystemController(config)
  controller.main_loop()
