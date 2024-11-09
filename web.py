from dataclasses import dataclass
from datetime import datetime
import json
import os
from typing import Literal

from flask import Flask, render_template

app = Flask(__name__)


@dataclass
class State:
  pump1_last_on: datetime | None = None
  pump2_last_on: datetime | None = None
  pump1_running: bool = False
  pump2_running: bool = False
  pump1_start_time: datetime | None = None
  pump2_start_time: datetime | None = None
  tank1_state: Literal["filling", "emptying"] | None = None


def read_state(state_file: str) -> State:
  if not os.path.exists(state_file):
    return State()

  with open(state_file, "r") as file:
    # load the state from the file
    # then turn the strings into datetime objects
    state = json.load(file)
    state["pump1_last_on"] = (
        datetime.fromisoformat(state["pump1_last_on"])
        if state["pump1_last_on"] is not None
        else None
    )
    state["pump2_last_on"] = (
        datetime.fromisoformat(state["pump2_last_on"])
        if state["pump2_last_on"] is not None
        else None
    )
    state["pump1_start_time"] = (
        datetime.fromisoformat(state["pump1_start_time"])
        if state["pump1_start_time"] is not None
        else None
    )
    state["pump2_start_time"] = (
        datetime.fromisoformat(state["pump2_start_time"])
        if state["pump2_start_time"] is not None
        else None
    )
    return State(**state)


@app.route("/")
def hello_world():
  with open("water_system_config.json", "r") as file:
    config = json.load(file)
  state = read_state(config["state_file"])
  return render_template("index.html", state=state)
