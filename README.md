# Claude Memory Sync System

A lightweight, automated memory sync system that gives Claude persistent context across devices and sessions.

## The Problem

Claude has no memory between conversations by default. Every new chat starts fresh -- no project history, no context, no idea what you were working on. For someone running multiple AI agents across multiple projects on two laptops, this is a real problem.

## The Solution

This system stores context, project state, and session history in structured JSON files on your local machine. Those files automatically sync to Proton Drive (end-to-end encrypted) every 30 minutes via rclone and cron -- keeping two machines always in sync.

## Architecture

See claude_memory_system_full_architecture.html and claude_memory_sync_data_flow.html for full visual diagrams. Open either file in any browser.

## How It Works

- claude_sync.py -- runs continuously via systemd, writes heartbeat and context files every 30 min
- claude_api_sync.py -- uses the Claude API to read memory files, generate startup context, and log session summaries
- rclone syncs the memory folder to Proton Drive every 30 min via cron
- Machine 1 pushes UP to Proton Drive
- Machine 2 pulls DOWN from Proton Drive
- Both machines auto-start on boot via systemd

## File Structure

~/Desktop/claude-memory/
  memory/       -- core context files, owner info, heartbeat, sessions
  projects/     -- per-project state, one JSON file per project
  experiments/  -- experiment logs and prompt test results
  logs/         -- sync activity logs

## Requirements

- Linux (Ubuntu or Mint)
- Python 3.10+
- rclone v1.73+
- Proton Drive account
- Anthropic API key with credits

## Install

python3 -m venv ~/claude-sync-venv
source ~/claude-sync-venv/bin/activate
pip install anthropic watchdog schedule python-dotenv

mkdir -p ~/Desktop/claude-memory/{memory,projects,experiments,logs}

echo "ANTHROPIC_API_KEY=your_key_here" > ~/claude-sync-venv/.env
chmod 600 ~/claude-sync-venv/.env

sudo -v ; curl https://rclone.org/install.sh | sudo bash
rclone config
rclone mkdir proton:claude-memory
rclone sync ~/Desktop/claude-memory/ proton:claude-memory --protondrive-replace-existing-draft=true

## Systemd Service

Create /etc/systemd/system/claude-sync.service with your username substituted in:

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

Then run:
sudo systemctl daemon-reload
sudo systemctl enable claude-sync
sudo systemctl start claude-sync

## Cron Job

Machine 1 pushes up:
*/30 * * * * /usr/bin/rclone sync /home/YOUR_USERNAME/Desktop/claude-memory/ proton:claude-memory --protondrive-replace-existing-draft=true --log-file=/home/YOUR_USERNAME/Desktop/claude-memory/logs/rclone.log

Machine 2 pulls down:
*/30 * * * * /usr/bin/rclone sync proton:claude-memory /home/YOUR_USERNAME/Desktop/claude-memory/ --protondrive-replace-existing-draft=true --log-file=/home/YOUR_USERNAME/Desktop/claude-memory/logs/rclone.log

## Usage

python ~/claude-sync-venv/claude_api_sync.py context ai_lab
python ~/claude-sync-venv/claude_api_sync.py log ai_lab "what we worked on today"
python ~/claude-sync-venv/claude_api_sync.py update ai_lab "project notes" "task1,task2"

## Security

- API key stored in local .env file with chmod 600, never synced to cloud
- All Proton Drive data is end-to-end encrypted
- No sensitive personal data stored in memory files
- .env is in .gitignore and never commits to GitHub

## Built With

- Python 3 + schedule + anthropic SDK
- rclone + Proton Drive
- systemd + cron
- Linux Ubuntu 24 and Mint 22

## License

MIT
