import json
import os
from datetime import datetime, timedelta

from flask import Flask, render_template

import dolianova
from dolianova import History, Measures, Settings, State, TankLevel

app = Flask(__name__)


def load_fake_measures(return_none: bool = False) -> Measures | None:
  if return_none:
    return None
  return Measures(
    time=datetime.now() - timedelta(minutes=0),
    well_level=50,
    large_tank_level=TankLevel.FULL,
    small_tank_level=TankLevel.EMPTY,
    well_to_large_tank_pump_active=True,
    lower_to_small_tank_pump_active=False,
    current_state=dolianova.SettleLargeTank,
    state_activated_at=datetime.now() - timedelta(minutes=50),
  )


def load_measures():
  if not os.path.exists("measures.json"):
    return None
  with open("measures.json") as f:
    data = f.read()
    return Measures.deserialize(data)


def load_fake_history(return_none: bool = False) -> History | None:
  if return_none:
    return None
  return History(
    measures={
      datetime.now() - timedelta(minutes=60 - 3 * i): Measures(
        time=datetime.now() - timedelta(minutes=60 - 3 * i),
        well_level=int(100 * (i + 1) / 20),
        large_tank_level=TankLevel.EMPTY if i < 10 else TankLevel.FULL,
        small_tank_level=TankLevel.EMPTY if i > 10 else TankLevel.MEDIUM,
        well_to_large_tank_pump_active=False,
        lower_to_small_tank_pump_active=False,
        current_state=dolianova.FillWell,
        state_activated_at=datetime.now() - timedelta(minutes=60),
      )
      for i in range(20)
    }
  )


def load_history():
  if not os.path.exists("history.json"):
    return None
  try:
    with open("history.json") as f:
      data = f.read()
      return History.deserialize(data)
  except Exception:
    print("Error deserializing history")
    return None


def translate_time(time: datetime) -> str:
  minutes_from_now = int(round((datetime.now() - time).total_seconds() / 60))
  hours = int(abs(minutes_from_now) / 60)
  minutes = abs(minutes_from_now) % 60
  if abs(minutes_from_now) < 1:
    return f"{time.strftime('%Y-%m-%d %H:%M')} (adesso)"
  hours_str = ""
  if hours == 1:
    hours_str = f"{hours} ora e "
  elif hours > 1:
    hours_str = f"{hours} ore e "
  minutes_str = ""
  if minutes == 1:
    minutes_str = f"{minutes} minuto"
  elif minutes > 1:
    minutes_str = f"{minutes} minuti"
  if minutes_from_now == 0:
    return f"{time.strftime('%Y-%m-%d %H:%M')} (adesso)"
  elif minutes_from_now < 0:
    return f"{time.strftime('%Y-%m-%d %H:%M')} (tra {hours_str}{minutes_str})"
  else:
    return f"{time.strftime('%Y-%m-%d %H:%M')} ({hours_str}{minutes_str} fa)"


def translate_level(level: TankLevel) -> str:
  if level == TankLevel.EMPTY:
    return "VUOTO"
  if level == TankLevel.MEDIUM:
    return "MEDIO"
  if level == TankLevel.FULL:
    return "PIENO"
  return "SCONOSCIUTO"


def level_class(level: TankLevel) -> str:
  if level == TankLevel.EMPTY:
    return "text-danger"
  if level == TankLevel.MEDIUM:
    return "text-warning"
  if level == TankLevel.FULL:
    return "text-success"
  return ""


def translate_pump(active: bool) -> str:
  return "ACCESA" if active else "SPENTA"


def translate_state(state: type[State], state_activated_at: datetime) -> str:
  if state == dolianova.FillWell:
    return "ricarica pozzo"
  if state == dolianova.FillLargeTank:
    return "ricarica serbatoio grande"
  if state == dolianova.SettleLargeTank:
    return "decantazione serbatoio grande"
  if state == dolianova.FillSmallTank:
    return "ricarica serbatoio piccolo"
  if state == dolianova.SmallTankInUse:
    return "attesa svuotamento serbatoio piccolo"
  return "sconosciuto"


def get_settle_end_time(measures: Measures) -> datetime | None:
  with open("settings.json") as f:
    data = f.read()
    settings = Settings.deserialize(data)

  if measures.current_state != dolianova.SettleLargeTank:
    return None
  return measures.state_activated_at + settings.settle_time


def translate_measures(measures: Measures) -> dict[str, object]:
  no_heartbeat = datetime.now() - measures.time > dolianova.timedelta(minutes=2)
  settle_end_time = get_settle_end_time(measures)
  return {
    "time": translate_time(measures.time),
    "no_heartbeat": no_heartbeat,
    "well_level": f"{measures.well_level}%",
    "large_tank_level": translate_level(measures.large_tank_level),
    "large_tank_level_class": level_class(measures.large_tank_level),
    "small_tank_level": translate_level(measures.small_tank_level),
    "small_tank_level_class": level_class(measures.small_tank_level),
    "well_to_large_tank_pump": translate_pump(measures.well_to_large_tank_pump_active),
    "lower_to_small_tank_pump": translate_pump(
      measures.lower_to_small_tank_pump_active
    ),
    "current_state": translate_state(
      measures.current_state, measures.state_activated_at
    ).upper(),
    "state_activated_at": translate_time(measures.state_activated_at),
    "settle_end_time": translate_time(settle_end_time)
    if settle_end_time is not None
    else None,
  }


def well_level_history(history: History) -> str:
  return json.dumps(
    [
      {
        "x": t.strftime("%Y-%m-%d %H:%M:%S"),
        "y": m.well_level,
      }
      for t, m in history.measures.items()
    ]
  )


def tank_level_history(history: History, tank: str) -> str:
  return json.dumps(
    [
      {
        "x": t.strftime("%Y-%m-%d %H:%M:%S"),
        "y": tank_level_to_number(getattr(m, tank + "_level")),
      }
      for t, m in history.measures.items()
    ]
  )


def tank_level_to_number(level: TankLevel) -> int:
  if level == TankLevel.EMPTY:
    return 10
  if level == TankLevel.MEDIUM:
    return 50
  if level == TankLevel.FULL:
    return 100
  return -1


@app.route("/")
def index():
  # TODO: do not depend on environment variables here.
  if os.environ.get("FAKE_DATA"):
    measures = load_fake_measures()
    history = load_fake_history()
  else:
    measures = load_measures()
    history = load_history()
  if measures is None or history is None:
    return "Nessun dato disponibile"
  history.add(measures, no_duplicates=False)
  translated_measures = translate_measures(measures)
  return render_template(
    "index.html",
    measures=translated_measures,
    well_level_history=well_level_history(history),
    large_tank_level_history=tank_level_history(history, "large_tank"),
    small_tank_level_history=tank_level_history(history, "small_tank"),
  )


if __name__ == "__main__":
  app.run(debug=True)
