import os
import shutil

HOME = os.path.expanduser("~")
NODE = shutil.which("node") or "not installed"
PYTHON = shutil.which("python3") or "not installed"

SYSTEM = f"Your name is Atom. Home: {HOME}. Node: {NODE}. Python: {PYTHON}."
