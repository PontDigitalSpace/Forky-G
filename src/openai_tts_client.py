"""
OpenAI TTS Client — Voice Over Generation in French, English and Spanish
"""
import requests

BASE_URL = "https://api.openai.com/v1/audio/speech"

# nova: natural, works great for FR/EN/ES
VOICES = {
    "fr": "nova",
    "en": "nova",
    "es": "nova",
}

class OpenAITTSClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def generate_voiceover(self, text: str, output_path: str,
                           lang: str = "fr",
                           voice: str = None,
                           speed: float = 1.0) -> str:
        selected_voice = voice or VOICES.get(lang, "nova")
        response = requests.post(
            BASE_URL,
            headers=self.headers,
            json={
                "model": "tts-1",
                "input": text,
                "voice": selected_voice,
                "speed": speed,
                "response_format": "mp3"
            }
        )
        response.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"  ✅ Voice over saved: {output_path}")
        return output_path
