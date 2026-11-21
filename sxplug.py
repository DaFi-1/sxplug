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

def _normalize_repo_url(spec: str) -> str:
    spec = spec.strip()
    if not spec:
        return ""
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        return spec
    return f"https://github.com/{spec.strip('/')}.git"

def _repo_name_from_url(url: str) -> str:
    return url.rstrip("/").removesuffix(".git").split("/")[-1]

def _shorthand_from_url(url: str) -> str:
    clean = url.strip().removesuffix(".git").rstrip("/")
    if "github.com/" in clean:
        parts = clean.split("github.com/")[-1].split("/")
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"
    if "/" in clean and not clean.startswith(("http", "git@")):
        parts = clean.split("/")
        if len(parts) == 2:
            return clean
    return _repo_name_from_url(url)

def _load_avatar(path: str = AVATAR_PATH):
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                import base64
                return f"data:image/jpg;base64,{base64.b64encode(f.read()).decode('utf-8')}"
        except Exception:
            pass
    return None
