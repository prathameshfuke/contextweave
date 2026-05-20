import requests
from typing import List, Dict, Any, Optional
from rich.console import Console

console = Console()

class VaultAPI:
    def __init__(self, api_key: str, port: int = 27123):
        self.api_key = api_key
        self.port = port
        self.base_url = f"http://localhost:{port}"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "text/markdown"
        }

    def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            response = requests.get(f"{self.base_url}/", timeout=2)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def read_note(self, path: str) -> str:
        url = f"{self.base_url}/vault/{path}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.text

    def write_note(self, path: str, content: str) -> bool:
        url = f"{self.base_url}/vault/{path}"
        response = requests.put(url, headers=self.headers, data=content.encode("utf-8"), timeout=10)
        return response.status_code in [200, 204]

    def list_notes(self, folder: str) -> List[str]:
        url = f"{self.base_url}/vault/{folder}/"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            return [item for item in data if isinstance(item, str)]
        elif isinstance(data, dict) and "files" in data:
            return data["files"]
        return []

    def search(self, query: str) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/search/simple/"
        payload = {"query": query}
        response = requests.post(url, headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, json=payload)
        response.raise_for_status()
        return response.json()
