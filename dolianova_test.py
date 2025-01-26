import pathlib as pl
import shutil
import typing
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from gpiozero import Device  # type: ignore
from gpiozero.pins.mock import MockFactory  # type: ignore

from dolianova import (
  Context,
  Controller,
  FakeTank,
  FillLargeTank,
  FillSmallTank,
  FillWell,
  GPIOPump,
  GPIOTank,
  History,
  Measures,
  Pump,
  Settings,
  SettleLargeTank,
  State,
  Tank,
  TankLevel,
  SmallTankInUse,
  Well,
)

Device.pin_factory = MockFactory()


class TestWell(unittest.TestCase):
  def test_init_now(self):
    well = well_factory(level=60)
    self.assertEqual(well.level, 60)

  def test_init_30_minutes_ago(self):
    well = well_factory(
      level=0,
      last_update=datetime.now() - timedelta(minutes=30),
    )
    self.assertEqual(well.level, 50)

  def test_pump_activated(self):
    with patch("dolianova.datetime") as mock_datetime:
      mock_now = datetime(2024, 1, 1, 12, 0, 0)
      mock_datetime.now.return_value = mock_now
      well = well_factory(
        level=100,
        last_update=mock_now,
      )
      # Check that mock works
      self.assertEqual(well.level, 100)

      well.pump_activated()

      mock_now += timedelta(minutes=15)
      mock_datetime.now.return_value = mock_now
      self.assertEqual(well.level, 75)

      mock_now += timedelta(minutes=15)
      mock_datetime.now.return_value = mock_now
      self.assertEqual(well.level, 50)

  def test_level_is_idempotent(self):
    well = well_factory(
      level=50,
      last_update=datetime.now(),
    )
    self.assertEqual(well.level, 50)
    self.assertEqual(well.level, 50)
    self.assertEqual(well.level, 50)
    self.assertEqual(well.level, 50)


def well_factory(
  level: int = 50,
  fill_period: timedelta = timedelta(hours=1),
  empty_period: timedelta = timedelta(hours=1),
  last_update: datetime = datetime.now(),
) -> Well:
  return Well(
    level=level,
    fill_period=fill_period,
    empty_period=empty_period,
    last_update=last_update,
  )


def context_factory(
  well: Well | None = None,
  large_tank: Tank | None = None,
  small_tank: Tank | None = None,
  well_to_large_tank_pump: Pump | None = None,
  lower_to_small_tank_pump: Pump | None = None,
  settle_time: timedelta | None = None,
  current_state: type[State] | None = None,
  state_activated_at: datetime | None = None,
) -> Context:
  context = Context(
    well=well or well_factory(),
    large_tank=large_tank or FakeTank(TankLevel.MEDIUM),
    small_tank=small_tank or FakeTank(TankLevel.MEDIUM),
    well_to_large_tank_pump=well_to_large_tank_pump or Pump(),
    lower_to_small_tank_pump=lower_to_small_tank_pump or Pump(),
    settle_time=settle_time or timedelta(hours=12),
    current_state=current_state or FillWell,
    state_activated_at=state_activated_at or datetime.now(),
  )
  return context


def measures_factory(
  time: datetime = datetime.now(),
  well_level: int = 50,
  large_tank_level: TankLevel = TankLevel.MEDIUM,
  small_tank_level: TankLevel = TankLevel.MEDIUM,
  well_to_large_tank_pump_active: bool = False,
  lower_to_small_tank_pump_active: bool = False,
  current_state: type[State] = FillWell,
  state_activated_at: datetime = datetime.now(),
) -> Measures:
  return Measures(
    time=time,
    well_level=well_level,
    large_tank_level=large_tank_level,
    small_tank_level=small_tank_level,
    well_to_large_tank_pump_active=well_to_large_tank_pump_active,
    lower_to_small_tank_pump_active=lower_to_small_tank_pump_active,
    current_state=current_state,
    state_activated_at=state_activated_at,
  )


def settings_factory(
  fill_period: timedelta = timedelta(hours=1),
  empty_period: timedelta = timedelta(hours=1),
  settle_time: timedelta = timedelta(hours=12),
  large_tank_low_floater_pin: str = "GPIO2",
  large_tank_high_floater_pin: str = "GPIO3",
  small_tank_low_floater_pin: str = "GPIO4",
  small_tank_high_floater_pin: str = "GPIO5",
  well_to_large_tank_pump_pin: str = "GPIO6",
  lower_to_small_tank_pump_pin: str = "GPIO7",
) -> Settings:
  return Settings(
    fill_period=fill_period,
    empty_period=empty_period,
    settle_time=settle_time,
    large_tank_low_floater_pin=large_tank_low_floater_pin,
    large_tank_high_floater_pin=large_tank_high_floater_pin,
    small_tank_low_floater_pin=small_tank_low_floater_pin,
    small_tank_high_floater_pin=small_tank_high_floater_pin,
    well_to_large_tank_pump_pin=well_to_large_tank_pump_pin,
    lower_to_small_tank_pump_pin=lower_to_small_tank_pump_pin,
  )


class TestFillWell(unittest.TestCase):
  def test_when_well_is_filled_go_fill_large_tank(self):
    context = context_factory(
      well=well_factory(level=100),
      current_state=FillWell,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, FillLargeTank)

  def test_if_well_is_not_full_stay_there(self):
    context = context_factory(
      well=well_factory(level=50),
      current_state=FillWell,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, context.current_state)


class TestFillLargeTank(unittest.TestCase):
  def test_when_large_tank_is_full_go_to_settle_large_tank(self):
    context = context_factory(
      large_tank=FakeTank(TankLevel.FULL),
      current_state=FillLargeTank,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, SettleLargeTank)

  def test_if_large_tank_is_not_full_stay_there(self):
    large_tank = FakeTank(TankLevel.MEDIUM)
    context = context_factory(
      large_tank=large_tank,
      current_state=FillLargeTank,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, context.current_state)

    large_tank.set_level(TankLevel.EMPTY)
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, context.current_state)

  def test_if_well_is_empty_go_fill_well(self):
    context = context_factory(
      well=well_factory(level=0),
      large_tank=FakeTank(TankLevel.EMPTY),
      current_state=FillLargeTank,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, FillWell)


class TestSettleLargeTank(unittest.TestCase):
  def test_if_large_tank_is_not_full_go_fill_it(self):
    context = context_factory(
      large_tank=FakeTank(TankLevel.MEDIUM),
      current_state=SettleLargeTank,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, FillLargeTank)

  def test_if_not_enough_time_elapsed_stay_there(self):
    context = context_factory(
      large_tank=FakeTank(TankLevel.FULL),
      settle_time=timedelta(hours=12),
      current_state=SettleLargeTank,
      state_activated_at=datetime.now() - timedelta(hours=6),
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, context.current_state)

  def test_if_enough_time_elapsed_go_fill_small_tank(self):
    context = context_factory(
      large_tank=FakeTank(TankLevel.FULL),
      settle_time=timedelta(hours=12),
      current_state=SettleLargeTank,
      state_activated_at=datetime.now() - timedelta(hours=12),
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, FillSmallTank)


class TestFillSmallTank(unittest.TestCase):
  def test_if_large_tank_is_empty_go_fill_it(self):
    context = context_factory(
      large_tank=FakeTank(TankLevel.EMPTY),
      small_tank=FakeTank(TankLevel.EMPTY),
      current_state=FillSmallTank,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, FillLargeTank)

  def test_if_small_tank_is_full_go_idle(self):
    context = context_factory(
      large_tank=FakeTank(TankLevel.FULL),
      small_tank=FakeTank(TankLevel.FULL),
      current_state=FillSmallTank,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, SmallTankInUse)

  def test_if_small_tank_is_not_full_stay_there(self):
    context = context_factory(
      large_tank=FakeTank(TankLevel.FULL),
      small_tank=FakeTank(TankLevel.MEDIUM),
      current_state=FillSmallTank,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, context.current_state)


class TestSmallTankInUse(unittest.TestCase):
  def test_if_large_tank_is_empty_go_fill_it(self):
    context = context_factory(
      large_tank=FakeTank(TankLevel.EMPTY),
      small_tank=FakeTank(TankLevel.FULL),
      current_state=SmallTankInUse,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, FillLargeTank)

  def test_if_small_tank_is_empty_go_fill_it(self):
    context = context_factory(
      large_tank=FakeTank(TankLevel.FULL),
      small_tank=FakeTank(TankLevel.EMPTY),
      current_state=SmallTankInUse,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, FillSmallTank)

  def test_if_small_tank_is_not_empty_stay_there(self):
    context = context_factory(
      large_tank=FakeTank(TankLevel.FULL),
      small_tank=FakeTank(TankLevel.MEDIUM),
      current_state=SmallTankInUse,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, context.current_state)


class TestGPIOTank(unittest.TestCase):
  @typing.no_type_check
  def test_low_floater_and_high_floater_high(self):
    tank = GPIOTank(
      low_floater_pin="BOARD11",
      high_floater_pin="BOARD12",
    )
    tank._low_floater.pin.drive_high()
    tank._high_floater.pin.drive_high()
    self.assertEqual(tank.level, TankLevel.EMPTY)

  @typing.no_type_check
  def test_low_floater_low_and_high_floater_high(self):
    tank = GPIOTank(
      low_floater_pin="BOARD11",
      high_floater_pin="BOARD12",
    )
    tank._low_floater.pin.drive_low()
    tank._high_floater.pin.drive_high()
    self.assertEqual(tank.level, TankLevel.MEDIUM)

  @typing.no_type_check
  def test_low_floater_low_and_high_floater_low(self):
    tank = GPIOTank(
      low_floater_pin="BOARD11",
      high_floater_pin="BOARD12",
    )
    tank._low_floater.pin.drive_low()
    tank._high_floater.pin.drive_low()
    self.assertEqual(tank.level, TankLevel.FULL)


class TestGPIOPump(unittest.TestCase):
  @typing.no_type_check
  def test_pump_activated(self):
    pump = GPIOPump(pin="BOARD13")
    pump.activate()
    self.assertTrue(pump._pump.is_active)

  @typing.no_type_check
  def test_pump_deactivated(self):
    pump = GPIOPump(pin="BOARD13")
    pump.activate()
    pump.deactivate()
    self.assertFalse(pump._pump.is_active)


class TestContext(unittest.TestCase):
  def test_check_does_nothing_if_state_does_not_change(self):
    activation_time = datetime.now() - timedelta(hours=6)
    context = context_factory(
      well=well_factory(),
      current_state=FillWell,
      state_activated_at=activation_time,
    )
    context.check()
    self.assertEqual(context.current_state, FillWell)
    self.assertEqual(context.state_activated_at, activation_time)

  def test_check_updates_state_and_activation_time(self):
    with patch("dolianova.datetime") as mock_datetime:
      # Freeze time.
      mock_now = datetime.now()
      mock_datetime.now.return_value = mock_now
      context = context_factory(
        well=well_factory(level=100),
        current_state=FillWell,
        state_activated_at=mock_now - timedelta(hours=6),
      )
      context.check()
      self.assertEqual(context.current_state, FillLargeTank)
      self.assertEqual(context.state_activated_at, mock_now)

  def test_check_updates_state_multiple_times(self):
    # Example: FillSmallTank -> FillLargeTank -> FillWell in one go.
    context = context_factory(
      well=well_factory(level=0),
      large_tank=FakeTank(TankLevel.EMPTY),
      small_tank=FakeTank(TankLevel.MEDIUM),
      current_state=FillSmallTank,
    )
    context.check()
    self.assertEqual(context.current_state, FillWell)

  def test_action_calls_current_state(self):
    class FakeState(State):
      action_called = False

      @typing.override
      @staticmethod
      def check(context: Context) -> type[State]:
        return FakeState

      @typing.override
      @staticmethod
      def action(context: Context) -> None:
        FakeState.action_called = True

    context = context_factory(current_state=FakeState)
    self.assertFalse(FakeState.action_called)
    context.action()
    self.assertTrue(FakeState.action_called)

  def test_context_connects_pump_with_well(self):
    with patch("dolianova.datetime") as mock_datetime:
      # Freeze time.
      mock_now = datetime.now()
      mock_datetime.now.return_value = mock_now
      context = context_factory(
        well=well_factory(
          level=100,
          empty_period=timedelta(hours=1),
          last_update=mock_now,
        ),
        well_to_large_tank_pump=Pump(),
        current_state=FillLargeTank,
      )
      # This activates the well_to_large_tank_pump.
      context.action()
      mock_now += timedelta(minutes=30)
      mock_datetime.now.return_value = mock_now
      self.assertEqual(context.well.level, 50)

  @typing.no_type_check
  def test_from_settings_and_measures(self):
    settings = settings_factory()
    measures = measures_factory(
      time=datetime.now() - timedelta(minutes=30),
      well_level=25,
      large_tank_level=TankLevel.MEDIUM,
      small_tank_level=TankLevel.FULL,
      well_to_large_tank_pump_active=False,
      lower_to_small_tank_pump_active=True,
      current_state=FillSmallTank,
      state_activated_at=datetime.now() - timedelta(hours=6),
    )
    context = Context.from_settings_and_measures(settings, measures)
    # Measure time was 30 minutes ago. The well level should be 25 + 50,
    # because it fill_period is 1 hour.
    self.assertEqual(context.well.level, measures.well_level + 50)
    self.assertEqual(context.well.fill_period, settings.fill_period)
    self.assertEqual(context.well.empty_period, settings.empty_period)
    self.assertEqual(context.settle_time, settings.settle_time)
    self.assertIsInstance(context.large_tank, GPIOTank)
    self.assertEqual(
      context.large_tank._low_floater.pin.info.name,
      settings.large_tank_low_floater_pin,
    )
    self.assertEqual(
      context.large_tank._high_floater.pin.info.name,
      settings.large_tank_high_floater_pin,
    )
    self.assertIsInstance(context.small_tank, GPIOTank)
    self.assertEqual(
      context.small_tank._low_floater.pin.info.name,
      settings.small_tank_low_floater_pin,
    )
    self.assertEqual(
      context.small_tank._high_floater.pin.info.name,
      settings.small_tank_high_floater_pin,
    )
    self.assertIsInstance(context.well_to_large_tank_pump, GPIOPump)
    self.assertEqual(
      context.well_to_large_tank_pump._pump.pin.info.name,
      settings.well_to_large_tank_pump_pin,
    )
    self.assertIsInstance(context.lower_to_small_tank_pump, GPIOPump)
    self.assertEqual(
      context.lower_to_small_tank_pump._pump.pin.info.name,
      settings.lower_to_small_tank_pump_pin,
    )
    self.assertEqual(context.current_state, FillSmallTank)
    self.assertEqual(context.state_activated_at, measures.state_activated_at)


class TestMeasures(unittest.TestCase):
  def test_measures_from_context(self):
    with patch("dolianova.datetime") as mock_datetime:
      # Freeze time.
      mock_now = datetime.now()
      mock_datetime.now.return_value = mock_now
      context = Context(
        well=well_factory(level=87),
        large_tank=FakeTank(TankLevel.MEDIUM),
        small_tank=FakeTank(TankLevel.FULL),
        well_to_large_tank_pump=Pump(),
        lower_to_small_tank_pump=Pump(),
        settle_time=timedelta(hours=12),
        current_state=FillSmallTank,
        state_activated_at=mock_now,
      )
      # This activates the lower_to_small_tank_pump,
      # because FillSmallTank is the current state.
      context.action()
      measures = context.measures()
      self.assertEqual(
        measures,
        measures_factory(
          time=mock_now,
          well_level=87,
          large_tank_level=TankLevel.MEDIUM,
          small_tank_level=TankLevel.FULL,
          well_to_large_tank_pump_active=False,
          lower_to_small_tank_pump_active=True,
          current_state=FillSmallTank,
          state_activated_at=mock_now,
        ),
      )
      # time is not part of the above comparison.
      self.assertEqual(measures.time, mock_now)

  def test_serialization_and_copy(self):
    measures = measures_factory(
      time=datetime(2024, 1, 1, 12, 0, 0),
      well_level=87,
      large_tank_level=TankLevel.MEDIUM,
      small_tank_level=TankLevel.FULL,
      well_to_large_tank_pump_active=False,
      lower_to_small_tank_pump_active=True,
      current_state=FillSmallTank,
      state_activated_at=datetime(2024, 1, 1, 12, 0, 0),
    )
    # Copy happens by serialization and deserialization.
    self.assertEqual(measures.copy(), measures)
    self.assertEqual(measures.copy().time, measures.time)


class TestSettings(unittest.TestCase):
  def test_serialization(self):
    settings = settings_factory()
    self.assertEqual(
      Settings.deserialize(settings.serialize()),
      settings,
    )


class TestHistory(unittest.TestCase):
  def test_history_copies_measures(self):
    measures = measures_factory(
      time=datetime(2024, 1, 1, 12, 0, 0),
      well_level=87,
      large_tank_level=TankLevel.MEDIUM,
      small_tank_level=TankLevel.FULL,
      well_to_large_tank_pump_active=False,
      lower_to_small_tank_pump_active=True,
      current_state=FillSmallTank,
      state_activated_at=datetime(2024, 1, 1, 12, 0, 0),
    )
    history = History()
    history.add(measures)
    self.assertDictEqual(history.measures, {measures.time: measures})
    # Check that the measures object is copied.
    self.assertIsNot(history.measures[measures.time], measures)

  def test_history_works(self):
    measures = measures_factory(
      time=datetime(2024, 1, 1, 12, 0, 0),
      well_level=87,
      large_tank_level=TankLevel.MEDIUM,
      small_tank_level=TankLevel.FULL,
      well_to_large_tank_pump_active=False,
      lower_to_small_tank_pump_active=True,
      current_state=FillSmallTank,
      state_activated_at=datetime(2024, 1, 1, 12, 0, 0),
    )
    history = History()
    history.add(measures)
    self.assertEqual(history.measures, {measures.time: measures})
    new_measures = measures.copy()
    new_measures.well_level = 88
    history.add(new_measures)
    self.assertEqual(
      history.measures,
      {
        measures.time: measures,
        new_measures.time: new_measures,
      },
    )

  def test_history_does_not_repeat(self):
    measures = measures_factory(
      time=datetime(2024, 1, 1, 12, 0, 0),
      well_level=87,
      large_tank_level=TankLevel.MEDIUM,
      small_tank_level=TankLevel.FULL,
      well_to_large_tank_pump_active=False,
      lower_to_small_tank_pump_active=True,
      current_state=FillSmallTank,
      state_activated_at=datetime(2024, 1, 1, 12, 0, 0),
    )
    history = History()
    history.add(measures)
    self.assertEqual(history.measures, {measures.time: measures})
    history.add(measures)
    # Exact same measure: it should not be added.
    self.assertEqual(history.measures, {measures.time: measures})
    old_time = measures.time
    measures.time = datetime(2024, 1, 1, 12, 0, 1)
    history.add(measures)
    # Different time, but same otherwise: do nothing.
    self.assertEqual(history.measures, {old_time: measures})
    self.assertNotEqual(history.measures[old_time].time, measures.time)

  def test_history_serialization(self):
    measures = measures_factory(
      time=datetime(2024, 1, 1, 12, 0, 0),
      well_level=87,
      large_tank_level=TankLevel.MEDIUM,
      small_tank_level=TankLevel.FULL,
      well_to_large_tank_pump_active=False,
      lower_to_small_tank_pump_active=True,
      current_state=FillSmallTank,
      state_activated_at=datetime(2024, 1, 1, 12, 0, 0),
    )
    history = History()
    history.add(measures)
    self.assertEqual(
      History.deserialize(history.serialize()),
      history,
    )


def assert_is_file(path: str) -> None:
  if not pl.Path(path).resolve().is_file():
    raise AssertionError("File does not exist: %s" % str(path))


class TestController(unittest.TestCase):
  def setUp(self) -> None:
    # Create directory to store temporary files.
    pl.Path("/tmp/dolianova_tests").mkdir(exist_ok=True)

  def tearDown(self) -> None:
    try:
      # Remove directory even if it is not empty.
      shutil.rmtree("/tmp/dolianova_tests")
    except Exception:
      pass

  def test_controller_loads_settings(self):
    controller = Controller(
      settings_file="settings.json",
      measures_file="/tmp/dolianova_tests/measures.json",
      history_file="/tmp/dolianova_tests/history.json",
    )
    controller.load()
    self.assertIsInstance(controller.context, Context)

  def test_controller_run_writes_measures_and_history(self):
    controller = Controller(
      settings_file="settings.json",
      measures_file="/tmp/dolianova_tests/measures.json",
      history_file="/tmp/dolianova_tests/history.json",
    )
    controller.load()
    controller.run()
    assert_is_file("/tmp/dolianova_tests/measures.json")
    assert_is_file("/tmp/dolianova_tests/history.json")

  def test_controller_runs_through_the_states(self):
    # This only simulates the first 5 hours of the process.
    with patch("dolianova.datetime", wraps=datetime) as mock_datetime:
      # Freeze time.
      mock_now = datetime.now()
      mock_datetime.now.return_value = mock_now

      controller = Controller(
        settings_file="settings.json",
        measures_file="/tmp/dolianova_tests/measures.json",
        history_file="/tmp/dolianova_tests/history.json",
      )
      controller.load()

      # For the first 5 hours, wait until the well is full.
      controller.run()
      time1 = mock_now
      measures1 = controller.context.measures()
      self.assertEqual(controller.context.current_state, FillWell)
      self.assertEqual(controller.history.measures, {time1: measures1})
      self.assertEqual(measures1.well_level, 0)

      # Calling run for the first 180 seconds now should not add anything to the history.
      mock_now += timedelta(seconds=179)
      mock_datetime.now.return_value = mock_now
      controller.run()
      self.assertEqual(controller.context.current_state, FillWell)
      self.assertEqual(controller.history.measures, {time1: measures1})

      # Calling run now will add a new measure to the history (level goes from 0 to 1).
      mock_now += timedelta(seconds=1)
      mock_datetime.now.return_value = mock_now
      controller.run()
      time2 = mock_now
      measures2 = controller.context.measures()
      self.assertEqual(controller.context.current_state, FillWell)
      self.assertEqual(
        controller.history.measures, {time1: measures1, time2: measures2}
      )
      self.assertEqual(measures2.well_level, 1)

      mock_now += timedelta(minutes=56)
      mock_datetime.now.return_value = mock_now
      controller.run()
      time3 = mock_now
      measures3 = controller.context.measures()
      self.assertEqual(controller.context.current_state, FillWell)
      self.assertEqual(
        controller.history.measures,
        {time1: measures1, time2: measures2, time3: measures3},
      )

      mock_now += timedelta(hours=4)
      mock_datetime.now.return_value = mock_now
      controller.run()
      time4 = mock_now
      measures4 = controller.context.measures()
      self.assertEqual(controller.context.current_state, FillWell)

      # After 5 hours, the well is full, so fill the lower tank.
      mock_now += timedelta(minutes=1)
      mock_datetime.now.return_value = mock_now
      controller.run()
      time5 = mock_now
      measures5 = controller.context.measures()
      self.assertEqual(measures5.current_state, FillLargeTank)
      self.assertEqual(measures5.large_tank_level, TankLevel.EMPTY)
      self.assertEqual(measures5.well_level, 100)
      self.assertDictEqual(
        controller.history.measures,
        {
          time1: measures1,
          time2: measures2,
          time3: measures3,
          time4: measures4,
          time5: measures5,
        },
      )

  def test_when_controller_stops_well_keeps_filling(self):
    with patch("dolianova.datetime", wraps=datetime) as mock_datetime:
      # Freeze time.
      mock_now = datetime.now()
      mock_datetime.now.return_value = mock_now

      controller = Controller(
        settings_file="settings.json",
        measures_file="/tmp/dolianova_tests/measures.json",
        history_file="/tmp/dolianova_tests/history.json",
      )
      controller.load()

      # First run will write the measures and history files.
      controller.run()

      # After 2.5 hours, the well is half full.
      mock_now += timedelta(hours=2.5)
      mock_datetime.now.return_value = mock_now
      controller.run()
      self.assertEqual(controller.context.well.level, 50)

      # Now let's simulate a restart by creating a new controller 2.5 hours later.
      mock_now += timedelta(hours=2.5)
      mock_datetime.now.return_value = mock_now

      # Copy the measures and history files to a new location to simulate a restart.
      pl.Path("/tmp/dolianova_tests/measures.json").replace(
        "/tmp/dolianova_tests/measures2.json"
      )
      pl.Path("/tmp/dolianova_tests/history.json").replace(
        "/tmp/dolianova_tests/history2.json"
      )

      # Let's get the measures from the current controller (for comparison).
      controller.run()
      measures = controller.context.measures()

      # We need to release the GPIO pins to create a new controller.
      Device.pin_factory.reset()  # type: ignore

      controller2 = Controller(
        settings_file="settings.json",
        measures_file="/tmp/dolianova_tests/measures2.json",
        history_file="/tmp/dolianova_tests/history2.json",
      )
      controller2.load()
      controller2.run()
      # We should be in FillLargeTank state.
      self.assertEqual(controller2.context.current_state, FillLargeTank)
      # The measures should be equal because both controllers would
      # only have to wait for the well to fill up.
      self.assertEqual(controller2.context.well.level, 100)
      self.assertEqual(measures.well_level, 100)

  def test_when_controller_stops_pumps_go_off(self):
    with patch("dolianova.datetime", wraps=datetime) as mock_datetime:
      # Freeze time.
      mock_now = datetime.now()
      mock_datetime.now.return_value = mock_now

      controller = Controller(
        settings_file="settings.json",
        measures_file="/tmp/dolianova_tests/measures.json",
        history_file="/tmp/dolianova_tests/history.json",
      )
      controller.load()

      # First run will write the measures and history files.
      controller.run()

      # After 5 hours, we change the state to FillLargeTank.
      mock_now += timedelta(hours=5)
      mock_datetime.now.return_value = mock_now
      controller.run()

      # Now let's simulate a restart by creating a new controller 10 minutes later.
      mock_now += timedelta(minutes=10)
      mock_datetime.now.return_value = mock_now

      # Move the measures and history files to a new location to simulate a restart.
      pl.Path("/tmp/dolianova_tests/measures.json").replace(
        "/tmp/dolianova_tests/measures2.json"
      )
      pl.Path("/tmp/dolianova_tests/history.json").replace(
        "/tmp/dolianova_tests/history2.json"
      )

      # Let's get the measures from the current controller (for comparison).
      # This also recreates the measures.json and history.json files.
      controller.run()
      measures = controller.context.measures()

      # We need to release the GPIO pins to create a new controller.
      Device.pin_factory.reset()  # type: ignore
      # From now on, we can't call controller methods because the pins are reset.

      controller2 = Controller(
        settings_file="settings.json",
        measures_file="/tmp/dolianova_tests/measures2.json",
        history_file="/tmp/dolianova_tests/history2.json",
      )
      controller2.load()
      controller2.run()
      # We should be in FillLargeTank state.
      self.assertEqual(controller2.context.current_state, FillLargeTank)
      # The measures should be different because if controller did not stop,
      # the well would not be full anymore.
      self.assertEqual(controller2.context.well.level, 100)
      self.assertEqual(measures.well_level, 66)


if __name__ == "__main__":
  unittest.main()
