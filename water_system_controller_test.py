import os
import time
import unittest

from gpiozero import Device
from gpiozero.pins.mock import MockFactory

from water_system_controller import WaterSystemController

Device.pin_factory = MockFactory()


class TestWaterSystemController(unittest.TestCase):
  def setUp(self):
    self.config = {
        "pins": {
            "tank1_max_level": 17,
            "tank1_min_level": 18,
            "tank2_max_level": 27,
            "tank2_min_level": 22,
            "pump1": 23,
            "pump2": 24
        },
        "pump_settings": {
            "pump1": {
                "max_duration": 1,
                "cooldown": 2
            },
            "pump2": {
                "wait_time": 3
            }
        },
        "state_file": "test_water_system_state.json"
    }
    # Remove the state file if needed
    if os.path.exists(self.config['state_file']):
      os.remove(self.config['state_file'])

  def test_start_pump(self):
    controller = WaterSystemController(self.config)
    controller.start_pump('pump1')
    self.assertTrue(controller.state['pump1_running'])

  def test_start_pump_twice(self):
    controller = WaterSystemController(self.config)
    controller.start_pump('pump1')
    start_time = controller.state['pump1_start_time']
    time.sleep(1)
    controller.start_pump('pump1')
    self.assertEquals(start_time, controller.state['pump1_start_time'])

  def test_step(self):
    controller = WaterSystemController(self.config)
    print()

    # Let's start with both tanks empty:
    controller.sensor_pins['tank1_min_level'].pin.drive_high()
    controller.sensor_pins['tank1_max_level'].pin.drive_high()
    controller.sensor_pins['tank2_min_level'].pin.drive_high()
    controller.sensor_pins['tank2_max_level'].pin.drive_high()
    controller.print_state()

    controller.step()
    time.sleep(1)
    controller.sensor_pins['tank1_min_level'].pin.drive_low()
    controller.step()
    time.sleep(1)
    controller.step()
    time.sleep(1)
    controller.step()
    time.sleep(1)
    controller.sensor_pins['tank1_max_level'].pin.drive_low()
    controller.step()
    time.sleep(1)
    controller.step()
    time.sleep(1)
    controller.step()
    time.sleep(1)
    controller.step()
    time.sleep(1)
    controller.sensor_pins['tank2_min_level'].pin.drive_low()
    controller.sensor_pins['tank1_max_level'].pin.drive_high()
    controller.step()
    time.sleep(1)
    controller.sensor_pins['tank2_max_level'].pin.drive_low()
    controller.step()
    time.sleep(1)
    controller.sensor_pins['tank2_max_level'].pin.drive_high()
    controller.step()
    time.sleep(1)
    controller.sensor_pins['tank1_min_level'].pin.drive_high()
    controller.step()

  def tearDown(self):
    # Remove the state file if needed
    if os.path.exists(self.config['state_file']):
      os.remove(self.config['state_file'])


if __name__ == '__main__':
  unittest.main()
