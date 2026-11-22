# ⚡ sxplug — Technical Specification & Documentation

**sxplug** is a single-file modular plugin manager and installer for the decentralized **SimpleX Chat** network.

---

## 1. Introduction & Overview

### 1.1. What is `sxplug`?
`sxplug` is an orchestration and plugin management layer built in Python for SimpleX Chat. It functions as a **Central Hub** that connects and executes multiple independent bots under a single connection, fixed SMP address, and profile, eliminating manual setup and operational complexity.

### 1.2. Motivation: Why was `sxplug` created?
In standard SimpleX Chat bot architecture, each bot requires:
- A separate websocket/IPC connection with the SimpleX core.
- An independent cryptographic database (`my_bot_chat.db`).
- A distinct SMP address generated for contacts.
- Multiple separate OS processes running concurrently.

This creates significant friction for users and developers who want to provide multiple bot capabilities under a single contact profile. Furthermore, manual installation required cloning multiple repos, installing conflicting dependencies in the same environment, and managing multiple databases. `sxplug` unifies the ecosystem into one coherent hub.

### 1.3. Modular Philosophy (LazyVim / Neovim Inspired)
Inspired by the declarative architecture of **LazyVim / packer.nvim**, `sxplug` adopts a simple declarative approach:
- Declare desired plugins as `user/repo` shorthands in the `PLUGINS` list.
- On startup, `sxplug` handles cloning, isolated environment setup, dependency management, and dynamic command discovery automatically.

### 1.4. Key Features & Highlights
- **Single-File Hub**: The core engine lives in a single, readable Python file (`sxplug.py`).
- **Dedicated Virtual Environments (`.venv`)**: Every plugin receives its own private `.venv`, preventing version conflicts between bots.
- **In-Process Dynamic Injection**: Avoids heavy IPC or separate child processes; packages are injected via runtime `site.addsitedir`.
- **SHA-256 Dependency Caching**: Caches `requirements.txt` state to skip pip invocations, enabling sub-millisecond boots.
- **Unified Identity**: All bots share the persistent profile and SMP address stored in `./data/`.

---

## 2. Architecture & Runtime Lifecycle

### 2.1. System Architecture
```text
                  +-----------------------------------+
                  |      SimpleX Chat Network         |
                  +-----------------+-----------------+
                                    | (SMP Protocol)
                                    v
                  +-----------------+-----------------+
                  |          sxplug (Hub)             |
                  |     (./data/my_bot_chat.db)       |
                  +--------+-----------------+--------+
                           |                 |
            +--------------+                 +--------------+
            v                                               v
+-----------------------+                       +-----------------------+
|  Plugin 1 (Folder)    |                       |  Plugin 2 (Folder)    |
|  - .venv/ (Isolated)  |                       |  - .venv/ (Isolated)  |
|  - requirements.txt   |                       |  - requirements.txt   |
|  - Commands & Handlers|                       |  - Commands & Handlers|
+-----------------------+                       +-----------------------+
```

### 2.2. Lifecycle: Startup to Execution
1. **Read `PLUGINS` Configuration**: `sxplug` parses configured plugins.
2. **Normalize URL**: Converts `user/repo` shorthand into full Git clone URLs.
3. **Auto-Clone**: Clones missing repositories into `./plugins/<RepoName>`.
4. **Dedicated `.venv` Setup**: Creates an isolated `.venv` per plugin if missing.
5. **SHA-256 Dependency Check**: Compares `requirements.txt` hash. Invokes pip only when changes are detected.
6. **Package Injection & Module Import**: Appends plugin's `site-packages` via `site.addsitedir` and loads the entrypoint file.
7. **Command Discovery**: Gathers all sub-bot commands into the hub's registry.
8. **SimpleX Event Loop**: Connects to the network and begins processing incoming messages.

### 2.3. Shorthand GitHub Syntax
`sxplug` supports both concise shorthand and full URLs:
```python
PLUGINS: list[str] = [
    "author/my-bot",             # Shorthand -> https://github.com/author/my-bot.git
    "https://github.com/user/bot", # Full HTTPS URL
    "git@github.com:user/bot.git", # SSH URL
]
```

### 2.4. Dedicated Virtual Environments & SHA-256 Cache
Each plugin gets an isolated virtual environment:
```bash
./plugins/<PluginName>/.venv/bin/pip install -r requirements.txt --quiet
```
Additionally, `sxplug` stores a SHA-256 hash in `.venv/.requirements.hash`. If `requirements.txt` is unchanged, pip execution is skipped entirely, reducing startup latency to **< 0.2ms**.

### 2.5. Message Capture and Routing
- **Command Messages (`/command-name`)**:
  When a message begins with `/`, the hub looks up the command in its registered handlers. The designated handler is executed with full message context (`Message` and `ParsedCommand`).
- **Plain Text Messages**:
  `sxplug` implements `@hub.on_message(content_type="text")` to silently discard non-command messages, preventing spam and conflicting responses.

---

## 3. Developer Guide: Building Compatible Plugins

Any Python SimpleX bot can be structured as an `sxplug` compatible plugin.

### 3.1. Minimum Requirements
1. Hosted in a Git repository (e.g. GitHub).
2. Contains an executable entrypoint file (`plugin.py`, `<RepoName>.py`, `bot.py`, or `main.py`).
3. (Optional) Contains `requirements.txt` with external dependencies.

### 3.2. Recommended Repository Structure
```text
MySimpleXBot/
├── requirements.txt            # External dependencies
├── README.md                   # Documentation and command references
├── .gitignore                  # Ignore .venv/, *.db, __pycache__/
├── plugin.py                   # Main entrypoint
└── assets/                     # Media, images, or static files
```

### 3.3. Entrypoint Resolution Priority
`sxplug` resolves entrypoints in the following order:
1. `plugin.py` *(Recommended)*
2. `<RepoName>.py` (e.g. `MyBot.py`)
3. `bot.py`
4. `main.py`
5. Any `.py` file in repository root not prefixed with `__`.

### 3.4. Integration Patterns

#### 3.4.1. Pattern A: `bot = Bot(...)` Instance (Recommended)
Develop and test your bot as an independent SimpleX bot. `sxplug` detects the `bot` instance and imports commands automatically:

```python
# plugin.py
from simplex_chat import Bot, BotCommand, BotProfile, Message, ParsedCommand, SqliteDb

bot = Bot(
    profile=BotProfile(display_name="MyBot"),
    db=SqliteDb(file_prefix="mybot"),
    commands=[
        BotCommand(keyword="mybot-hello", label="Send a friendly greeting"),
    ],
)

@bot.on_command("mybot-hello")
async def hello_handler(msg: Message, cmd: ParsedCommand) -> None:
    await msg.client.api.api_send_text_message(
        msg.chat_info, 
        "👋 Hello! Response sent directly from MyBot plugin."
    )

if __name__ == "__main__":
    bot.run()
```

#### 3.4.2. Pattern B: `setup(hub)` Hook
Ideal for plugins designed specifically to run inside `sxplug`:

```python
# plugin.py
from simplex_chat import BotCommand, Message, ParsedCommand

def setup(hub):
    hub._commands.append(BotCommand("mybot-info", "Display MyBot information"))

    @hub.on_command("mybot-info")
    async def info_handler(msg: Message, cmd: ParsedCommand) -> None:
        await msg.client.api.api_send_text_message(
            msg.chat_info, 
            "ℹ️ Info provided via setup(hub) hook."
        )
```

### 3.5. Best Practices & Rules

#### 3.5.1. Command Namespacing (Mandatory)
Because multiple plugins share the same connection:
- **Never use generic command names** like `/help`, `/add`, `/list`, or `/start`.
- Every command must be prefixed with the bot's unique identifier.
  - ❌ **Prohibited:** `/help`, `/add <text>`, `/delete <id>`, `/reset`
  - ✅ **Required:** `/mybot-help`, `/mybot-add <text>`, `/mybot-delete <id>`, `/mybot-reset`

#### 3.5.2. Isolated Relative Persistence
If your plugin uses SQLite or local files:
- Use strictly relative paths inside the plugin directory:
  ```python
  BASE_DIR = os.path.dirname(os.path.abspath(__file__))
  DB_PATH = os.path.join(BASE_DIR, "mybot.db")
  ```
- **Never write files to the sxplug root or data/ directory.**
- Add `*.db` and `*.sqlite` to your plugin's `.gitignore`.

---

### 3.6. The 4 Gold Rules of Plugin Architecture

| Rule | Requirement | Purpose |
| :--- | :--- | :--- |
| **1. Full Autonomy** | Standalone Git repository with `requirements.txt`. | Allows independent testing outside the hub. |
| **2. Standard Entrypoint** | Provide `plugin.py` or `<RepoName>.py`. | Ensures seamless auto-discovery. |
| **3. Strict Namespacing** | Commands prefixed with `/<name>-command`. | Prevents command collisions between plugins. |
| **4. Confined Data** | Store databases and state inside plugin directory. | Guarantees safe cleanup and no cross-plugin corruption. |

---

## 4. Hub Operation & Management

### 4.1. Quickstart (Zero Setup)
`sxplug` features automatic self-bootstrapping:
1. Clone the repository: `git clone https://github.com/DaFi-1/sxplug.git`
2. Declare desired bots in `PLUGINS = [...]` in `sxplug.py`.
3. Run directly:
   ```bash
   python3 sxplug.py
   ```
If executed using the system Python, `sxplug` automatically creates the root `.venv`, installs requirements, and re-executes itself inside the virtualenv.

### 4.2. Built-in Commands
- `/plugin-list`: Display all active plugins and repositories in a Markdown table.
- `/plugin-help`: Display manager overview and command guidance.

### 4.3. Bot Profile & Identity Configuration (`BOT_CONFIG`)
The central bot identity, profile cards, avatar, and automatic welcome message can be fully configured in `BOT_CONFIG`:

```python
BOT_CONFIG = {
    "display_name": "sxplug",
    "full_name": "Plugin Manager",
    "short_descr": "> Plugin Manager for SimpleX Chat\n> Powered by sxplug Hub",
    "description": "Modular plug-and-play bot ecosystem for SimpleX Chat.",
    "welcome_message": "👋 Welcome to sxplug!\nType /plugin-help to see available commands.",
    "avatar_path": AVATAR_PATH,
}
```

- **`display_name`**: Primary bot name displayed in chat headers and message lists.
- **`full_name`**: Optional subtitle or secondary name shown on contact info.
- **`short_descr`**: Brief status/bio snippet.
- **`description`**: Extended markdown biography/info for contact profile.
- **`welcome_message`**: Automated message sent immediately when a new user connects to the bot.
- **`avatar_path`**: Path to JPEG/PNG avatar (automatically resized to 128x128 thumbnail with ~2.5 KB payload to strictly respect SimpleX SMP size constraints).

### 4.4. Rotating SimpleX Address (`-new`)
To revoke the existing SMP address queue and generate a fresh link and QR code:
```bash
python3 sxplug.py -new
```
This calls `api_delete_user_address` to cleanly delete the old address on SimpleX servers and creates a new cryptographic address and terminal QR code.
