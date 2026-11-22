"""sxplug - Single-file Modular Bot Manager and Installer for SimpleX Chat.

Inspired by LazyVim architecture:
- Declare bots in PLUGINS: ["user/repo", ...]
- Automatically bootstraps its own root .venv if run with system python.
- Automatically clones, sets up dedicated .venv, installs dependencies and loads commands.
- Unified fixed SimpleX address and identity.
"""
from __future__ import annotations

import os
import subprocess
import sys


# =============================================================================
# SELF-BOOTSTRAP (Allows running `python3 sxplug.py` with zero manual setup)
# =============================================================================
def _bootstrap_root_env() -> None:
    """Ensure root virtual environment exists and self-reexecutes if needed."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    root_venv = os.path.join(base_dir, ".venv")
    venv_py = os.path.join(root_venv, "bin", "python3")
    venv_pip = os.path.join(root_venv, "bin", "pip")
    req_file = os.path.join(base_dir, "requirements.txt")

    # If running with external/system Python, ensure root .venv exists and re-execute
    if not hasattr(sys, "real_prefix") and (sys.base_prefix == sys.prefix):
        if not os.path.exists(venv_py):
            print("🌱 [sxplug] Bootstrapping root environment (.venv)...")
            subprocess.run([sys.executable, "-m", "venv", root_venv], check=True)
            if os.path.exists(req_file):
                print("⚙️ [sxplug] Installing base requirements...")
                subprocess.run([venv_pip, "install", "-r", req_file, "--quiet"], check=True)

        # Self-reexec inside root .venv
        os.execv(venv_py, [venv_py, os.path.abspath(__file__)] + sys.argv[1:])


if __name__ == "__main__" or "simplex_chat" not in sys.modules:
    try:
        import simplex_chat  # noqa: F401
    except ImportError:
        _bootstrap_root_env()

import base64
import glob
import hashlib
import importlib.util
import logging
import site
import time
from typing import Any, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich import box

    console = Console()
    HAS_RICH = True
except ImportError:
    console = None
    HAS_RICH = False

from simplex_chat import (
    Bot,
    BotCommand,
    BotProfile,
    Message,
    ParsedCommand,
    SqliteDb,
    TextMessage,
)

# =============================================================================
# PLUGIN CONFIGURATION (Short 'user/repo' or full Git URL)
# =============================================================================
PLUGINS: list[str] = [
    "DaFi-1/DinoBot",
    # Add new bots below (e.g. "user/another-bot"):
]

# =============================================================================
# DIRECTORIES AND GLOBAL CONSTANTS
# =============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGINS_DIR = os.path.join(BASE_DIR, "plugins")
DATA_DIR = os.path.join(BASE_DIR, "data")
AVATAR_PATH = os.path.join(BASE_DIR, "assets", "dinobot_avatar_best.jpg")
LOG_PATH = os.path.join(DATA_DIR, "sxplug.log")

os.makedirs(PLUGINS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Direct all technical background logs to file to keep terminal clean and silent
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def _normalize_repo_url(spec: str) -> str:
    """Normalize plugin specification ('user/repo' shorthand or full URL) into a Git clone URL."""
    spec = spec.strip()
    if not spec:
        return ""
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        return spec
    return f"https://github.com/{spec.strip('/')}.git"


def _shorthand_from_url(url: str) -> str:
    """Extract 'user/repo' shorthand from URL or spec if possible."""
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


def _repo_name_from_url(url: str) -> str:
    """Extract repository name from a Git/GitHub URL or shorthand."""
    return url.rstrip("/").removesuffix(".git").split("/")[-1]


def _load_avatar(path: str = AVATAR_PATH) -> Optional[str]:
    """Load bot avatar image as Base64 for SimpleX Chat."""
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return f"data:image/jpg;base64,{base64.b64encode(f.read()).decode('utf-8')}"
        except Exception:
            pass
    return None


def _render_dashboard(client: SxPlugClient, address: str = "") -> None:
    """Render top header rectangle and clean status."""
    title = "sxplug 1.0.0"
    box_w = 26
    pad = (box_w - len(title)) // 2
    inner = " " * pad + title + " " * (box_w - len(title) - pad)
    border = "+" + "-" * box_w + "+"

    if not HAS_RICH or console is None:
        print(f"\n{border}")
        print(f"|{inner}|")
        print(f"{border}\n")
        print("Plugins:")
        if client.plugin_registry:
            for name, meta in client.plugin_registry.items():
                cmds = len(meta.get("commands", []))
                print(f"    - {name} ({cmds} commands)")
        else:
            print("    (none)")
        print(f"\nAddress: {address}\n")
        return

    console.print(f"\n[bold green]{border}[/bold green]")
    console.print(f"[bold green]|[/bold green][bold white]{inner}[/bold white][bold green]|[/bold green]")
    console.print(f"[bold green]{border}[/bold green]\n")

    console.print("[dim white]Plugins:[/dim white]")
    if client.plugin_registry:
        for name, meta in client.plugin_registry.items():
            cmds = len(meta.get("commands", []))
            console.print(f"    [green]-[/green] [bold white]{name}[/bold white] [dim]({cmds} commands)[/dim]")
    else:
        console.print("    [dim](none)[/dim]")

    console.print(f"\n[dim white]Address:[/dim white] [bold bright_green]{address}[/bold bright_green]\n")


# =============================================================================
# SIMPLEX HUB CLIENT (CENTRAL MANAGER)
# =============================================================================
class SxPlugClient(Bot):
    """SimpleX bot client with dynamic plugin support and strict security settings."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.plugin_registry: dict[str, dict[str, Any]] = {}

    def _profile_to_wire(self) -> dict[str, Any]:
        """Apply least-privilege security settings and enable media/file transfers."""
        p = super()._profile_to_wire()
        prefs = p.setdefault("preferences", {})
        prefs.update({k: {"allow": "no"} for k in ("reactions", "calls", "voice", "timedMessages", "sessions")})
        prefs.update({k: {"allow": "yes"} for k in ("files", "fullDelete")})
        p["peerType"] = "bot"
        return p

    async def _sync_profile(self, user: dict[str, Any]) -> bool:
        """Sync profile without sending invalid contactLink field."""
        new_p = self._profile_to_wire()
        cur = user.get("profile", {})
        keys = ("displayName", "fullName", "shortDescr", "image", "preferences", "peerType")
        if any(cur.get(k) != new_p.get(k) for k in keys):
            try:
                await self.api.api_update_profile(user["userId"], new_p)
                return True
            except Exception as e:
                logging.warning("Warning updating profile on SMP: %s", e)
        return False

    async def _post_start(self, user: Any) -> None:
        """Post-start hook: sync address and render UI dashboard."""
        await super()._post_start(user)
        addr = getattr(self, "_contact_link", None) or ""
        _render_dashboard(self, addr)


# Central SimpleX instance with persistent storage in ./data/my_bot
hub = SxPlugClient(
    profile=BotProfile(
        display_name="sxplug",
        full_name="",
        short_descr="> Plugin Manager for SimpleX Chat\n> Powered by sxplug Hub",
        image=_load_avatar(),
    ),
    db=SqliteDb(file_prefix=os.path.join(DATA_DIR, "my_bot")),
    create_address=True,
    update_address=True,
    update_profile=True,
    allow_files=True,
    commands=[
        BotCommand(keyword="plugin-list", label="List installed plugins in a table"),
        BotCommand(keyword="plugin-help", label="sxplug overview and guide"),
    ],
)


# =============================================================================
# PLUGIN MANAGER (GIT CLONE, VENV SETUP, PIP INSTALL AND DISCOVERY)
# =============================================================================
class PluginManager:
    """Manages cloning, virtual environments, dependency installation, and loading plugins."""

    def __init__(self, client: SxPlugClient, plugins_dir: str = PLUGINS_DIR):
        self.client = client
        self.plugins_dir = plugins_dir

    def sync_all(self, repo_specs: list[str]) -> None:
        """Clone new repositories and load all configured plugins."""
        for spec in repo_specs:
            spec = spec.strip()
            if spec and not spec.startswith("#"):
                self.install_or_load(spec)

    def install_or_load(self, spec: str) -> bool:
        """Ensure the plugin repository is cloned and loaded into the hub."""
        url = _normalize_repo_url(spec)
        repo_name = _repo_name_from_url(spec)
        target_dir = os.path.join(self.plugins_dir, repo_name)

        if not os.path.exists(target_dir):
            logging.info("📦 [sxplug] Cloning %s...", repo_name)
            try:
                subprocess.run(["git", "clone", url, target_dir], check=True)
                logging.info("✅ [sxplug] %s cloned successfully!", repo_name)
            except Exception as e:
                logging.error("❌ Failed to clone %s: %s", url, e)
                return False

        self._check_requirements(target_dir, repo_name)
        return self._load_plugin_module(target_dir, repo_name, url)

    def _ensure_venv(self, target_dir: str, repo_name: str) -> str:
        """Create and ensure a dedicated virtual environment (.venv) inside the plugin folder."""
        venv_dir = os.path.join(target_dir, ".venv")
        pip_path = os.path.join(venv_dir, "bin", "pip")
        if not os.path.exists(venv_dir) or not os.path.exists(pip_path):
            logging.info("🌱 [sxplug] Creating dedicated virtual environment (.venv) for %s...", repo_name)
            try:
                subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
                logging.info("✅ [sxplug] .venv created successfully in %s", venv_dir)
            except Exception as e:
                logging.warning("Warning creating .venv for %s: %s", repo_name, e)
        return venv_dir

    def _check_requirements(self, target_dir: str, repo_name: str) -> None:
        """Install plugin dependencies into its isolated .venv only when requirements.txt changes."""
        req_file = os.path.join(target_dir, "requirements.txt")
        if not os.path.exists(req_file):
            return

        venv_dir = self._ensure_venv(target_dir, repo_name)
        hash_file = os.path.join(venv_dir, ".requirements.hash")

        try:
            with open(req_file, "rb") as f:
                cur_hash = hashlib.sha256(f.read()).hexdigest()
        except Exception:
            cur_hash = ""

        # Skip pip subprocess if dependencies have already been successfully installed
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

    def _find_entrypoint(self, target_dir: str, repo_name: str) -> Optional[str]:
        """Locate the plugin entrypoint file."""
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

    def _load_plugin_module(self, target_dir: str, repo_name: str, repo_url: str) -> bool:
        """Import the plugin module and attach commands/handlers to the hub."""
        entry_file = self._find_entrypoint(target_dir, repo_name)
        if not entry_file:
            logging.warning("No entrypoint executable file found in %s", target_dir)
            return False

        # Inject isolated .venv site-packages
        for sp in glob.glob(os.path.join(target_dir, ".venv", "lib", "python*", "site-packages")):
            if os.path.isdir(sp):
                site.addsitedir(sp)

        if target_dir not in sys.path:
            sys.path.insert(0, target_dir)

        mod_name = f"sxplug_{repo_name.lower()}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, entry_file)
            if not spec or not spec.loader:
                return False
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)

            commands_registered: list[str] = []

            # 1. Hook setup(hub)
            if hasattr(mod, "setup") and callable(mod.setup):
                mod.setup(self.client)

            # 2. Sub-bot instance
            sub_bot = getattr(mod, "bot", None)
            if sub_bot and isinstance(sub_bot, Bot):
                for item in getattr(sub_bot, "_command_handlers", []):
                    self.client._command_handlers.append(item)
                    kw = item[0][0] if isinstance(item[0], (tuple, list)) else str(item[0])
                    commands_registered.append(kw)

                existing_kw = {c.keyword for c in self.client._commands}
                for c in getattr(sub_bot, "_commands", []):
                    if c.keyword not in existing_kw:
                        self.client._commands.append(c)
                        existing_kw.add(c.keyword)

                setattr(mod, "bot", self.client)

            self.client.plugin_registry[repo_name] = {
                "name": repo_name,
                "url": repo_url,
                "path": target_dir,
                "entry": os.path.basename(entry_file),
                "commands": commands_registered,
            }
            logging.info("⚡ [sxplug] Plugin '%s' enabled! (%d commands)", repo_name, len(commands_registered))
            return True
        except Exception as e:
            logging.error("❌ Error initializing plugin %s: %s", repo_name, e, exc_info=True)
            return False


# =============================================================================
# BUILTIN SXPLUG COMMANDS
# =============================================================================
manager = PluginManager(hub)


async def _reply(msg: Message, text: str) -> None:
    """Send text reply via SimpleX Chat."""
    await msg.client.api.api_send_text_message(msg.chat_info, text.strip())


@hub.on_command("plugin-list")
async def cmd_plugin_list(msg: Message, _cmd: ParsedCommand) -> None:
    """List all installed plugins in markdown table format."""
    if not hub.plugin_registry:
        await _reply(msg, "**Installed Plugins:**\n\n_No plugins installed._")
        return

    lines = [
        "**Installed Plugins:**\n",
        "| Plugin | Repository |",
        "| :--- | :--- |",
    ]
    for name, p in hub.plugin_registry.items():
        shorthand = _shorthand_from_url(p.get("url", name))
        lines.append(f"| {name} | {shorthand} |")
    await _reply(msg, "\n".join(lines))


@hub.on_command("plugin-help")
async def cmd_plugin_help(msg: Message, _cmd: ParsedCommand) -> None:
    """Display general help about sxplug manager."""
    text = (
        "🚀 **Welcome to sxplug!**\n\n"
        "The modular plug-and-play bot ecosystem for SimpleX Chat.\n\n"
        "Built-in manager commands:\n"
        "• `/plugin-list`: Display installed plugins in a table\n"
        "• `/plugin-help`: Show this overview message\n\n"
        "💡 To install or configure bots, declare them in the `PLUGINS` list in `sxplug.py`!"
    )
    await _reply(msg, text)


@hub.on_message(content_type="text")
async def handle_text(msg: TextMessage) -> None:
    """Ignore non-command plain text messages."""
    return


# =============================================================================
# MANAGER STARTUP
# =============================================================================
def start() -> None:
    """Synchronize plugins and start the SimpleX bot hub."""
    if HAS_RICH and console:
        with console.status("[dim]Loading plugins...[/dim]", spinner="dots"):
            manager.sync_all(PLUGINS)
    else:
        manager.sync_all(PLUGINS)

    hub.run()


if __name__ == "__main__":
    start()
