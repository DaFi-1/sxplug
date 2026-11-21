"""sxplug - Single-file Modular Bot Manager and Installer for SimpleX Chat."""
from __future__ import annotations

import os
import subprocess
import sys

def _bootstrap_root_env() -> None:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    root_venv = os.path.join(base_dir, ".venv")
    venv_py = os.path.join(root_venv, "bin", "python3")
    venv_pip = os.path.join(root_venv, "bin", "pip")
    req_file = os.path.join(base_dir, "requirements.txt")

    if not hasattr(sys, "real_prefix") and (sys.base_prefix == sys.prefix):
        if not os.path.exists(venv_py):
            print("🌱 [sxplug] Bootstrapping root environment (.venv)...")
            subprocess.run([sys.executable, "-m", "venv", root_venv], check=True)
            if os.path.exists(req_file):
                print("⚙️ [sxplug] Installing base requirements...")
                subprocess.run([venv_pip, "install", "-r", req_file, "--quiet"], check=True)
        os.execv(venv_py, [venv_py, os.path.abspath(__file__)] + sys.argv[1:])

if __name__ == "__main__" or "simplex_chat" not in sys.modules:
    try:
        import simplex_chat  # noqa: F401
    except ImportError:
        _bootstrap_root_env()
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

from simplex_chat import Bot, BotCommand, BotProfile, Message, ParsedCommand, SqliteDb, TextMessage

class SxPlugClient(Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.plugin_registry = {}

    def _profile_to_wire(self):
        p = super()._profile_to_wire()
        prefs = p.setdefault("preferences", {})
        prefs.update({k: {"allow": "no"} for k in ("reactions", "calls", "voice", "timedMessages", "sessions")})
        prefs.update({k: {"allow": "yes"} for k in ("files", "fullDelete")})
        p["peerType"] = "bot"
        return p

    async def _sync_profile(self, user):
        new_p = self._profile_to_wire()
        cur = user.get("profile", {})
        keys = ("displayName", "fullName", "shortDescr", "image", "preferences", "peerType")
        if any(cur.get(k) != new_p.get(k) for k in keys):
            try:
                await self.api.api_update_profile(user["userId"], new_p)
                return True
            except Exception as e:
                import logging
                logging.warning("Warning updating profile on SMP: %s", e)
        return False

hub = SxPlugClient(
    profile=BotProfile(
        display_name="sxplug",
        full_name="",
        short_descr="> Plugin Manager for SimpleX Chat
> Powered by sxplug Hub",
        image=_load_avatar(),
    ),
    db=SqliteDb(file_prefix=os.path.join(DATA_DIR, "my_bot")),
    create_address=False,
    update_address=False,
    update_profile=True,
    allow_files=True,
    commands=[
        BotCommand(keyword="plugin-list", label="List installed plugins in a table"),
        BotCommand(keyword="plugin-help", label="sxplug overview and guide"),
    ],
)

class PluginManager:
    def __init__(self, client: SxPlugClient, plugins_dir: str = PLUGINS_DIR):
        self.client = client
        self.plugins_dir = plugins_dir

    def _ensure_venv(self, target_dir: str, repo_name: str) -> str:
        venv_dir = os.path.join(target_dir, ".venv")
        pip_path = os.path.join(venv_dir, "bin", "pip")
        if not os.path.exists(venv_dir) or not os.path.exists(pip_path):
            import logging
            logging.info("🌱 [sxplug] Creating dedicated virtual environment (.venv) for %s...", repo_name)
            try:
                subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
                logging.info("✅ [sxplug] .venv created successfully in %s", venv_dir)
            except Exception as e:
                logging.warning("Warning creating .venv for %s: %s", repo_name, e)
        return venv_dir

    def _check_requirements(self, target_dir: str, repo_name: str) -> None:
        req_file = os.path.join(target_dir, "requirements.txt")
        if not os.path.exists(req_file):
            return
        venv_dir = self._ensure_venv(target_dir, repo_name)
        hash_file = os.path.join(venv_dir, ".requirements.hash")
        import hashlib, logging
        try:
            with open(req_file, "rb") as f:
                cur_hash = hashlib.sha256(f.read()).hexdigest()
        except Exception:
            cur_hash = ""
        if cur_hash and os.path.exists(hash_file):
            try:
                with open(hash_file, "r") as f:
                    if f.read().strip() == cur_hash:
                        return
            except Exception:
                pass
        pip_path = os.path.join(venv_dir, "bin", "pip")
        cmd = [pip_path if os.path.exists(pip_path) else sys.executable, "install", "-r", req_file, "--quiet"]
        if not os.path.exists(pip_path):
            cmd = [sys.executable, "-m", "pip", "install", "-r", req_file, "--quiet"]
        logging.info("⚙️ [sxplug] Installing/updating dependencies for %s in dedicated .venv...", repo_name)
        try:
            subprocess.run(cmd, check=False)
            if cur_hash:
                with open(hash_file, "w") as f:
                    f.write(cur_hash)
        except Exception as e:
            logging.warning("Warning installing requirements for %s: %s", repo_name, e)

    def _find_entrypoint(self, target_dir: str, repo_name: str):
        candidates = [
            os.path.join(target_dir, "plugin.py"),
            os.path.join(target_dir, f"{repo_name}.py"),
            os.path.join(target_dir, "bot.py"),
            os.path.join(target_dir, "main.py"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        for f in os.listdir(target_dir):
            if f.endswith(".py") and not f.startswith("__"):
                return os.path.join(target_dir, f)
        return None
