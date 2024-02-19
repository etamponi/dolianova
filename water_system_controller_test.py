import os
import time
import unittest

from gpiozero import Device
from gpiozero.pins.mock import MockFactory

# Adjust the import path as needed
from water_system_controller import WaterSystemController

Device.pin_factory = MockFactory()


class TestWaterSystemController(unittest.TestCase):
  def setUp(self):
    self.sensor_pins = {'tank1_full': 17, 'tank1_empty': 18,
                        'tank2_full': 27, 'tank2_empty': 22}
    self.pump_pins = {'pump1': 23, 'pump2': 24}
    self.state_file = 'test_water_system_state.json'
    # Remove the state file if needed
    if os.path.exists(self.state_file):
      os.remove(self.state_file)

  def test_start_pump(self):
    controller = WaterSystemController(
      self.sensor_pins, self.pump_pins, self.state_file)
    controller.start_pump('pump1')
    self.assertTrue(controller.state['pump1_running'])

  def test_start_pump_twice(self):
    controller = WaterSystemController(
      self.sensor_pins, self.pump_pins, self.state_file)
    controller.start_pump('pump1')
    start_time = controller.state['pump1_start_time']
    time.sleep(1)
    controller.start_pump('pump1')
    self.assertEquals(start_time, controller.state['pump1_start_time'])

  def tearDown(self):
    # Remove the state file if needed
    if os.path.exists(self.state_file):
      os.remove(self.state_file)


if __name__ == '__main__':
  unittest.main()
