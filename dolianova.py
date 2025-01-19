from __future__ import annotations

import pathlib as pl
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from time import sleep
from typing import TypeGuard, override

import fire  # type: ignore
import json5 as json  # type: ignore
from gpiozero import LED, Button  # type: ignore

type PinID = int | str


class TankLevel(StrEnum):
  EMPTY = "empty"
  MEDIUM = "medium"
  FULL = "full"


class PumpListener(ABC):
  @abstractmethod
  def pump_activated(self) -> None:
    pass

  @abstractmethod
  def pump_deactivated(self) -> None:
    pass


class Well(PumpListener):
  def __init__(
    self,
    *,
    # Settings
    fill_period: timedelta,
    empty_period: timedelta,
    # State
    level: int,
    last_update: datetime,
  ):
    assert 0 <= level <= 100
    self._level: float = level / 100.0
    self.fill_period = fill_period
    self.empty_period = empty_period
    self.last_update = last_update
    # The well has to be initialized with the pump off.
    self.pump_active = False
    self._update_level()

  @override
  def pump_activated(self):
    if self.pump_active:
      return
    self._update_level()
    self.pump_active = True

  @override
  def pump_deactivated(self):
    if not self.pump_active:
      return
    self._update_level()
    self.pump_active = False

  @property
  def level(self) -> int:
    self._update_level()
    return int(100.0 * self._level)

  def _update_level(self) -> None:
    now = datetime.now()
    delta_time = now - self.last_update
    if self.pump_active:
      self._level -= delta_time / self.empty_period
    else:
      self._level += delta_time / self.fill_period
    self._level = max(0.0, min(1.0, self._level))
    self.last_update = now


class Tank(ABC):
  @property
  @abstractmethod
  def level(self) -> TankLevel:
    pass


class FakeTank(Tank):
  def __init__(self, level: TankLevel) -> None:
    self._level = level

  def set_level(self, level: TankLevel) -> None:
    self._level = level

  @property
  def level(self) -> TankLevel:
    return self._level


class GPIOTank(Tank):
  def __init__(self, low_floater_pin: PinID, high_floater_pin: PinID) -> None:
    self._low_floater: Button = Button(low_floater_pin)
    self._high_floater: Button = Button(high_floater_pin)

  @property
  def level(self) -> TankLevel:
    if not self._low_floater.is_active:
      return TankLevel.EMPTY
    if not self._high_floater.is_active:
      return TankLevel.MEDIUM
    return TankLevel.FULL


class Pump:
  def __init__(self) -> None:
    self.listeners: list[PumpListener] = []
    self._active: bool = False

  def add_listener(self, listener: PumpListener) -> None:
    self.listeners.append(listener)

  def activate(self) -> None:
    self._active = True
    for listener in self.listeners:
      listener.pump_activated()

  def deactivate(self) -> None:
    self._active = False
    for listener in self.listeners:
      listener.pump_deactivated()

  @property
  def active(self) -> bool:
    return self._active


class GPIOPump(Pump):
  def __init__(self, pin: PinID) -> None:
    super().__init__()
    self._pump = LED(pin)

  def activate(self) -> None:
    self._pump.on()
    super().activate()

  def deactivate(self) -> None:
    self._pump.off()
    super().deactivate()


@dataclass
class Context:
  well: Well
  lower_tank: Tank
  upper_tank: Tank
  well_to_lower_tank_pump: Pump
  lower_to_upper_tank_pump: Pump
  settle_time: timedelta
  current_state: type[State]
  state_activated_at: datetime

  def __post_init__(self) -> None:
    self.well_to_lower_tank_pump.add_listener(self.well)

  def check(self):
    new_state = self.current_state.check(self)
    while new_state != self.current_state:
      self.current_state = new_state
      self.state_activated_at = datetime.now()
      new_state = self.current_state.check(self)

  def action(self) -> None:
    self.current_state.action(self)

  @property
  def same_state_since(self) -> timedelta:
    return datetime.now() - self.state_activated_at

  def measures(self) -> Measures:
    return Measures(
      time=datetime.now(),
      well_level=self.well.level,
      lower_tank_level=self.lower_tank.level,
      upper_tank_level=self.upper_tank.level,
      well_to_lower_tank_pump_active=self.well_to_lower_tank_pump.active,
      lower_to_upper_tank_pump_active=self.lower_to_upper_tank_pump.active,
      current_state=self.current_state,
      state_activated_at=self.state_activated_at,
    )

  @staticmethod
  def from_settings_and_measures(settings: Settings, measures: Measures) -> Context:
    well = Well(
      fill_period=settings.fill_period,
      empty_period=settings.empty_period,
      level=measures.well_level,
      last_update=measures.time,
    )
    lower_tank = GPIOTank(
      low_floater_pin=settings.lower_tank_low_floater_pin,
      high_floater_pin=settings.lower_tank_high_floater_pin,
    )
    upper_tank = GPIOTank(
      low_floater_pin=settings.upper_tank_low_floater_pin,
      high_floater_pin=settings.upper_tank_high_floater_pin,
    )
    well_to_lower_tank_pump = GPIOPump(settings.well_to_lower_tank_pump_pin)
    lower_to_upper_tank_pump = GPIOPump(settings.lower_to_upper_tank_pump_pin)
    return Context(
      well=well,
      lower_tank=lower_tank,
      upper_tank=upper_tank,
      well_to_lower_tank_pump=well_to_lower_tank_pump,
      lower_to_upper_tank_pump=lower_to_upper_tank_pump,
      settle_time=settings.settle_time,
      current_state=measures.current_state,
      state_activated_at=measures.state_activated_at,
    )


class State(ABC):
  @staticmethod
  @abstractmethod
  def check(context: Context) -> type[State]:
    pass

  @staticmethod
  @abstractmethod
  def action(context: Context) -> None:
    pass


class FillWell(State):
  @override
  @staticmethod
  def check(context: Context) -> type[State]:
    if context.well.level == 100:
      return FillLowerTank
    return FillWell

  @override
  @staticmethod
  def action(context: Context) -> None:
    context.well_to_lower_tank_pump.deactivate()
    context.lower_to_upper_tank_pump.deactivate()


class FillLowerTank(State):
  @override
  @staticmethod
  def check(context: Context) -> type[State]:
    if context.lower_tank.level == TankLevel.FULL:
      return SettleLowerTank
    if context.well.level == 0:
      return FillWell
    return FillLowerTank

  @override
  @staticmethod
  def action(context: Context) -> None:
    context.well_to_lower_tank_pump.activate()
    context.lower_to_upper_tank_pump.deactivate()


class SettleLowerTank(State):
  @override
  @staticmethod
  def check(context: Context) -> type[State]:
    if context.lower_tank.level != TankLevel.FULL:
      return FillLowerTank
    if context.same_state_since > context.settle_time:
      return FillUpperTank
    return SettleLowerTank

  @override
  @staticmethod
  def action(context: Context) -> None:
    context.well_to_lower_tank_pump.deactivate()
    context.lower_to_upper_tank_pump.deactivate()


class FillUpperTank(State):
  @override
  @staticmethod
  def check(context: Context) -> type[State]:
    if context.lower_tank.level == TankLevel.EMPTY:
      return FillLowerTank
    if context.upper_tank.level == TankLevel.FULL:
      return UpperTankInUse
    return FillUpperTank

  @override
  @staticmethod
  def action(context: Context) -> None:
    context.well_to_lower_tank_pump.deactivate()
    context.lower_to_upper_tank_pump.activate()


class UpperTankInUse(State):
  @override
  @staticmethod
  def check(context: Context) -> type[State]:
    if context.lower_tank.level == TankLevel.EMPTY:
      return FillLowerTank
    if context.upper_tank.level == TankLevel.EMPTY:
      return FillUpperTank
    return UpperTankInUse

  @override
  @staticmethod
  def action(context: Context) -> None:
    context.well_to_lower_tank_pump.deactivate()
    context.lower_to_upper_tank_pump.deactivate()


@dataclass
class Measures:
  time: datetime = field(compare=False)
  well_level: int
  lower_tank_level: TankLevel
  upper_tank_level: TankLevel
  well_to_lower_tank_pump_active: bool
  lower_to_upper_tank_pump_active: bool
  current_state: type[State]
  state_activated_at: datetime

  @staticmethod
  def initial() -> Measures:
    return Measures(
      time=datetime.now(),
      well_level=0,
      lower_tank_level=TankLevel.EMPTY,
      upper_tank_level=TankLevel.EMPTY,
      well_to_lower_tank_pump_active=False,
      lower_to_upper_tank_pump_active=False,
      current_state=FillWell,
      state_activated_at=datetime.now(),
    )

  @staticmethod
  def deserialize(s: str) -> Measures:
    data: dict[str, object] = json.loads(s)  # type: ignore
    assert isinstance(data["time"], str)
    assert isinstance(data["well_level"], int)
    assert isinstance(data["lower_tank_level"], str)
    assert isinstance(data["upper_tank_level"], str)
    assert isinstance(data["well_to_lower_tank_pump_active"], bool)
    assert isinstance(data["lower_to_upper_tank_pump_active"], bool)
    assert isinstance(data["current_state"], str)
    assert isinstance(data["state_activated_at"], str)
    return Measures(
      time=datetime.fromisoformat(data["time"]),
      well_level=data["well_level"],
      lower_tank_level=TankLevel(data["lower_tank_level"]),
      upper_tank_level=TankLevel(data["upper_tank_level"]),
      well_to_lower_tank_pump_active=bool(data["well_to_lower_tank_pump_active"]),
      lower_to_upper_tank_pump_active=bool(data["lower_to_upper_tank_pump_active"]),
      current_state=globals()[data["current_state"]],
      state_activated_at=datetime.fromisoformat(data["state_activated_at"]),
    )

  def serialize(self) -> str:
    return json.dumps(  # type: ignore
      {
        "time": self.time.isoformat(),
        "well_level": self.well_level,
        "lower_tank_level": self.lower_tank_level.value,
        "upper_tank_level": self.upper_tank_level.value,
        "well_to_lower_tank_pump_active": self.well_to_lower_tank_pump_active,
        "lower_to_upper_tank_pump_active": self.lower_to_upper_tank_pump_active,
        "current_state": self.current_state.__name__,
        "state_activated_at": self.state_activated_at.isoformat(),
      },
      indent=2,
    )

  def copy(self):
    return Measures.deserialize(self.serialize())


def is_pin_id(value: object) -> TypeGuard[PinID]:
  return isinstance(value, int) or isinstance(value, str)


def is_number(value: object) -> TypeGuard[int | float]:
  return isinstance(value, int) or isinstance(value, float)


@dataclass
class Settings:
  fill_period: timedelta
  empty_period: timedelta
  settle_time: timedelta
  lower_tank_low_floater_pin: PinID
  lower_tank_high_floater_pin: PinID
  upper_tank_low_floater_pin: PinID
  upper_tank_high_floater_pin: PinID
  well_to_lower_tank_pump_pin: PinID
  lower_to_upper_tank_pump_pin: PinID

  @staticmethod
  def deserialize(s: str) -> Settings:
    data: dict[str, object] = json.loads(s)  # type: ignore
    assert is_number(data["fill_period"])
    assert is_number(data["empty_period"])
    assert is_number(data["settle_time"])
    assert is_pin_id(data["lower_tank_low_floater_pin"])
    assert is_pin_id(data["lower_tank_high_floater_pin"])
    assert is_pin_id(data["upper_tank_low_floater_pin"])
    assert is_pin_id(data["upper_tank_high_floater_pin"])
    assert is_pin_id(data["well_to_lower_tank_pump_pin"])
    assert is_pin_id(data["lower_to_upper_tank_pump_pin"])
    return Settings(
      fill_period=timedelta(seconds=data["fill_period"]),
      empty_period=timedelta(seconds=data["empty_period"]),
      settle_time=timedelta(seconds=data["settle_time"]),
      lower_tank_low_floater_pin=data["lower_tank_low_floater_pin"],
      lower_tank_high_floater_pin=data["lower_tank_high_floater_pin"],
      upper_tank_low_floater_pin=data["upper_tank_low_floater_pin"],
      upper_tank_high_floater_pin=data["upper_tank_high_floater_pin"],
      well_to_lower_tank_pump_pin=data["well_to_lower_tank_pump_pin"],
      lower_to_upper_tank_pump_pin=data["lower_to_upper_tank_pump_pin"],
    )

  def serialize(self) -> str:
    return json.dumps(  # type: ignore
      {
        "fill_period": self.fill_period.total_seconds(),
        "empty_period": self.empty_period.total_seconds(),
        "settle_time": self.settle_time.total_seconds(),
        "lower_tank_low_floater_pin": self.lower_tank_low_floater_pin,
        "lower_tank_high_floater_pin": self.lower_tank_high_floater_pin,
        "upper_tank_low_floater_pin": self.upper_tank_low_floater_pin,
        "upper_tank_high_floater_pin": self.upper_tank_high_floater_pin,
        "well_to_lower_tank_pump_pin": self.well_to_lower_tank_pump_pin,
        "lower_to_upper_tank_pump_pin": self.lower_to_upper_tank_pump_pin,
      },
      indent=2,
    )


@dataclass
class History:
  measures: dict[datetime, Measures] = field(default_factory=dict)

  def add(self, measures: Measures) -> None:
    # If new measures are the same as the last one, do nothing.
    # Except for the time, of course.
    if len(self.measures) and next(reversed(self.measures.values())) == measures:
      pass
    else:
      self.measures[measures.time] = measures.copy()

  def serialize(self) -> str:
    return json.dumps({t.isoformat(): m.serialize() for t, m in self.measures.items()})  # type: ignore

  @staticmethod
  def deserialize(s: str) -> History:
    data: dict[str, str] = json.loads(s)  # type: ignore
    measures = {
      datetime.fromisoformat(t): Measures.deserialize(m) for t, m in data.items()
    }
    return History(measures)


class Controller:
  def __init__(
    self,
    settings_file: str,
    measures_file: str,
    history_file: str,
  ) -> None:
    self.settings_file = settings_file
    self.measures_file = measures_file
    self.history_file = history_file

    self.context: Context
    self.history: History

  def load(self) -> None:
    if not pl.Path(self.settings_file).exists():
      raise FileNotFoundError(f"Settings file {self.settings_file} not found.")
    with open(self.settings_file) as f:
      settings = Settings.deserialize(f.read())
    
    # Load measures and history if they exist.
    if pl.Path(self.measures_file).exists():
      with open(self.measures_file) as f:
        measures = Measures.deserialize(f.read())
    else:
      measures = Measures.initial()
    if pl.Path(self.history_file).exists():
      with open(self.history_file) as f:
        self.history = History.deserialize(f.read())
    else:
      self.history = History()

    self.context = Context.from_settings_and_measures(settings, measures)

  def run(self) -> None:
    history_length = len(self.history.measures)
    self.context.check()
    self.context.action()
    measures = self.context.measures()
    self.history.add(measures)
    # Save measures and history if they have changed.
    # TODO: also every minute.
    # TODO: make atomic.
    if len(self.history.measures) > history_length:
      with open(self.measures_file, "w") as f:
        f.write(measures.serialize())
      with open(self.history_file, "w") as f:
        f.write(self.history.serialize())


def main(
  *,
  settings_file: str = "settings.json",
  measures_file: str = "measures.json",
  history_file: str = "history.json",
) -> None:
  pass


if __name__ == "__main__":
  fire.Fire(main)  # type: ignore
