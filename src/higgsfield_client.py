"""
Higgsfield API Client — Image & Video Generation (Veo 3.1)
"""
import requests
import time

BASE_URL = "https://api.higgsfield.ai"

class HiggsFieldClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def generate_image(self, prompt: str, model: str = "nano_banana_pro",
                       aspect_ratio: str = "1:1", count: int = 1) -> dict:
        response = requests.post(
            f"{BASE_URL}/v1/images/generations",
            headers=self.headers,
            json={"model": model, "prompt": prompt,
                  "aspect_ratio": aspect_ratio, "count": count}
        )
        response.raise_for_status()
        return self._poll_job(response.json()["id"])

    def generate_video(self, prompt: str, model: str = "veo3_1_lite",
                       aspect_ratio: str = "9:16", duration: int = 8,
                       start_image_url: str = None) -> dict:
        payload = {
            "model": model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "duration": duration,
        }
        if start_image_url:
            payload["medias"] = [{"value": start_image_url, "role": "start_image"}]
        response = requests.post(
            f"{BASE_URL}/v1/videos/generations",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        return self._poll_job(response.json()["id"], timeout=300)

    def upload_image(self, image_path: str) -> str:
        with open(image_path, "rb") as f:
            response = requests.post(
                f"{BASE_URL}/v1/media/upload",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": f}
            )
        response.raise_for_status()
        return response.json()["id"]

    def download_result(self, job: dict, output_path: str) -> str:
        url = job.get("results", [{}])[0].get("url")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"  ✅ Downloaded to {output_path}")
        return output_path

    def _poll_job(self, job_id: str, timeout: int = 120, interval: int = 5) -> dict:
        elapsed = 0
        while elapsed < timeout:
            r = requests.get(f"{BASE_URL}/v1/jobs/{job_id}", headers=self.headers)
            r.raise_for_status()
            job = r.json()
            status = job.get("status")
            if status == "completed":
                return job
            elif status == "failed":
                raise Exception(f"Job failed: {job.get('error')}")
            print(f"  ⏳ {job_id}: {status} ({elapsed}s)")
            time.sleep(interval)
            elapsed += interval
        raise TimeoutError(f"Job {job_id} timed out")
