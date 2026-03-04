import os
import shutil
from datetime import datetime

HOME = os.path.expanduser("~")
NODE = shutil.which("node") or "not installed"
PYTHON = shutil.which("python3") or "not installed"

now = datetime.now()
TIME = now.strftime("%-I:%M %p")
DATE = now.strftime("%b %-d, %Y")
TIMEZONE = now.astimezone().tzname()

SYSTEM = f"""Your name is Atom.
Your home directory is {HOME}.
Node is at {NODE}.
Python is at {PYTHON}.
The current time is {TIME}.
The date is {DATE}.
The timezone is {TIMEZONE}."""
