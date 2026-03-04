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

SYSTEM = f"Your name is Atom. Home: {HOME}. Node: {NODE}. Python: {PYTHON}. Time: {TIME}. Date: {DATE}. Timezone: {TIMEZONE}."
