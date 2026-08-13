#!/usr/bin/env python3
"""
claude_api_sync.py
Claude Memory Sync -- API Intelligence Layer
v1.1.1 -- Model updated to claude-sonnet-5 (claude-sonnet-4-20250514 is deprecated)
v1.1.0 -- Added framework file injection into startup brief

Commands:
  context  <project>              Generate startup context brief
  log      <project> <notes>      Log session summary
  update   <project> <notes> <tasks>  Update project state

Framework injection:
  Loads projects/frameworks/<project>.json if it exists.
  Framework rules are prepended to the startup brief before project state.
  Missing or malformed framework files are skipped silently (warning logged).
"""

import os
import json
import sys
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import anthropic

# -- Config ------------------------------------------------------------------

MEMORY_DIR = Path.home() / "Desktop" / "claude-memory"
PROJECTS_DIR = MEMORY_DIR / "projects"
FRAMEWORKS_DIR = PROJECTS_DIR / "frameworks"
MEMORY_FILE = MEMORY_DIR / "memory" / "owner_context.json"
LOG_DIR = MEMORY_DIR / "logs"

LOG_DIR.mkdir(parents=True, exist_ok=True)
FRAMEWORKS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "api_sync.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

load_dotenv(Path.home() / "claude-sync-venv" / ".env")
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-5"


# -- Helpers -----------------------------------------------------------------

def load_json(path: Path) -> dict | None:
    """Load a JSON file. Returns None if missing or malformed."""
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logging.warning(f"Malformed JSON at {path}: {e}")
        return None


def save_json(path: Path, data: dict):
    """Write a JSON file with pretty formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_project_state(project_name: str) -> dict | None:
    """Load project state JSON from projects/<project>.json."""
    path = PROJECTS_DIR / f"{project_name}.json"
    state = load_json(path)
    if state is None:
        logging.error(f"Project state not found or invalid: {path}")
    return state


def load_framework(project_name: str) -> dict | None:
    """
    Load framework rules from projects/frameworks/<project>.json.
    Returns None if file is missing, malformed, or has no rules.
    Logs a warning for malformed files but never raises.
    """
    path = FRAMEWORKS_DIR / f"{project_name}.json"

    if not path.exists():
        logging.info(f"No framework file found for '{project_name}' -- skipping injection.")
        return None

    data = load_json(path)

    if data is None:
        logging.warning(f"Framework file for '{project_name}' is malformed -- skipping injection.")
        return None

    rules = data.get("rules", [])
    if not rules:
        logging.warning(f"Framework file for '{project_name}' has empty rules -- skipping injection.")
        return None

    logging.info(f"Framework loaded for '{project_name}' -- {len(rules)} rules, v{data.get('version', 'unknown')}.")
    return data


def build_framework_block(framework: dict) -> str:
    """Format framework data as a readable block for the startup brief."""
    lines = []
    lines.append("=== REASONING FRAMEWORK ===")
    if framework.get("description"):
        lines.append(f"Description: {framework['description']}")
    if framework.get("version"):
        lines.append(f"Version: {framework['version']}")
    lines.append("Rules:")
    for i, rule in enumerate(framework["rules"], 1):
        lines.append(f"  {i}. {rule}")
    lines.append("=== END FRAMEWORK ===")
    return "\n".join(lines)


def load_owner_context() -> dict:
    """Load owner context. Returns empty dict if missing."""
    return load_json(MEMORY_FILE) or {}


# -- Core Commands -----------------------------------------------------------

def get_startup_context(project_name: str):
    """
    Generate a startup context brief for a project.
    Framework rules (if present) are injected before project state.
    """
    print(f"Generating startup context for: {project_name}")

    # Load project state (required)
    state = load_project_state(project_name)
    if state is None:
        print(f"Error: No project state found for '{project_name}'. Check projects/{project_name}.json exists.")
        sys.exit(1)

    # Load framework (optional)
    framework = load_framework(project_name)

    # Load owner context
    owner = load_owner_context()

    # Build the prompt payload -- framework first, then state
    sections = []

    if framework:
        sections.append(build_framework_block(framework))

    sections.append("=== PROJECT STATE ===")
    sections.append(json.dumps(state, indent=2))
    sections.append("=== END PROJECT STATE ===")

    if owner:
        sections.append("=== OWNER CONTEXT ===")
        sections.append(json.dumps(owner, indent=2))
        sections.append("=== END OWNER CONTEXT ===")

    payload = "\n\n".join(sections)

    prompt = f"""You are generating a startup context brief for a Claude AI session.

The user is starting a new session for the project: {project_name}

Here is the full context payload:

{payload}

Generate a concise, practical startup brief that:
1. Opens with the reasoning framework rules (if provided) so they guide the session
2. Summarizes current project state -- what's been done, what's in progress, what's next
3. Highlights the most important tasks or open questions
4. Sets the right tone and context for the session to continue productively

Keep it tight. No fluff. Sound like a smart assistant handing off a clean briefing."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    brief = response.content[0].text

    # Save the generated brief
    brief_path = MEMORY_DIR / "memory" / f"{project_name}_startup_brief.md"
    with open(brief_path, "w") as f:
        f.write(f"# Startup Brief: {project_name}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        if framework:
            f.write(f"Framework: v{framework.get('version', 'unknown')} -- {len(framework['rules'])} rules injected\n")
        else:
            f.write("Framework: none\n")
        f.write("\n---\n\n")
        f.write(brief)

    logging.info(f"Startup brief generated for '{project_name}'. Framework injected: {framework is not None}.")
    print("\n" + "="*60)
    print(brief)
    print("="*60)
    print(f"\nBrief saved to: {brief_path}")


def log_session(project_name: str, notes: str):
    """Log what happened in a session. Generates an AI summary."""
    print(f"Logging session for: {project_name}")

    state = load_project_state(project_name)
    if state is None:
        print(f"Error: No project state found for '{project_name}'.")
        sys.exit(1)

    prompt = f"""Summarize this session log entry for project '{project_name}'.

Current project state:
{json.dumps(state, indent=2)}

Session notes:
{notes}

Write a concise 3-5 sentence summary of what was accomplished. Focus on progress made, decisions taken, and what comes next. No fluff."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )

    summary = response.content[0].text
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Append to session log
    log_path = MEMORY_DIR / "memory" / f"{project_name}_session_log.md"
    with open(log_path, "a") as f:
        f.write(f"\n## Session: {timestamp}\n\n")
        f.write(f"**Raw notes:** {notes}\n\n")
        f.write(f"**Summary:** {summary}\n\n")
        f.write("---\n")

    logging.info(f"Session logged for '{project_name}'.")
    print(f"Session logged: {log_path}")
    print(f"\nSummary: {summary}")


def update_project(project_name: str, notes: str, tasks: str):
    """Update project state JSON with new notes and tasks."""
    print(f"Updating project state for: {project_name}")

    path = PROJECTS_DIR / f"{project_name}.json"
    state = load_project_state(project_name) or {}

    state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state["notes"] = notes
    state["current_tasks"] = [t.strip() for t in tasks.split(",") if t.strip()]

    save_json(path, state)
    logging.info(f"Project state updated for '{project_name}'.")
    print(f"Project state updated: {path}")


# -- Entry Point -------------------------------------------------------------

def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python claude_api_sync.py context  <project>")
        print("  python claude_api_sync.py log      <project> <notes>")
        print("  python claude_api_sync.py update   <project> <notes> <tasks>")
        sys.exit(1)

    command = sys.argv[1]
    project = sys.argv[2]

    if command == "context":
        get_startup_context(project)

    elif command == "log":
        if len(sys.argv) < 4:
            print("Usage: python claude_api_sync.py log <project> <notes>")
            sys.exit(1)
        log_session(project, sys.argv[3])

    elif command == "update":
        if len(sys.argv) < 5:
            print("Usage: python claude_api_sync.py update <project> <notes> <tasks>")
            sys.exit(1)
        update_project(project, sys.argv[3], sys.argv[4])

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
