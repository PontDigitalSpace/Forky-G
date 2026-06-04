"""
Descript API Client — Video Editing & Export
"""
import requests
import time
from pathlib import Path

BASE_URL = "https://api.descript.com/v2"

class DescriptClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def create_project(self, name: str) -> dict:
        r = requests.post(f"{BASE_URL}/projects",
                          headers=self.headers, json={"name": name})
        r.raise_for_status()
        return r.json()

    def upload_media(self, project_id: str, file_path: str,
                     media_name: str = None) -> dict:
        if not media_name:
            media_name = Path(file_path).name
        file_size = Path(file_path).stat().st_size
        r = requests.post(
            f"{BASE_URL}/projects/{project_id}/media",
            headers=self.headers,
            json={"name": media_name, "content_type": "video/mp4",
                  "file_size": file_size}
        )
        r.raise_for_status()
        upload_data = r.json()
        with open(file_path, "rb") as f:
            put_r = requests.put(
                upload_data["upload_url"], data=f,
                headers={"Content-Type": "application/octet-stream"}
            )
        put_r.raise_for_status()
        print(f"  ✅ Uploaded {media_name} to Descript")
        return upload_data

    def export_video(self, project_id: str, composition_id: str,
                     resolution: str = "1080p") -> str:
        r = requests.post(
            f"{BASE_URL}/projects/{project_id}/compositions/{composition_id}/exports",
            headers=self.headers,
            json={"resolution": resolution, "format": "mp4"}
        )
        r.raise_for_status()
        export_id = r.json()["id"]
        for _ in range(60):
            sr = requests.get(f"{BASE_URL}/exports/{export_id}",
                              headers=self.headers)
            s = sr.json()
            if s.get("status") == "completed":
                return s["download_url"]
            time.sleep(5)
        raise TimeoutError("Export timed out")
