"""Unit tests for sxplug."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import sxplug as sx


def test_normalize_and_repo_name():
    assert sx._normalize_repo_url("DaFi-1/DinoBot") == "https://github.com/DaFi-1/DinoBot.git"
    assert sx._normalize_repo_url("https://github.com/DaFi-1/DinoBot.git") == "https://github.com/DaFi-1/DinoBot.git"
    assert sx._normalize_repo_url("git@github.com:DaFi-1/DinoBot.git") == "git@github.com:DaFi-1/DinoBot.git"
    assert sx._normalize_repo_url("") == ""

    assert sx._shorthand_from_url("https://github.com/DaFi-1/DinoBot.git") == "DaFi-1/DinoBot"
    assert sx._shorthand_from_url("DaFi-1/DinoBot") == "DaFi-1/DinoBot"
    assert sx._shorthand_from_url("just-a-bot") == "just-a-bot"

    assert sx._repo_name_from_url("DaFi-1/DinoBot") == "DinoBot"
    assert sx._repo_name_from_url("https://github.com/DaFi-1/DinoBot") == "DinoBot"
    assert sx._repo_name_from_url("https://github.com/DaFi-1/DinoBot.git") == "DinoBot"
    assert sx._repo_name_from_url("https://github.com/user/bot/") == "bot"


def test_avatar_loader(tmp_path: Path):
    assert sx._load_avatar(str(tmp_path / "nonexistent.jpg")) is None
    dummy = tmp_path / "avatar.jpg"
    dummy.write_bytes(b"image_bytes")
    assert sx._load_avatar(str(dummy)).startswith("data:image/jpg;base64,")


def test_dir_size_str(tmp_path: Path):
    assert sx._dir_size_str(str(tmp_path / "nonexistent")) == "0 B"
    d = tmp_path / "test_plugin_dir"
    d.mkdir()
    (d / "plugin.py").write_bytes(b"x" * 2048)  # 2 KB
    # Include .venv files in total size
    venv = d / ".venv"
    venv.mkdir()
    (venv / "huge.bin").write_bytes(b"x" * 1024 * 1024)  # 1 MB
    # .git should still be ignored
    git_dir = d / ".git"
    git_dir.mkdir()
    (git_dir / "objects.bin").write_bytes(b"x" * 5 * 1024 * 1024)
    res = sx._dir_size_str(str(d))
    assert "1.0 MB" in res


def test_lazy_client_permissions_and_sync():
    wire = sx.hub._profile_to_wire()
    assert wire["peerType"] == "bot"
    assert wire["preferences"]["reactions"]["allow"] == "no"
    assert wire["preferences"]["files"]["allow"] == "yes"

    class DummyApi:
        def __init__(self):
            self.calls = []

        async def api_update_profile(self, uid, prof):
            self.calls.append((uid, prof))

    dummy_client = sx.SxPlugClient(
        profile=sx.hub._profile,
        db=sx.hub._db,
    )
    dummy_client._api = DummyApi()

    # No changes
    res_no = asyncio.run(dummy_client._sync_profile({"userId": 1, "profile": dict(dummy_client._profile_to_wire())}))
    assert res_no is False

    # With changes
    res_yes = asyncio.run(dummy_client._sync_profile({"userId": 1, "profile": {"displayName": "Old"}}))
    assert res_yes is True
    assert len(dummy_client._api.calls) == 1


def test_bot_config_profile():
    assert sx.BOT_CONFIG["display_name"] == "sxplug"
    assert sx.hub._profile.display_name == sx.BOT_CONFIG["display_name"]
    assert sx.hub._profile.full_name == sx.BOT_CONFIG["full_name"]
    assert sx.hub._profile.short_descr == sx.BOT_CONFIG["short_descr"]
    assert sx.hub._welcome == sx.BOT_CONFIG["welcome_message"]

    wire = sx.hub._profile_to_wire()
    assert wire["displayName"] == "sxplug"
    assert wire["fullName"] == "Plugin Manager"
    assert wire["description"] == sx.BOT_CONFIG["description"]
    assert wire["peerType"] == "bot"


def test_entrypoint_resolution_priority(tmp_path: Path):
    manager = sx.PluginManager(sx.hub, plugins_dir=str(tmp_path))
    bot_dir = tmp_path / "CustomBot"
    bot_dir.mkdir()

    # Empty folder
    assert manager._find_entrypoint(str(bot_dir), "CustomBot") is None

    # Priority 5: any non-__ python file
    f5 = bot_dir / "random.py"
    f5.write_text("# random")
    assert manager._find_entrypoint(str(bot_dir), "CustomBot") == str(f5)

    # Priority 4: main.py
    f4 = bot_dir / "main.py"
    f4.write_text("# main")
    assert manager._find_entrypoint(str(bot_dir), "CustomBot") == str(f4)

    # Priority 3: bot.py
    f3 = bot_dir / "bot.py"
    f3.write_text("# bot")
    assert manager._find_entrypoint(str(bot_dir), "CustomBot") == str(f3)

    # Priority 2: CustomBot.py (<RepoName>.py)
    f2 = bot_dir / "CustomBot.py"
    f2.write_text("# repo name")
    assert manager._find_entrypoint(str(bot_dir), "CustomBot") == str(f2)

    # Priority 1: plugin.py (Highest priority)
    f1 = bot_dir / "plugin.py"
    f1.write_text("# plugin")
    assert manager._find_entrypoint(str(bot_dir), "CustomBot") == str(f1)


def test_requirements_caching_and_invalidation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    manager = sx.PluginManager(sx.hub, plugins_dir=str(tmp_path))
    bot_dir = tmp_path / "CachedBot"
    bot_dir.mkdir()
    req_file = bot_dir / "requirements.txt"
    req_file.write_text("package-a>=1.0.0\n")

    venv_dir = bot_dir / ".venv"
    venv_dir.mkdir()
    (venv_dir / "bin").mkdir()
    pip_bin = venv_dir / "bin" / "pip"
    pip_bin.write_text("#!/bin/sh\nexit 0")
    pip_bin.chmod(0o755)

    pip_calls = []

    def mock_run(cmd, **kwargs):
        pip_calls.append(cmd)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(sx.subprocess, "run", mock_run)

    # First run: should call pip and create .requirements.hash
    manager._check_requirements(str(bot_dir), "CachedBot")
    assert len(pip_calls) == 1
    hash_file = venv_dir / ".requirements.hash"
    assert hash_file.exists()
    first_hash = hash_file.read_text().strip()

    # Second run: hash is unchanged, pip must NOT be called (Instant boot)
    manager._check_requirements(str(bot_dir), "CachedBot")
    assert len(pip_calls) == 1  # Unchanged!

    # Modify requirements.txt: pip must be called again
    req_file.write_text("package-a>=1.0.0\npackage-b>=2.0.0\n")
    manager._check_requirements(str(bot_dir), "CachedBot")
    assert len(pip_calls) == 2
    assert hash_file.read_text().strip() != first_hash


def test_plugin_fault_tolerance(tmp_path: Path):
    manager = sx.PluginManager(sx.hub, plugins_dir=str(tmp_path))

    # 1. Broken plugin with syntax error
    bad_dir = tmp_path / "BrokenBot"
    bad_dir.mkdir()
    (bad_dir / "plugin.py").write_text("def broken syntax (: this is invalid python")

    # install_or_load should catch exception and return False without crashing
    res = manager.install_or_load(str(bad_dir))
    assert res is False
    assert "BrokenBot" not in sx.hub.plugin_registry

    # 2. Plugin directory without entrypoint
    empty_dir = tmp_path / "EmptyBot"
    empty_dir.mkdir()
    (empty_dir / "README.md").write_text("# Just docs")
    res_empty = manager.install_or_load(str(empty_dir))
    assert res_empty is False


def test_plugin_sub_bot_instance_pattern(tmp_path: Path):
    manager = sx.PluginManager(sx.hub, plugins_dir=str(tmp_path))
    bot_dir = tmp_path / "SubBot"
    bot_dir.mkdir()

    # Sub-bot creating its own Bot instance with required profile & db
    (bot_dir / "plugin.py").write_text(
        "from simplex_chat import Bot, BotCommand, BotProfile, SqliteDb\n"
        "bot = Bot(\n"
        "    profile=BotProfile(display_name='SubBot'),\n"
        "    db=SqliteDb(file_prefix='subbot'),\n"
        "    commands=[BotCommand('subbot-ping', 'SubBot Ping')],\n"
        ")\n"
        "@bot.on_command('subbot-ping')\n"
        "async def _p(m, c): pass\n"
    )

    res = manager.install_or_load(str(bot_dir))
    assert res is True
    assert "SubBot" in sx.hub.plugin_registry
    assert "subbot-ping" in sx.hub.plugin_registry["SubBot"]["commands"]


def test_markdown_table_plugin_list(tmp_path: Path):
    sent = []

    class MockApi:
        async def api_send_text_message(self, chat_info, text):
            sent.append(text)

    msg = SimpleNamespace(chat_info={"type": "direct"}, client=SimpleNamespace(api=MockApi()))

    # Create dummy plugin folder
    p_dir = tmp_path / "DinoBot"
    p_dir.mkdir()
    (p_dir / "plugin.py").write_text("print('dino')")

    # Case 1: Registry with plugins
    sx.hub.plugin_registry = {
        "DinoBot": {
            "url": "https://github.com/DaFi-1/DinoBot.git",
            "commands": ["dinobot-help", "dinobot-play"],
            "path": str(p_dir),
        },
        "WeatherBot": {
            "url": "user/WeatherBot",
            "commands": [],
            "path": "",
        },
    }
    asyncio.run(sx.cmd_plugin_list(msg, None))
    output = sent[-1]
    assert "| Plugin | Commands | Size | Repository |" in output
    assert "| DinoBot | 2 |" in output
    assert "| DaFi-1/DinoBot |" in output
    assert "| WeatherBot | 0 | 0 B | user/WeatherBot |" in output

    # Case 2: Empty registry
    sx.hub.plugin_registry = {}
    asyncio.run(sx.cmd_plugin_list(msg, None))
    assert "_No plugins installed._" in sent[-1]

    # Builtin help and text handler
    asyncio.run(sx.cmd_plugin_help(msg, None))
    assert "sxplug" in sent[-1]
    asyncio.run(sx.handle_text(SimpleNamespace()))


def test_dashboard_and_ascii_qr(capsys: pytest.CaptureFixture):
    # Test QR generator with valid address
    sx._print_ascii_qr("https://smp8.simplex.im/a#test12345")
    captured = capsys.readouterr().out
    assert len(captured.strip()) > 0

    # Test dashboard rendering
    dummy_client = SimpleNamespace(
        plugin_registry={"DinoBot": {"commands": ["ping", "help"]}},
        _commands=[SimpleNamespace(keyword="ping"), SimpleNamespace(keyword="help")],
    )
    sx._render_dashboard(dummy_client, "https://smp8.simplex.im/a#test12345")
    out = capsys.readouterr().out
    assert "sxplug 1.0.0" in out
    assert "DinoBot" in out
    assert "Address:" in out


def test_address_rotation():
    class MockApi:
        def __init__(self):
            self.deleted = []
            self.created = []
            self.addr = {"connLinkContact": {"connShortLink": "https://smp8.simplex.im/a#initial"}, "addressSettings": {}}

        async def api_get_user_address(self, uid):
            return self.addr

        async def api_delete_user_address(self, uid):
            self.deleted.append(uid)
            self.addr = None

        async def api_create_user_address(self, uid):
            self.created.append(uid)
            self.addr = {"connLinkContact": {"connShortLink": "https://smp8.simplex.im/a#fresh_rotated"}, "addressSettings": {}}

        async def api_set_address_settings(self, uid, settings):
            pass

    client = sx.SxPlugClient(
        rotate_address=True,
        profile=sx.BotProfile(display_name="Test"),
        db=sx.SqliteDb(file_prefix="test_db"),
    )
    client._api = MockApi()

    res = asyncio.run(client._sync_address({"userId": 42}))
    assert len(client.api.deleted) == 1
    assert client.rotate_address is False
    assert client.api.deleted[0] == 42
    assert len(client.api.created) == 1
