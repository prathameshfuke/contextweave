import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.progress import Progress
from .config import load_config
from .vault import Vault

console = Console()

class Retrieval:
    def __init__(self):
        self.config = load_config()
        self.chroma_path = Path.home() / ".contextweave" / "chroma"
        self._model = None
        self._client = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError:
                console.print("[yellow]Run: uv add sentence-transformers chromadb[/yellow]")
                exit(1)
        return self._model

    def _get_client(self):
        if self._client is None:
            try:
                import chromadb
                self._client = chromadb.PersistentClient(path=str(self.chroma_path))
            except ImportError:
                console.print("[yellow]Run: uv add sentence-transformers chromadb[/yellow]")
                exit(1)
        return self._client

    def index_vault(self, project_slug: str):
        vault = Vault(self.config["vault_path"])
        project_folder = Path("projects") / project_slug
        notes = vault.list_notes(str(project_folder))
        
        # Filter sessions older than 30 days
        filtered_notes = []
        now = datetime.now()
        thirty_days_ago = now - timedelta(days=30)

        for note in notes:
            if "sessions/" in note:
                try:
                    # Expecting YYYY-MM-DD-agent-feature.md
                    filename = Path(note).name
                    date_part = "-".join(filename.split("-")[:3])
                    note_date = datetime.strptime(date_part, "%Y-%m-%d")
                    if note_date < thirty_days_ago:
                        continue
                except:
                    pass
            filtered_notes.append(note)

        client = self._get_client()
        model = self._get_model()
        collection = client.get_or_create_collection(name=project_slug)

        with Progress() as progress:
            task = progress.add_task(f"[cyan]Indexing {project_slug}...", total=len(filtered_notes))
            
            for note in filtered_notes:
                try:
                    content = vault.read_note(note)
                    # Simple chunking by words
                    words = content.split()
                    chunk_size = 300
                    chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
                    
                    ids = [f"{note}_{i}" for i in range(len(chunks))]
                    metadatas = [{"note_path": note} for _ in range(len(chunks))]
                    embeddings = model.encode(chunks).tolist()
                    
                    collection.upsert(
                        ids=ids,
                        embeddings=embeddings,
                        documents=chunks,
                        metadatas=metadatas
                    )
                except Exception as e:
                    console.print(f"[red]Error indexing {note}: {e}[/red]")
                
                progress.update(task, advance=1)
        
        console.print(f"[green]Successfully indexed {len(filtered_notes)} notes for '{project_slug}'.[/green]")

    def index_single_note(self, project_slug: str, note_path: str):
        vault = Vault(self.config["vault_path"])
        
        if "sessions/" in note_path:
            try:
                filename = Path(note_path).name
                date_part = "-".join(filename.split("-")[:3])
                note_date = datetime.strptime(date_part, "%Y-%m-%d")
                thirty_days_ago = datetime.now() - timedelta(days=30)
                if note_date < thirty_days_ago:
                    return
            except:
                pass

        try:
            content = vault.read_note(note_path)
            words = content.split()
            chunk_size = 300
            chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]

            if not chunks:
                return

            ids = [f"{note_path}_{i}" for i in range(len(chunks))]
            metadatas = [{"note_path": note_path} for _ in range(len(chunks))]
            
            client = self._get_client()
            model = self._get_model()
            collection = client.get_or_create_collection(name=project_slug)
            
            embeddings = model.encode(chunks).tolist()

            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadatas
            )
        except Exception as e:
            console.print(f"[red]Error indexing {note_path}: {e}[/red]")

    def delete_note_from_index(self, project_slug: str, note_path: str):
        try:
            client = self._get_client()
            collection = client.get_or_create_collection(name=project_slug)
            collection.delete(where={"note_path": note_path})
        except Exception as e:
            console.print(f"[red]Error deleting {note_path} from index: {e}[/red]")

    def search(self, project_slug: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        client = self._get_client()
        model = self._get_model()
        collection = client.get_or_create_collection(name=project_slug)
        
        query_embedding = model.encode([query]).tolist()
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=top_k
        )
        
        formatted_results = []
        if results['documents']:
            for i in range(len(results['documents'][0])):
                formatted_results.append({
                    "note_path": results['metadatas'][0][i]['note_path'],
                    "excerpt": results['documents'][0][i],
                    "score": results['distances'][0][i] if 'distances' in results else 0
                })
        return formatted_results

    def build_context_prompt(self, project_slug: str, query: str, max_tokens: int = 3000) -> str:
        results = self.search(project_slug, query, top_k=10)
        
        prompt = f"# Project Context: {project_slug}\n\n## Relevant Notes\n\n"
        current_tokens = len(prompt) // 4
        
        for res in results:
            note_block = f"### {res['note_path']}\n{res['excerpt']}\n\n"
            note_tokens = len(note_block) // 4
            
            if current_tokens + note_tokens > max_tokens:
                break
            
            prompt += note_block
            current_tokens += note_tokens
            
        return prompt
