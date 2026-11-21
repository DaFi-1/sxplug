"""Unit tests for sxplug."""
from __future__ import annotations
import os, sys, pytest
from pathlib import Path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
import sxplug as sx

def test_normalize_and_repo_name():
    assert sx._normalize_repo_url("DaFi-1/DinoBot") == "https://github.com/DaFi-1/DinoBot.git"
    assert sx._repo_name_from_url("DaFi-1/DinoBot") == "DinoBot"

def test_avatar_loader(tmp_path: Path):
    assert sx._load_avatar(str(tmp_path / "nonexistent.jpg")) is None
    dummy = tmp_path / "avatar.jpg"
    dummy.write_bytes(b"image_bytes")
    assert sx._load_avatar(str(dummy)).startswith("data:image/jpg;base64,")

def test_lazy_client_permissions_and_sync():
    wire = sx.hub._profile_to_wire()
    assert wire["peerType"] == "bot"
    assert wire["preferences"]["reactions"]["allow"] == "no"
    assert wire["preferences"]["files"]["allow"] == "yes"

def test_entrypoint_resolution_priority(tmp_path: Path):
    manager = sx.PluginManager(sx.hub, plugins_dir=str(tmp_path))
    bot_dir = tmp_path / "CustomBot"
    bot_dir.mkdir()
    assert manager._find_entrypoint(str(bot_dir), "CustomBot") is None
