import os
import platform
import shutil
from datetime import datetime

HOME = os.path.expanduser("~")
NODE = shutil.which("node") or "not installed"
PYTHON = shutil.which("python3") or "not installed"

now = datetime.now()
TIME = now.strftime("%-I:%M %p")
DATE = now.strftime("%b %-d, %Y")
TIMEZONE = now.astimezone().tzname()

# os
try:
    with open("/etc/os-release") as f:
        _os = dict(l.strip().split("=", 1) for l in f if "=" in l)
    OS = _os.get("PRETTY_NAME", "").strip('"')
except Exception:
    OS = platform.system()
ARCH = platform.machine()
SHELL = os.environ.get("SHELL", "unknown")

# uptime
try:
    with open("/proc/uptime") as f:
        _secs = int(float(f.read().split()[0]))
    _days, _rem = divmod(_secs, 86400)
    _hrs, _rem = divmod(_rem, 3600)
    _mins = _rem // 60
    UPTIME = f"{_days}d {_hrs}h {_mins}m" if _days else f"{_hrs}h {_mins}m"
except Exception:
    UPTIME = "unknown"

# cpu
try:
    _cpus = os.cpu_count()
    with open("/proc/cpuinfo") as f:
        _freq = [l.split(":")[1].strip() for l in f if "model name" in l]
    CPU = f"{_cpus} cores, {_freq[0]}" if _freq else f"{_cpus} cores"
except Exception:
    CPU = f"{os.cpu_count()} cores"

# ram
try:
    with open("/proc/meminfo") as f:
        _mem = {l.split(":")[0]: int(l.split(":")[1].strip().split()[0]) for l in f if "MemTotal" in l or "MemAvailable" in l}
    _total = round(_mem["MemTotal"] / 1048576, 1)
    _avail = round(_mem["MemAvailable"] / 1048576, 1)
    RAM = f"{_total} GB total, {_avail} GB available"
except Exception:
    RAM = "unknown"

# disk
try:
    _st = os.statvfs(HOME)
    _dtotal = round((_st.f_blocks * _st.f_frsize) / (1024**3), 1)
    _dfree = round((_st.f_bavail * _st.f_frsize) / (1024**3), 1)
    DISK = f"{_dtotal} GB total, {_dfree} GB free"
except Exception:
    DISK = "unknown"

# gpu
try:
    import subprocess
    _lspci = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5)
    _vga = [l.split(": ", 1)[1] for l in _lspci.stdout.splitlines() if "VGA" in l]
    _vga = [v for v in _vga if "Cirrus" not in v and "Bochs" not in v and "QXL" not in v]
    if _vga:
        _name = _vga[0]
        try:
            with open("/sys/class/drm/card0/device/mem_info_vram_total") as f:
                _vram = round(int(f.read().strip()) / (1024**3), 1)
            GPU = f"{_name}, {_vram} GB VRAM"
        except Exception:
            GPU = _name
    else:
        GPU = None
except Exception:
    GPU = None

SYSTEM = f"""Your name is Atom.
The OS is {OS} ({ARCH}).
The shell is {SHELL}.
Your home directory is {HOME}.
Node is at {NODE}.
Python is at {PYTHON}.
The current time is {TIME}.
The date is {DATE}.
The timezone is {TIMEZONE}.
You have {CPU}.
RAM is {RAM}.
Disk is {DISK}.
Uptime is {UPTIME}.
GPU is {GPU or 'none'}.
Your custom tools are in {HOME}/.atom-0-tools/."""
