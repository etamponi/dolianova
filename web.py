import json
import os
from datetime import datetime

from flask import Flask, render_template

import dolianova
from dolianova import History, Measures, State, TankLevel

app = Flask(__name__)


def load_measures():
  # return Measures(
  #   time=datetime.now() - timedelta(minutes=5),
  #   well_level=50,
  #   large_tank_level=TankLevel.FULL,
  #   small_tank_level=TankLevel.EMPTY,
  #   well_to_large_tank_pump_active=True,
  #   lower_to_small_tank_pump_active=False,
  #   current_state=dolianova.SmallTankInUse,
  #   state_activated_at=datetime.now() - timedelta(minutes=50),
  # )

  if not os.path.exists("measures.json"):
    return None
  with open("measures.json") as f:
    data = f.read()
    return Measures.deserialize(data)


def load_history():
  # return History(
  #   {
  #     datetime.now() - timedelta(minutes=60 - 3 * i): Measures(
  #       time=datetime.now() - timedelta(minutes=60 - 3 * i),
  #       well_level=int(100 * (i+1) / 20),
  #       large_tank_level=TankLevel.EMPTY if i < 10 else TankLevel.FULL,
  #       small_tank_level=TankLevel.EMPTY if i > 10 else TankLevel.MEDIUM,
  #       well_to_large_tank_pump_active=False,
  #       lower_to_small_tank_pump_active=False,
  #       current_state=dolianova.FillWell,
  #       state_activated_at=datetime.now() - timedelta(minutes=60),
  #     )
  #     for i in range(20)
  #   }
  # )

  if not os.path.exists("history.json"):
    return None
  with open("history.json") as f:
    data = f.read()
    return History.deserialize(data)


def translate_time(time: datetime) -> str:
  minutes_from_now = int((datetime.now() - time).total_seconds() / 60)
  return f"{time.strftime('%Y-%m-%d %H:%M')} ({minutes_from_now} minuti fa)"


def translate_level(level: TankLevel) -> str:
  if level == TankLevel.EMPTY:
    return "VUOTO"
  if level == TankLevel.MEDIUM:
    return "MEDIO"
  if level == TankLevel.FULL:
    return "PIENO"
  return "sconosciuto"


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


def translate_measures(measures: Measures) -> dict[str, object]:
  no_heartbeat = datetime.now() - measures.time > dolianova.timedelta(minutes=7)
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
  measures = load_measures()
  history = load_history()
  if measures is None or history is None:
    return "Nessun dato disponibile"
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
