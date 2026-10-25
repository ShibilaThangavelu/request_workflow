import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sqlite3

import pandas as pd

from workflow.branches import DB_PATH, TEAMS, SUPERVISOR

# internal address -> team name, used for the Team inbox "channels" (in tab order)
from workflow.branches import DEPARTMENT_TEAMS

TEAM_BY_ADDRESS = {}
for _name, _addr in [TEAMS["Complaint"], SUPERVISOR, TEAMS["Needs Human Review"]] + list(DEPARTMENT_TEAMS.values()):
    TEAM_BY_ADDRESS[_addr] = _name


def read(sql, params=()):
    with sqlite3.connect(DB_PATH) as db:
        return pd.read_sql_query(sql, db, params=params)


def when(value):
    try:
        return datetime.fromisoformat(value).strftime("%d %b, %H:%M")
    except (TypeError, ValueError):
        return "-"


def due_state(value):
    due = datetime.fromisoformat(value)
    hours = (due - datetime.now()).total_seconds() / 3600
    if hours < 0:
        return "OVERDUE"
    return f"in {hours:.1f} hours" if hours < 48 else f"in {hours / 24:.1f} days"
