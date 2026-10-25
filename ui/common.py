import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sqlite3

import pandas as pd

from workflow.branches import DB_PATH, TEAMS, SUPERVISOR

# internal address -> team name, used for the Team inbox "channels"
TEAM_BY_ADDRESS = {addr: name for name, addr in TEAMS.values()}
TEAM_BY_ADDRESS[SUPERVISOR[1]] = SUPERVISOR[0]


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
