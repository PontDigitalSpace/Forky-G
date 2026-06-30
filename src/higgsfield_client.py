"""
Higgsfield API Client — Image & Video Generation
Base URL: https://platform.higgsfield.ai
Auth: Key {api_key}:{api_key_secret}  (format: uuid:uuid separated by colon)
"""
import requests
import time

BASE_URL = "https://platform.higgsfield.ai"

# Image model
IMAGE_MODEL = "higgsfield-ai/soul/standard"

# Video models (text-to-video via image intermediary)
VIDEO_MODEL = "higgsfield-ai/dop/standard"


class HiggsFieldClient:
    def __init__(self, api_key: str):
        # api_key format: "uuid" or "uuid:uuid" — both supported
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def generate_image(self, prompt: str, model: str = IMAGE_MODEL,
                       aspect_ratio: str = "1:1", count: int = 1) -> dict:
        response = requests.post(
            f"{BASE_URL}/{model}",
            headers=self.headers,
            json={"prompt": prompt, "aspect_ratio": aspect_ratio},
            timeout=30
        )
        response.raise_for_status()
        request_id = response.json().get("request_id") or response.json().get("id")
        return self._poll_request(request_id, timeout=120)

    def generate_video(self, prompt: str, model: str = VIDEO_MODEL,
                       aspect_ratio: str = "9:16", duration: int = 5,
                       start_image_url: str = None) -> dict:
        payload = {"prompt": prompt, "duration": duration, "aspect_ratio": aspect_ratio}
        if start_image_url:
            payload["image_url"] = start_image_url
        response = requests.post(
            f"{BASE_URL}/{model}",
            headers=self.headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        request_id = response.json().get("request_id") or response.json().get("id")
        # Higgsfield video gen can take 5-9 min under load; poll generously so we
        # don't give up early and fall back to FFmpeg.
        return self._poll_request(request_id, timeout=600)

    def upload_image(self, image_path: str) -> str:
        """
        Upload a local image and return a public URL for Higgsfield's start image.
        Tries several no-auth hosts in order so a single host being down (0x0.st was
        returning 503) never breaks the pipeline. Returns the first working URL.
        A real browser User-Agent is sent because some hosts block default UAs.
        """
        import os
        ua = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
        fname = os.path.basename(image_path)
        errors = []

        def _catbox():
            with open(image_path, "rb") as f:
                r = requests.post("https://catbox.moe/user/api.php",
                                  data={"reqtype": "fileupload"},
                                  files={"fileToUpload": (fname, f)},
                                  headers=ua, timeout=60)
            r.raise_for_status()
            url = r.text.strip()
            if not url.startswith("http"):
                raise Exception(f"catbox unexpected: {url[:100]}")
            return url

        def _zerox():
            with open(image_path, "rb") as f:
                r = requests.post("https://0x0.st", files={"file": (fname, f)},
                                  headers=ua, timeout=60)
            r.raise_for_status()
            url = r.text.strip()
            if not url.startswith("http"):
                raise Exception(f"0x0.st unexpected: {url[:100]}")
            return url

        def _tmpfiles():
            with open(image_path, "rb") as f:
                r = requests.post("https://tmpfiles.org/api/v1/upload",
                                  files={"file": (fname, f)}, headers=ua, timeout=60)
            r.raise_for_status()
            page = r.json()["data"]["url"]               # https://tmpfiles.org/123/x.jpg
            return page.replace("tmpfiles.org/", "tmpfiles.org/dl/", 1)  # direct-download URL

        for name, fn in (("catbox.moe", _catbox), ("0x0.st", _zerox), ("tmpfiles.org", _tmpfiles)):
            try:
                url = fn()
                print(f"  📤 Uploaded frame → {url} (via {name})")
                return url
            except Exception as e:
                errors.append(f"{name}: {e}")
                print(f"  ⚠️ Upload host {name} failed: {e}")

        raise Exception("upload_image: all hosts failed — " + " | ".join(errors))

    def get_result_url(self, job: dict) -> str:
        """Extract the public URL from a completed job result."""
        if job.get("images"):
            return job["images"][0].get("url") or job["images"][0]
        elif job.get("video"):
            return job["video"].get("url") or job["video"]
        elif job.get("results"):
            return job["results"][0].get("url")
        raise Exception(f"No URL in job result: {job}")

    def download_result(self, job: dict, output_path: str) -> str:
        # Try images array first, then video object
        url = None
        if job.get("images"):
            url = job["images"][0].get("url") or job["images"][0]
        elif job.get("video"):
            url = job["video"].get("url") or job["video"]
        elif job.get("results"):
            url = job["results"][0].get("url")

        if not url:
            raise Exception(f"No download URL in job result: {job}")

        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"  ✅ Downloaded to {output_path}")
        return output_path

    def _poll_request(self, request_id: str, timeout: int = 120, interval: int = 5) -> dict:
        elapsed = 0
        while elapsed < timeout:
            r = requests.get(
                f"{BASE_URL}/requests/{request_id}/status",
                headers=self.headers,
                timeout=15
            )
            r.raise_for_status()
            job = r.json()
            status = job.get("status")
            if status == "completed":
                return job
            elif status in ("failed", "cancelled"):
                raise Exception(f"Request {status}: {job.get('error') or job}")
            print(f"  ⏳ {request_id[:8]}...: {status} ({elapsed}s)")
            time.sleep(interval)
            elapsed += interval
        raise TimeoutError(f"Request {request_id} timed out after {timeout}s")
