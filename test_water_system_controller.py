import os
import unittest

from gpiozero import Device
from gpiozero.pins.mock import MockFactory

from water_system_controller import WaterSystemController  # Adjust the import path as needed

Device.pin_factory = MockFactory()

class TestWaterSystemController(unittest.TestCase):
    def setUp(self):
        self.sensor_pins = {'tank1_full': 17, 'tank1_empty': 18, 'tank2_full': 27, 'tank2_empty': 22}
        self.pump_pins = {'pump1': 23, 'pump2': 24}
        self.state_file = 'test_water_system_state.json'

    def test_start_pump(self):
        # This is an example test. You should add more tests to cover all methods.
        controller = WaterSystemController(self.sensor_pins, self.pump_pins, self.state_file)
        controller.start_pump('pump1')
        self.assertTrue(controller.state['pump1_running'])

    def tearDown(self):
        # Remove the state file if needed
        if os.path.exists(self.state_file):
            os.remove(self.state_file)

if __name__ == '__main__':
    unittest.main()
