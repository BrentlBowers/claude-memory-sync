#!/usr/bin/env python3
import json
import anthropic
from datetime import datetime
from pathlib import Path
from dotenv import dotenv_values

BASE_DIR = Path.home() / 'Desktop' / 'claude-memory'
MEMORY_DIR = BASE_DIR / 'memory'
PROJECTS_DIR = BASE_DIR / 'projects'

ENV_PATH = Path.home() / 'claude-sync-venv' / '.env'
config = dotenv_values(ENV_PATH)
API_KEY = config.get('ANTHROPIC_API_KEY')
client = anthropic.Anthropic(api_key=API_KEY)

def read_json(path):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}

def write_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f'Written: {path.name}')

def load_context():
    context = read_json(MEMORY_DIR / 'context.json')
    projects = {}
    for p in PROJECTS_DIR.glob('*.json'):
        projects[p.stem] = read_json(p)
    sessions_path = MEMORY_DIR / 'sessions.json'
    sessions = read_json(sessions_path) if sessions_path.exists() else []
    return context, projects, sessions

def build_context_block():
    context, projects, sessions = load_context()
    lines = []
    lines.append(f"Owner: {context.get('owner', 'Brent Bowers')}")
    lines.append(f"Primary machine: {context.get('primary_machine', 'Thing')}")
    lines.append(f"Projects: {', '.join(context.get('projects', []))}")
    lines.append('')
    lines.append('Project States:')
    for name, data in projects.items():
        lines.append(f'  {name}:')
        lines.append(f"    notes: {data.get('notes', 'none')}")
        tasks = data.get('tasks', [])
        if tasks:
            lines.append(f"    tasks: {', '.join(tasks)}")
        lines.append(f"    last_updated: {data.get('last_updated', 'unknown')}")
    if sessions:
        lines.append('')
        lines.append('Recent Sessions:')
        for s in sessions[-5:]:
            lines.append(f"  [{s.get('date', 'unknown')}] {s.get('project', 'unknown')}: {s.get('summary', '')}")
    return '\n'.join(lines)

def summarize_session(project, conversation_notes):
    print(f'Generating session summary for {project}...')
    prompt = ('You are summarizing a work session for Brent Bowers.\n'
              f'Project: {project}\n'
              f'Session notes: {conversation_notes}\n\n'
              'Write a 2-3 sentence summary of what was accomplished. Be specific and practical.\n'
              'Focus on: what was built or decided, what the current state is, and what comes next.\n'
              'Keep it tight -- this will be read at the start of the next session as context.')
    message = client.messages.create(
        model='claude-sonnet-4-20250514',
        max_tokens=300,
        messages=[{'role': 'user', 'content': prompt}]
    )
    return message.content[0].text.strip()

def update_project(project_name, notes='', tasks=None):
    path = PROJECTS_DIR / f'{project_name}.json'
    data = read_json(path)
    if notes:
        data['notes'] = notes
    if tasks:
        data['tasks'] = tasks
    data['last_updated'] = datetime.now().isoformat()
    write_json(path, data)

def log_session(project, conversation_notes):
    summary = summarize_session(project, conversation_notes)
    sessions_path = MEMORY_DIR / 'sessions.json'
    sessions = read_json(sessions_path) if sessions_path.exists() else []
    sessions.append({
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'project': project,
        'summary': summary,
        'raw_notes': conversation_notes
    })
    sessions = sessions[-50:]
    write_json(sessions_path, sessions)
    print(f'Session logged: {summary}')
    return summary

def get_startup_context(project):
    context_block = build_context_block()
    prompt = ('You are Claude, Brent Bowers AI assistant.\n'
              'Here is your current memory and context:\n\n'
              f'{context_block}\n\n'
              f'Current project: {project}\n\n'
              f'In 3-4 sentences, summarize what you know about where things stand with {project} '
              'and what Brent is likely working on. Be direct and practical.')
    message = client.messages.create(
        model='claude-sonnet-4-20250514',
        max_tokens=300,
        messages=[{'role': 'user', 'content': prompt}]
    )
    return message.content[0].text.strip()

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Usage:')
        print('  python claude_api_sync.py context <project>')
        print('  python claude_api_sync.py log <project> "session notes"')
        print('  python claude_api_sync.py update <project> "notes" "task1,task2"')
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'context' and len(sys.argv) >= 3:
        project = sys.argv[2]
        print('\n--- STARTUP CONTEXT ---')
        print(get_startup_context(project))
        print('--- END CONTEXT ---\n')
    elif cmd == 'log' and len(sys.argv) >= 4:
        project = sys.argv[2]
        notes = sys.argv[3]
        log_session(project, notes)
    elif cmd == 'update' and len(sys.argv) >= 4:
        project = sys.argv[2]
        notes = sys.argv[3]
        tasks = sys.argv[4].split(',') if len(sys.argv) >= 5 else []
        update_project(project, notes, tasks)
        print(f'Project {project} updated.')
    else:
        print('Unknown command.')