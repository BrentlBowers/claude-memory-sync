# Claude Memory Sync System

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Platform: Linux](https://img.shields.io/badge/Platform-Linux-lightgrey.svg)
![Cloud: Proton Drive](https://img.shields.io/badge/Cloud-Proton%20Drive-6D4AFF.svg)
![Status: Active](https://img.shields.io/badge/Status-Active-brightgreen.svg)

A lightweight, automated memory sync system that gives Claude persistent context across devices and sessions. Runs silently in the background. Zero manual steps after setup.

---

## The Problem

Claude starts every session from scratch. No project history, no context, no idea what you were building yesterday. For someone running multiple AI agents across multiple projects on two laptops, that's a real productivity killer -- every session wastes 10-15 minutes re-establishing context.

## The Solution

Structured JSON context files stored locally, synced to end-to-end encrypted cloud storage once a day, with a Python API layer that generates smart startup briefs via the Claude API. When you start a new session, Claude already knows where you left off.

**This system complements Claude's native memory -- it doesn't replace it.** Claude's built-in memory features keep improving, but they live inside Anthropic's platform. This is a structured, portable, encrypted backup system you own — provider-independent, inspectable, and yours to grep. Both work together.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Claude AI                          │
│              (startup context injected)                 │
└──────────────┬──────────────────────┬───────────────────┘
               │ api_sync context     │ api_sync context
               ▼                      ▼
┌──────────────────────┐   ┌──────────────────────────────┐
│  Machine 1           │   │  Machine 2                   │
│  (primary machine)   │   │  (travel machine)            │
│                      │   │                              │
│  claude_sync.py      │   │  claude_sync.py              │
│  heartbeat + context │   │  heartbeat + context         │
│                      │   │                              │
│  claude_api_sync.py  │   │  claude_api_sync.py          │
│  reads memory,       │   │  reads memory,               │
│  calls Claude API    │   │  calls Claude API            │
│                      │   │                              │
│  systemd + cron      │   │  systemd + cron              │
│  auto-start on boot  │   │  auto-start on boot          │
│                      │   │                              │
│  ~/Desktop/          │   │  ~/Desktop/                  │
│  claude-memory/      │   │  claude-memory/              │
└──────────┬───────────┘   └──────────────┬───────────────┘
           │ rclone push (1x a day)    │ rclone pull (1x a day)
           ▼                              ▲
           ┌──────────────────────────────┤
           │       Proton Drive           │
           │  (E2E encrypted cloud sync)  │
           └──────────────────────────────┘
```

**Machine 1** -- primary daily driver. Pushes memory up to Proton Drive 1x a day.  
**Machine 2** -- travel machine. Pulls down from Proton Drive 1x a day.  
**Proton Drive** -- encrypted cloud layer in the middle. No plain text ever hits the cloud.  
**api_sync** -- reads local memory files, calls Claude API, generates startup context brief.

![Claude Memory Sync Architecture](claude_memory_sync_architecture.svg)

**Interactive diagrams -- open in browser for full detail:**

- [Full System Architecture](https://htmlpreview.github.io/?https://github.com/BrentlBowers/claude-memory-sync/blob/main/claude_memory_system_full_architecture.html)
- [Data Flow Diagram](https://htmlpreview.github.io/?https://github.com/BrentlBowers/claude-memory-sync/blob/main/claude_memory_sync_data_flow.html)

---

## How It Works

| Component | What it does |
|-----------|-------------|
| `claude_sync.py` | Runs continuously via systemd. Writes heartbeat and context files every 30 min (local writes only — no cloud traffic). |
| `claude_api_sync.py` | Reads memory files, calls Claude API to generate startup context, logs session summaries. Injects per-project framework rules into every brief (v1.1.0 — see below). |
| rclone + cron | Syncs `~/Desktop/claude-memory/` to Proton Drive 1x a day. Machine 1 pushes up, Machine 2 pulls down. |
| systemd | Auto-starts both scripts on boot. Fully hands-off after setup. |
| `.env` (chmod 600) | API key + per-machine identity (`CLAUDE_SYNC_MACHINE`, `CLAUDE_SYNC_PEER`, `CLAUDE_SYNC_OWNER`). Stored locally only. Never synced to cloud. Never committed to git. |

---

## File Structure

```
~/Desktop/claude-memory/
├── memory/        # Core context files -- owner info, heartbeat, session summaries
├── projects/      # Per-project state -- one JSON file per project
│   └── frameworks/  # Optional per-project reasoning frameworks (see below)
├── experiments/   # Experiment logs and prompt test results
└── logs/          # Sync activity logs from Python scripts and rclone
```

---

## Framework Injection (v1.1.0)

Each project can carry an optional **reasoning framework** -- a versioned set of rules that gets prepended to every startup brief for that project, so your working principles survive across sessions without retyping them.

Create `projects/frameworks/<project>.json`:

```json
{
  "version": "1.0",
  "description": "Ground rules for the ai_lab project",
  "rules": [
    "Prefer simple, working solutions over clever ones",
    "Every claim in a summary must trace to a source file",
    "Flag technical debt instead of silently accepting it"
  ]
}
```

When you run `context <project>`, the framework block is injected **before** the project state, so the rules frame everything that follows. Behavior is fail-soft by design: a missing, malformed, or empty framework file is skipped with a log warning -- it never blocks brief generation. The generated brief records which framework version (and how many rules) was injected.

---

## Requirements

- Linux (Ubuntu 22.04+ or Mint 22+)
- Python 3.10+
- rclone v1.73+
- Proton Drive account
- Anthropic API key with credits

---

## Install

### 1. Python environment

```bash
python3 -m venv ~/claude-sync-venv
source ~/claude-sync-venv/bin/activate
pip install anthropic watchdog schedule python-dotenv
```

### 2. Memory folder structure

```bash
mkdir -p ~/Desktop/claude-memory/{memory,projects,experiments,logs}
```

### 3. API key + machine identity

```bash
cat > ~/claude-sync-venv/.env <<'EOF'
ANTHROPIC_API_KEY=your_key_here
CLAUDE_SYNC_MACHINE=primary
CLAUDE_SYNC_PEER=secondary
CLAUDE_SYNC_OWNER=Your Name
EOF
chmod 600 ~/claude-sync-venv/.env
```

On the second machine, swap `CLAUDE_SYNC_MACHINE=secondary` / `CLAUDE_SYNC_PEER=primary`.

### 4. rclone + Proton Drive

```bash
sudo -v ; curl https://rclone.org/install.sh | sudo bash
rclone config
# Add Proton Drive as a remote named "proton"

rclone mkdir proton:claude-memory
rclone sync ~/Desktop/claude-memory/ proton:claude-memory --protondrive-replace-existing-draft=true
```

### 5. systemd service

Create `/etc/systemd/system/claude-sync.service`:

```ini
[Unit]
Description=Claude Memory Sync
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME
ExecStart=/home/YOUR_USERNAME/claude-sync-venv/bin/python /home/YOUR_USERNAME/claude-sync-venv/claude_sync.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable claude-sync
sudo systemctl start claude-sync
```

### 6. Cron jobs

Once a day, staggered -- push first, pull half an hour later:

**Machine 1 (push up, 03:00):**
```
0 3 * * * /usr/bin/rclone sync /home/YOUR_USERNAME/Desktop/claude-memory/ proton:claude-memory --protondrive-replace-existing-draft=true --config /home/YOUR_USERNAME/.config/rclone/rclone.conf --log-file=/home/YOUR_USERNAME/Desktop/claude-memory/logs/rclone.log
```

**Machine 2 (pull down, 03:30):**
```
30 3 * * * /usr/bin/rclone sync proton:claude-memory /home/YOUR_USERNAME/Desktop/claude-memory/ --protondrive-replace-existing-draft=true --config /home/YOUR_USERNAME/.config/rclone/rclone.conf --log-file=/home/YOUR_USERNAME/Desktop/claude-memory/logs/rclone.log
```

> **Important -- three rules learned in production:**
>
> 1. Always use the full `/usr/bin/rclone` path, not just `rclone`. Cron runs in a stripped environment and may not find the binary otherwise.
> 2. Always include `--config /home/YOUR_USERNAME/.config/rclone/rclone.conf`. Without it, cron can't find your stored Proton auth token and re-authenticates on every sync cycle -- which triggers repeated "new login" security alerts on your phone and creates phantom sessions in your Proton account. Adding the config flag fixes this completely.
> 3. **Once a day is deliberate -- and never schedule two rclone-to-Proton jobs at the same time on one machine.** Proton issues a single-use refresh token per rclone config: frequent syncs multiply token-refresh events and draft-replacement retries, and two jobs sharing one config can race to refresh the same token, which we've seen crash rclone mid-sync. Daily, staggered slots have been boring-reliable. If you add more Proton sync jobs later, give each its own time slot.

---

## Usage

```bash
# Generate startup context for a project
python ~/claude-sync-venv/claude_api_sync.py context ai_lab

# Log what you worked on
python ~/claude-sync-venv/claude_api_sync.py log ai_lab "what we worked on today"

# Update project state
python ~/claude-sync-venv/claude_api_sync.py update ai_lab "project notes" "task1,task2"
```

To give a project standing rules, drop a framework file at `projects/frameworks/ai_lab.json` (format above) -- every subsequent `context ai_lab` brief opens with those rules.

---

## Security

- API key lives in a local `.env` file with `chmod 600` -- never synced, never committed
- All Proton Drive data is end-to-end encrypted by Proton
- No sensitive personal data stored in memory files
- `.env` is in `.gitignore` -- see `.env.example` for the required format
- Memory files contain project context only -- no passwords, no health data, no financials

---

## Design Decisions

**Why not build a custom chat interface?**  
Anthropic ships native persistent memory and actively improves claude.ai. Building a local replacement would sacrifice mobile access, artifacts, voice mode, web search, and everything else that makes Claude useful. This system stops at the structured backup layer -- maximum value, zero technical debt.

**Why Proton Drive?**  
End-to-end encryption by default. No extra configuration needed to keep your context private.

**Why rclone + systemd + cron instead of a custom daemon?**  
Standard Linux tools. Reliable, well-documented, and won't break when dependencies update.

**Why sync once a day instead of every 30 minutes?**  
The original design synced every 30 minutes. Production experience moved it to daily: Proton's single-use refresh token makes high-frequency syncs a source of auth races, draft-replacement retries, and phantom-session alerts, and memory context simply doesn't change fast enough to justify 48 syncs a day. The local heartbeat still runs every 30 minutes -- only the cloud leg is daily.

---

## Built With

- Python 3 + `schedule` + `anthropic` SDK
- rclone + Proton Drive
- systemd + cron
- Linux Mint 22 and Ubuntu 22.04

---

## License

MIT -- see [LICENSE](LICENSE) for details.

Built by [Brent Bowers](https://github.com/BrentlBowers) with Claude AI -- April 2026, updated August 2026.
