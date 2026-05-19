import os
import frontmatter
from pathlib import Path
from datetime import datetime

from .config import load_config
from .vault import Vault
from .llm import summarise

def _extract_diff_info(content: str) -> dict:
    decisions = []
    files_modified = []
    open_questions = []
    
    in_decisions = False
    in_files = False
    in_questions = False
    
    for line in content.split('\n'):
        line = line.strip()
        
        if line.startswith('## Decisions'):
            in_decisions = True
            in_files = False
            in_questions = False
            continue
        elif line.startswith('## Files Modified') or line.startswith('## Files'):
            in_decisions = False
            in_files = True
            in_questions = False
            continue
        elif line.startswith('## Open Questions'):
            in_decisions = False
            in_files = False
            in_questions = True
            continue
        elif line.startswith('## '):
            in_decisions = False
            in_files = False
            in_questions = False
            continue
            
        if line.startswith('- '):
            item = line[2:]
            if in_decisions:
                decisions.append(item)
            elif in_files:
                files_modified.append(item)
            elif in_questions:
                open_questions.append(item)
                
    return {
        "decisions": decisions,
        "files_modified": files_modified,
        "open_questions": open_questions
    }

def session_diff(project_slug: str, session_a_path: str, session_b_path: str) -> str:
    config = load_config()
    vault = Vault(config.get("vault_path"))
    
    content_a = vault.read_note(session_a_path)
    content_b = vault.read_note(session_b_path)
    
    post_a = frontmatter.loads(content_a)
    post_b = frontmatter.loads(content_b)
    
    info_a = _extract_diff_info(content_a)
    info_b = _extract_diff_info(content_b)
    
    raw_data = f"""
=== Session A ({Path(session_a_path).name}) ===
Agent: {post_a.get('agent', 'Unknown')}
Feature: {post_a.get('feature', 'Unknown')}
Decisions: {', '.join(info_a['decisions']) if info_a['decisions'] else 'None'}
Files Modified: {', '.join(info_a['files_modified']) if info_a['files_modified'] else 'None'}
Open Questions: {', '.join(info_a['open_questions']) if info_a['open_questions'] else 'None'}

=== Session B ({Path(session_b_path).name}) ===
Agent: {post_b.get('agent', 'Unknown')}
Feature: {post_b.get('feature', 'Unknown')}
Decisions: {', '.join(info_b['decisions']) if info_b['decisions'] else 'None'}
Files Modified: {', '.join(info_b['files_modified']) if info_b['files_modified'] else 'None'}
Open Questions: {', '.join(info_b['open_questions']) if info_b['open_questions'] else 'None'}
    """
    
    instruction = """
Given two AI session logs from the same project, produce a diff summary.
Show: what decisions changed or were added, what files were newly touched,
what questions were resolved, what new questions appeared.
Be specific. Output markdown with headers: 
## New Decisions
## Newly Touched Files
## Resolved Questions
## New Open Questions
"""

    return summarise(raw_data, instruction=instruction)

def latest_diff(project_slug: str) -> str:
    config = load_config()
    vault = Vault(config.get("vault_path"))
    project_folder = f"projects/{project_slug}"
    sessions_dir = f"{project_folder}/sessions"
    
    session_notes = vault.list_notes(sessions_dir)
    
    # Extract dates and sort
    parsed_sessions = []
    for note in session_notes:
        content = vault.read_note(note)
        post = frontmatter.loads(content)
        started = post.get('started')
        if started:
            try:
                dt = datetime.fromisoformat(str(started).replace('Z', '+00:00'))
                if dt.tzinfo:
                    dt = dt.replace(tzinfo=None)
                parsed_sessions.append((dt, note))
            except ValueError:
                pass
                
    if len(parsed_sessions) < 2:
        return "Not enough sessions to generate a diff."
        
    parsed_sessions.sort(key=lambda x: x[0], reverse=True)
    
    session_b_path = parsed_sessions[0][1] # newest
    session_a_path = parsed_sessions[1][1] # second newest
    
    diff_md = session_diff(project_slug, session_a_path, session_b_path)
    
    diff_filename = f"{project_folder}/agents/latest-diff.md"
    
    final_content = f"""---
generated: {datetime.now().isoformat()}
project: {project_slug}
session_a: {Path(session_a_path).name}
session_b: {Path(session_b_path).name}
---

{diff_md}
"""
    vault.write_note(diff_filename, final_content)
    return diff_md
