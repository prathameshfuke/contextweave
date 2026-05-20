from datetime import datetime, timedelta
from pathlib import Path
import frontmatter

from .config import load_config
from .vault import Vault
from .llm import summarise
from .project import list_projects

def generate_brief(project_slug: str) -> str:
    config = load_config()
    vault = Vault(config.get("vault_path"))
    project_folder = f"projects/{project_slug}"
    
    now = datetime.now()
    yesterday = now - timedelta(hours=24)
    last_week = now - timedelta(days=7)
    
    sessions_dir = f"{project_folder}/sessions"
    agents_dir = f"{project_folder}/agents"
    context_dir = f"{project_folder}/context"
    web_captures_dir = f"{project_folder}/web-captures"
    
    # Session stats
    sessions_last_24h = 0
    sessions_last_7d = 0
    unique_agents = set()
    features_touched = set()
    open_questions = []
    
    session_notes = vault.list_notes(sessions_dir)
    for note_path in session_notes:
        content = vault.read_note(note_path)
        post = frontmatter.loads(content)
        
        started = post.get('started')
        if started:
            try:
                # Handle various ISO formats roughly
                dt = datetime.fromisoformat(str(started).replace('Z', '+00:00'))
                if dt.tzinfo:
                    dt = dt.replace(tzinfo=None)
                if dt > yesterday:
                    sessions_last_24h += 1
                if dt > last_week:
                    sessions_last_7d += 1
            except ValueError:
                pass
                
        agent = post.get('agent')
        if agent:
            unique_agents.add(agent)
            
        feature = post.get('feature')
        if feature:
            features_touched.add(feature)
            
        # Parse Open Questions from the session body only.
        in_open_questions = False
        for line in post.content.split('\n'):
            line = line.strip()
            if line.startswith('## Open Questions'):
                in_open_questions = True
                continue
            elif line.startswith('## '):
                in_open_questions = False
                continue
            
            if in_open_questions and line.startswith('- ') and '[x]' not in line.lower():
                open_questions.append(line[2:])
                
    # Handoff stats
    handoff_notes = vault.list_notes(agents_dir)
    handoff_notes = [n for n in handoff_notes if 'handoff' in n.lower()]
    total_handoffs = len(handoff_notes)
    
    latest_handoff_step = "None"
    if handoff_notes:
        handoff_notes.sort(reverse=True)
        latest_handoff_content = vault.read_note(handoff_notes[0])
        post = frontmatter.loads(latest_handoff_content)
        latest_handoff_step = post.get("next_task", "None")
        
    # In progress
    in_progress_content = ""
    in_progress_path = f"{context_dir}/in-progress.md"
    try:
        in_progress_content = vault.read_note(in_progress_path)
    except Exception:
        pass
        
    # Web captures
    web_captures = vault.list_notes(web_captures_dir)
    recent_captures = []
    for note_path in web_captures:
        content = vault.read_note(note_path)
        post = frontmatter.loads(content)
        captured = post.get('captured')
        if captured:
            try:
                dt = datetime.fromisoformat(str(captured).replace('Z', '+00:00'))
                if dt.tzinfo:
                    dt = dt.replace(tzinfo=None)
                if dt > yesterday:
                    recent_captures.append(post.get('title', note_path))
            except ValueError:
                pass
                
    # Build data string
    raw_data = f"""
Project: {project_slug}
Sessions Last 24h: {sessions_last_24h}
Sessions Last 7d: {sessions_last_7d}
Agents: {', '.join(unique_agents)}
Features Touched: {', '.join(features_touched)}
Total Handoffs: {total_handoffs}
Latest Exact Next Step: {latest_handoff_step}
Recent Web Captures: {', '.join(recent_captures) if recent_captures else 'None'}

In Progress Context:
{in_progress_content}

Open Questions:
{chr(10).join(['- ' + q for q in open_questions]) if open_questions else 'None'}
    """

    instruction = """
You are a project assistant writing a developer's daily brief.
Given this raw project data, write a concise daily brief in markdown.
Be direct and specific — tell the developer exactly what state their project is in,
what the AI agents did yesterday, what is blocked, and what they should do first today.
Do not be generic. Use the actual feature names, file names, and agent names from the data.
Maximum 300 words. Use these exact headers:
## Status
## Yesterday's AI Work
## Blocked / Open Questions
## Do This First Today
"""

    summary_md = summarise(raw_data, instruction=instruction)
    
    final_markdown = f"""---
generated: {datetime.now().isoformat()}
project: {project_slug}
sessions_last_24h: {sessions_last_24h}
open_questions_count: {len(open_questions)}
---

{summary_md}
"""

    brief_filename = f"daily-briefs/{datetime.now().strftime('%Y-%m-%d')}.md"
    vault.write_note(f"{project_folder}/{brief_filename}", final_markdown)
    return final_markdown

def brief_all_projects() -> dict[str, str]:
    projects = list_projects()
    results = {}
    for p in projects:
        results[p] = generate_brief(p)
    return results
