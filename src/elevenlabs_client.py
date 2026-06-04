"""
ElevenLabs TTS Client — Voice Over Generation in French
"""
import requests

BASE_URL = "https://api.elevenlabs.io/v1"

FRENCH_VOICES = {
    "charlotte": "XB0fDUnXU5powFXDhCwa",
    "daniel":    "onwK4e9ZLuTAKqWW03F9",
    "matilda":   "XrExE9yKIg1WjnnlVkGX",
}

class ElevenLabsClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json"
        }

    def generate_voiceover(self, text: str, output_path: str,
                            voice: str = "charlotte",
                            stability: float = 0.5,
                            similarity_boost: float = 0.75) -> str:
        voice_id = FRENCH_VOICES.get(voice, FRENCH_VOICES["charlotte"])
        response = requests.post(
            f"{BASE_URL}/text-to-speech/{voice_id}",
            headers=self.headers,
            json={
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": stability,
                    "similarity_boost": similarity_boost
                }
            }
        )
        response.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"  ✅ Voice over saved: {output_path}")
        return output_path

    def list_voices(self) -> list:
        r = requests.get(f"{BASE_URL}/voices", headers=self.headers)
        r.raise_for_status()
        return r.json()["voices"]
