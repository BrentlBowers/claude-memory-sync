#!/usr/bin/env python3
"""
Claude Memory Sync Script
Thing (Primary) -- Brent Bowers AI Lab
"""

import os
import json
import logging
import schedule
import time
from datetime import datetime
from pathlib import Path
from dotenv import dotenv_values

BASE_DIR = Path.home() / "Desktop" / "claude-memory"
MEMORY_DIR = BASE_DIR / "memory"
PROJECTS_DIR = BASE_DIR / "projects"
EXPERIMENTS_DIR = BASE_DIR / "experiments"
LOGS_DIR = BASE_DIR / "logs"

ENV_PATH = Path.home() / "claude-sync-venv" / ".env"
config = dotenv_values(ENV_PATH)
API_KEY = config.get("ANTHROPIC_API_KEY")

logging.basicConfig(
    filename=LOGS_DIR / "sync.log",
    level=logging.INFO,
    format="%(asctime)s -- %(levelname)s -- %(message)s"
)

def log(msg):
    print(msg)
    logging.info(msg)

def write_memory(filename, data):
    filepath = MEMORY_DIR / filename
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    log(f"Memory written: {filename}")

def read_memory(filename):
    filepath = MEMORY_DIR / filename
    if filepath.exists():
        with open(filepath, "r") as f:
            return json.load(f)
    return {}

def write_project(project_name, data):
    filepath = PROJECTS_DIR / f"{project_name}.json"
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    log(f"Project written: {project_name}")

def read_project(project_name):
    filepath = PROJECTS_DIR / f"{project_name}.json"
    if filepath.exists():
        with open(filepath, "r") as f:
            return json.load(f)
    return {}

def log_experiment(name, data):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = EXPERIMENTS_DIR / f"{timestamp}_{name}.json"
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    log(f"Experiment logged: {name}")

def heartbeat():
    data = {
        "last_ping": datetime.now().isoformat(),
        "machine": "Thing",
        "status": "running"
    }
    write_memory("heartbeat.json", data)
    log(f"Heartbeat: {data['last_ping']}")

def init_state():
    if not (MEMORY_DIR / "context.json").exists():
        write_memory("context.json", {
            "owner": "Brent Bowers",
            "primary_machine": "Thing",
            "secondary_machine": "Drone",
            "projects": ["ViTell", "AI Lab", "LinkedIn Pro", "Personal Advisor", "Grok Intel"],
            "created": datetime.now().isoformat(),
            "notes": "Primary context file for Claude memory sync"
        })
        log("Initial context.json created")

    for project in ["vitell", "ai_lab", "linkedin_pro", "personal_advisor", "grok_intel"]:
        if not (PROJECTS_DIR / f"{project}.json").exists():
            write_project(project, {
                "name": project,
                "created": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "notes": "",
                "tasks": [],
                "experiments": []
            })
            log(f"Initial project file created: {project}")

def run_scheduler():
    schedule.every(30).minutes.do(heartbeat)
    log("Scheduler started. Heartbeat every 30 minutes.")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    log("Claude Sync starting up on Thing...")
    if not API_KEY:
        log("ERROR: No API key found. Check your .env file.")
        exit(1)
    init_state()
    heartbeat()
    run_scheduler()
