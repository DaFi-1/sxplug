"""sxplug - Single-file Modular Bot Manager and Installer for SimpleX Chat."""
from __future__ import annotations

import os
import subprocess
import sys

PLUGINS: list[str] = [
    "DaFi-1/DinoBot",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGINS_DIR = os.path.join(BASE_DIR, "plugins")
DATA_DIR = os.path.join(BASE_DIR, "data")
AVATAR_PATH = os.path.join(BASE_DIR, "assets", "dinobot_avatar_best.jpg")

os.makedirs(PLUGINS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
