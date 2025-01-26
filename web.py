import os
from datetime import datetime, timedelta

from flask import Flask, render_template

import dolianova
from dolianova import Measures, State, TankLevel

app = Flask(__name__)


def load_measures():
  return Measures(
    time=datetime.now() - timedelta(minutes=5),
    well_level=50,
    large_tank_level=TankLevel.FULL,
    small_tank_level=TankLevel.EMPTY,
    well_to_large_tank_pump_active=True,
    lower_to_small_tank_pump_active=False,
    current_state=dolianova.SmallTankInUse,
    state_activated_at=datetime.now() - timedelta(minutes=50),
  )

  if not os.path.exists("measures.json"):
    return None
  with open("measures.json") as f:
    data = f.read()
    return Measures.deserialize(data)
  

def translate_time(time: datetime) -> str:
  minutes_from_now = int((datetime.now() - time).total_seconds() / 60)
  return f"{time.strftime("%Y-%m-%d %H:%M")} ({minutes_from_now} minuti fa)"


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
  no_heartbeat = datetime.now() - measures.time > dolianova.timedelta(minutes=2)
  return {
    "time": translate_time(measures.time),
    "no_heartbeat": no_heartbeat,
    "well_level": f"{measures.well_level}%",
    "large_tank_level": translate_level(measures.large_tank_level),
    "large_tank_level_class": level_class(measures.large_tank_level),
    "small_tank_level": translate_level(measures.small_tank_level),
    "small_tank_level_class": level_class(measures.small_tank_level),
    "well_to_large_tank_pump": translate_pump(measures.well_to_large_tank_pump_active),
    "lower_to_small_tank_pump": translate_pump(measures.lower_to_small_tank_pump_active),
    "current_state": translate_state(measures.current_state, measures.state_activated_at).upper(),
    "state_activated_at": translate_time(measures.state_activated_at),
  }


@app.route("/")
def index():
  measures = load_measures()
  if measures is None:
    return "Nessun dato disponibile"
  translated_measures = translate_measures(measures)
  return render_template("index.html", measures=translated_measures)


if __name__ == "__main__":
  app.run(debug=True)
