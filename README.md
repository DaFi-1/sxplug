# ⚡ sxplug

Single-file modular plugin manager and installer for **SimpleX Chat**.

Inspired by **LazyVim**, **sxplug** allows running multiple bots under a single fixed SimpleX Chat address simply by declaring GitHub repositories in a configuration list.

---

## 🚀 Quickstart (Zero Setup)

1. **Clone the repository:**
```bash
git clone https://github.com/DaFi-1/sxplug.git
cd sxplug
```

2. **Configure your bots in `sxplug.py`:**
Simply list your bots using `user/repo` shorthand (or full Git URL):

```python
PLUGINS: list[str] = [
    "DaFi-1/DinoBot",
    # "user/another-bot",
]
```

3. **Start sxplug with a single command:**
```bash
python3 sxplug.py
```

> **✨ Auto-Bootstrap**: `sxplug` automatically detects if the root virtual environment exists. If not, it creates `.venv`, installs required dependencies, and restarts itself inside the virtualenv. On subsequent runs, it boots instantly!

---

### What `sxplug` does automatically:
1. **Auto-Clone**: Clones listed repositories to `./plugins/<RepoName>`.
2. **Dedicated Virtual Environment**: Creates an isolated `.venv` per plugin and installs `requirements.txt` with zero version conflicts.
3. **Instant Boot Cache**: Computes SHA-256 hashes of `requirements.txt` to skip redundant pip checks and start in sub-milliseconds.
4. **Auto-Discovery**: Resolves entrypoint files and registers all commands dynamically.
5. **Fixed Identity**: Keeps persistent keys and SMP address in `./data/my_bot_chat.db`.
6. **Built-in Chat Commands**:
   - `/plugin-list`: Display installed bots in a clean Markdown table.
   - `/plugin-help`: Display overview and usage instructions.
7. **Minimalist Dashboard & Terminal QR Code**: Displays a clean startup summary with an instant terminal-scannable ASCII QR code for fast mobile connection.

---

## 📁 Directory Structure

```text
sxplug/
├── sxplug.py                   # Central single-file manager
├── requirements.txt            # Base dependencies
├── README.md                   # Quickstart guide
├── doc.md                      # Full technical specification & developer guide
├── data/                       # Persistent SimpleX cryptographic keys
├── tests/                      # Unit test suite
└── plugins/                    # Isolated cloned plugins (each with its own .venv)
```
