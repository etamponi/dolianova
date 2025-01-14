import typing
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from dolianova import (
  Context,
  Controller,
  FakeTank,
  FillLowerTank,
  FillUpperTank,
  FillWell,
  GPIOPump,
  GPIOTank,
  History,
  Measures,
  Pump,
  Settings,
  SettleLowerTank,
  State,
  Tank,
  TankLevel,
  UpperTankInUse,
  Well,
)

from gpiozero import Device  # type: ignore
from gpiozero.pins.mock import MockFactory  # type: ignore

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
  lower_tank: Tank | None = None,
  upper_tank: Tank | None = None,
  well_to_lower_tank_pump: Pump | None = None,
  lower_to_upper_tank_pump: Pump | None = None,
  settle_time: timedelta | None = None,
  current_state: type[State] | None = None,
  state_activated_at: datetime | None = None,
) -> Context:
  context = Context(
    well=well or well_factory(),
    lower_tank=lower_tank or FakeTank(TankLevel.MEDIUM),
    upper_tank=upper_tank or FakeTank(TankLevel.MEDIUM),
    well_to_lower_tank_pump=well_to_lower_tank_pump or Pump(),
    lower_to_upper_tank_pump=lower_to_upper_tank_pump or Pump(),
    settle_time=settle_time or timedelta(hours=12),
    current_state=current_state or FillWell,
    state_activated_at=state_activated_at or datetime.now(),
  )
  return context


def measures_factory(
  time: datetime = datetime.now(),
  well_level: int = 50,
  lower_tank_level: TankLevel = TankLevel.MEDIUM,
  upper_tank_level: TankLevel = TankLevel.MEDIUM,
  well_to_lower_tank_pump_active: bool = False,
  lower_to_upper_tank_pump_active: bool = False,
  current_state: type[State] = FillWell,
  state_activated_at: datetime = datetime.now(),
) -> Measures:
  return Measures(
    time=time,
    well_level=well_level,
    lower_tank_level=lower_tank_level,
    upper_tank_level=upper_tank_level,
    well_to_lower_tank_pump_active=well_to_lower_tank_pump_active,
    lower_to_upper_tank_pump_active=lower_to_upper_tank_pump_active,
    current_state=current_state,
    state_activated_at=state_activated_at,
  )


class TestFillWell(unittest.TestCase):
  def test_when_well_is_filled_go_fill_lower_tank(self):
    context = context_factory(
      well=well_factory(level=100),
      current_state=FillWell,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, FillLowerTank)

  def test_if_well_is_not_full_stay_there(self):
    context = context_factory(
      well=well_factory(level=50),
      current_state=FillWell,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, context.current_state)


class TestFillLowerTank(unittest.TestCase):
  def test_when_lower_tank_is_full_go_to_settle_lower_tank(self):
    context = context_factory(
      lower_tank=FakeTank(TankLevel.FULL),
      current_state=FillLowerTank,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, SettleLowerTank)

  def test_if_lower_tank_is_not_full_stay_there(self):
    lower_tank = FakeTank(TankLevel.MEDIUM)
    context = context_factory(
      lower_tank=lower_tank,
      current_state=FillLowerTank,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, context.current_state)

    lower_tank.set_level(TankLevel.EMPTY)
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, context.current_state)

  def test_if_well_is_empty_go_fill_well(self):
    context = context_factory(
      well=well_factory(level=0),
      lower_tank=FakeTank(TankLevel.EMPTY),
      current_state=FillLowerTank,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, FillWell)


class TestSettleLowerTank(unittest.TestCase):
  def test_if_lower_tank_is_not_full_go_fill_it(self):
    context = context_factory(
      lower_tank=FakeTank(TankLevel.MEDIUM),
      current_state=SettleLowerTank,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, FillLowerTank)

  def test_if_not_enough_time_elapsed_stay_there(self):
    context = context_factory(
      lower_tank=FakeTank(TankLevel.FULL),
      settle_time=timedelta(hours=12),
      current_state=SettleLowerTank,
      state_activated_at=datetime.now() - timedelta(hours=6),
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, context.current_state)

  def test_if_enough_time_elapsed_go_fill_upper_tank(self):
    context = context_factory(
      lower_tank=FakeTank(TankLevel.FULL),
      settle_time=timedelta(hours=12),
      current_state=SettleLowerTank,
      state_activated_at=datetime.now() - timedelta(hours=12),
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, FillUpperTank)


class TestFillUpperTank(unittest.TestCase):
  def test_if_lower_tank_is_empty_go_fill_it(self):
    context = context_factory(
      lower_tank=FakeTank(TankLevel.EMPTY),
      upper_tank=FakeTank(TankLevel.EMPTY),
      current_state=FillUpperTank,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, FillLowerTank)

  def test_if_upper_tank_is_full_go_idle(self):
    context = context_factory(
      lower_tank=FakeTank(TankLevel.FULL),
      upper_tank=FakeTank(TankLevel.FULL),
      current_state=FillUpperTank,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, UpperTankInUse)

  def test_if_upper_tank_is_not_full_stay_there(self):
    context = context_factory(
      lower_tank=FakeTank(TankLevel.FULL),
      upper_tank=FakeTank(TankLevel.MEDIUM),
      current_state=FillUpperTank,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, context.current_state)


class TestUpperTankInUse(unittest.TestCase):
  def test_if_lower_tank_is_empty_go_fill_it(self):
    context = context_factory(
      lower_tank=FakeTank(TankLevel.EMPTY),
      upper_tank=FakeTank(TankLevel.FULL),
      current_state=UpperTankInUse,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, FillLowerTank)

  def test_if_upper_tank_is_empty_go_fill_it(self):
    context = context_factory(
      lower_tank=FakeTank(TankLevel.FULL),
      upper_tank=FakeTank(TankLevel.EMPTY),
      current_state=UpperTankInUse,
    )
    next_state = context.current_state.check(context)
    self.assertEqual(next_state, FillUpperTank)

  def test_if_upper_tank_is_not_empty_stay_there(self):
    context = context_factory(
      lower_tank=FakeTank(TankLevel.FULL),
      upper_tank=FakeTank(TankLevel.MEDIUM),
      current_state=UpperTankInUse,
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
      self.assertEqual(context.current_state, FillLowerTank)
      self.assertEqual(context.state_activated_at, mock_now)

  def test_check_updates_state_multiple_times(self):
    # Example: FillUpperTank -> FillLowerTank -> FillWell in one go.
    context = context_factory(
      well=well_factory(level=0),
      lower_tank=FakeTank(TankLevel.EMPTY),
      upper_tank=FakeTank(TankLevel.MEDIUM),
      current_state=FillUpperTank,
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
        well_to_lower_tank_pump=Pump(),
        current_state=FillLowerTank,
      )
      # This activates the well_to_lower_tank_pump.
      context.action()
      mock_now += timedelta(minutes=30)
      mock_datetime.now.return_value = mock_now
      self.assertEqual(context.well.level, 50)

  @typing.no_type_check
  def test_from_settings_and_measures(self):
    settings = Settings(
      fill_period=timedelta(hours=1),
      empty_period=timedelta(hours=1),
      settle_time=timedelta(hours=12),
      lower_tank_low_floater_pin="GPIO2",
      lower_tank_high_floater_pin="GPIO3",
      upper_tank_low_floater_pin="GPIO4",
      upper_tank_high_floater_pin="GPIO5",
      well_to_lower_tank_pump_pin="GPIO6",
      lower_to_upper_tank_pump_pin="GPIO7",
    )
    measures = measures_factory(
      time=datetime.now() - timedelta(minutes=30),
      well_level=25,
      lower_tank_level=TankLevel.MEDIUM,
      upper_tank_level=TankLevel.FULL,
      well_to_lower_tank_pump_active=False,
      lower_to_upper_tank_pump_active=True,
      current_state=FillUpperTank,
      state_activated_at=datetime.now() - timedelta(hours=6),
    )
    context = Context.from_settings_and_measures(settings, measures)
    # Measure time was 30 minutes ago. The well level should be 25 + 50,
    # because it fill_period is 1 hour.
    self.assertEqual(context.well.level, measures.well_level + 50)
    self.assertEqual(context.well.fill_period, settings.fill_period)
    self.assertEqual(context.well.empty_period, settings.empty_period)
    self.assertEqual(context.settle_time, settings.settle_time)
    self.assertIsInstance(context.lower_tank, GPIOTank)
    self.assertEqual(
      context.lower_tank._low_floater.pin.info.name,
      settings.lower_tank_low_floater_pin,
    )
    self.assertEqual(
      context.lower_tank._high_floater.pin.info.name,
      settings.lower_tank_high_floater_pin,
    )
    self.assertIsInstance(context.upper_tank, GPIOTank)
    self.assertEqual(
      context.upper_tank._low_floater.pin.info.name,
      settings.upper_tank_low_floater_pin,
    )
    self.assertEqual(
      context.upper_tank._high_floater.pin.info.name,
      settings.upper_tank_high_floater_pin,
    )
    self.assertIsInstance(context.well_to_lower_tank_pump, GPIOPump)
    self.assertEqual(
      context.well_to_lower_tank_pump._pump.pin.info.name,
      settings.well_to_lower_tank_pump_pin,
    )
    self.assertIsInstance(context.lower_to_upper_tank_pump, GPIOPump)
    self.assertEqual(
      context.lower_to_upper_tank_pump._pump.pin.info.name,
      settings.lower_to_upper_tank_pump_pin,
    )
    self.assertEqual(context.current_state, FillUpperTank)
    self.assertEqual(context.state_activated_at, measures.state_activated_at)


class TestMeasures(unittest.TestCase):
  def test_measures_from_context(self):
    with patch("dolianova.datetime") as mock_datetime:
      # Freeze time.
      mock_now = datetime.now()
      mock_datetime.now.return_value = mock_now
      context = Context(
        well=well_factory(level=87),
        lower_tank=FakeTank(TankLevel.MEDIUM),
        upper_tank=FakeTank(TankLevel.FULL),
        well_to_lower_tank_pump=Pump(),
        lower_to_upper_tank_pump=Pump(),
        settle_time=timedelta(hours=12),
        current_state=FillUpperTank,
        state_activated_at=mock_now,
      )
      # This activates the lower_to_upper_tank_pump,
      # because FillUpperTank is the current state.
      context.action()
      measures = context.measures()
      self.assertEqual(
        measures,
        measures_factory(
          time=mock_now,
          well_level=87,
          lower_tank_level=TankLevel.MEDIUM,
          upper_tank_level=TankLevel.FULL,
          well_to_lower_tank_pump_active=False,
          lower_to_upper_tank_pump_active=True,
          current_state=FillUpperTank,
          state_activated_at=mock_now,
        ),
      )
      # time is not part of the above comparison.
      self.assertEqual(measures.time, mock_now)

  def test_serialization(self):
    measures = measures_factory(
      time=datetime(2024, 1, 1, 12, 0, 0),
      well_level=87,
      lower_tank_level=TankLevel.MEDIUM,
      upper_tank_level=TankLevel.FULL,
      well_to_lower_tank_pump_active=False,
      lower_to_upper_tank_pump_active=True,
      current_state=FillUpperTank,
      state_activated_at=datetime(2024, 1, 1, 12, 0, 0),
    )
    self.assertEqual(
      Measures.deserialize(measures.serialize()),
      measures,
    )
    # time is not part of the above comparison.
    self.assertEqual(
      Measures.deserialize(measures.serialize()).time,
      measures.time,
    )


class TestSettings(unittest.TestCase):
  def test_serialization(self):
    settings = Settings(
      fill_period=timedelta(hours=1),
      empty_period=timedelta(hours=1),
      settle_time=timedelta(hours=12),
      lower_tank_low_floater_pin="BOARD11",
      lower_tank_high_floater_pin="BOARD12",
      upper_tank_low_floater_pin="BOARD13",
      upper_tank_high_floater_pin="BOARD14",
      well_to_lower_tank_pump_pin="BOARD15",
      lower_to_upper_tank_pump_pin="BOARD16",
    )
    self.assertEqual(
      Settings.deserialize(settings.serialize()),
      settings,
    )


class TestHistory(unittest.TestCase):
  def test_history_copies_measures(self):
    measures = measures_factory(
      time=datetime(2024, 1, 1, 12, 0, 0),
      well_level=87,
      lower_tank_level=TankLevel.MEDIUM,
      upper_tank_level=TankLevel.FULL,
      well_to_lower_tank_pump_active=False,
      lower_to_upper_tank_pump_active=True,
      current_state=FillUpperTank,
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
      lower_tank_level=TankLevel.MEDIUM,
      upper_tank_level=TankLevel.FULL,
      well_to_lower_tank_pump_active=False,
      lower_to_upper_tank_pump_active=True,
      current_state=FillUpperTank,
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
      lower_tank_level=TankLevel.MEDIUM,
      upper_tank_level=TankLevel.FULL,
      well_to_lower_tank_pump_active=False,
      lower_to_upper_tank_pump_active=True,
      current_state=FillUpperTank,
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
    # Different time, but same otherwise: it should be replaced.
    self.assertEqual(history.measures, {old_time: measures})
    self.assertEqual(history.measures[old_time].time, measures.time)

  def test_history_serialization(self):
    measures = measures_factory(
      time=datetime(2024, 1, 1, 12, 0, 0),
      well_level=87,
      lower_tank_level=TankLevel.MEDIUM,
      upper_tank_level=TankLevel.FULL,
      well_to_lower_tank_pump_active=False,
      lower_to_upper_tank_pump_active=True,
      current_state=FillUpperTank,
      state_activated_at=datetime(2024, 1, 1, 12, 0, 0),
    )
    history = History()
    history.add(measures)
    self.assertEqual(
      History.deserialize(history.serialize()),
      history,
    )


class TestController(unittest.TestCase):
  def test_run_writes_history(self):
    context = context_factory()
    history = History()
    controller = Controller(context, history)
    controller.run()
    self.assertListEqual(list(history.measures.values()), [context.measures()])


if __name__ == "__main__":
  unittest.main()
