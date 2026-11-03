import httpx
from app.config import get_settings
from typing import Optional

settings = get_settings()


def _get_azure_token() -> Optional[str]:
    key = settings.AZURE_TTS_KEY
    region = settings.AZURE_TTS_REGION
    if not key or not region:
        return None
    url = f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
    headers = {"Ocp-Apim-Subscription-Key": key}
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(url, headers=headers)
            r.raise_for_status()
            return r.text
    except Exception:
        return None


def synthesize_text(text: str, voice: str = "zh-CN-XiaoxiaoNeural", output_format: str = "audio-16khz-32kbitrate-mono-mp3") -> bytes:
    """Synthesize text to audio bytes using Azure TTS. Returns MP3/WAV bytes.

    Requires `AZURE_TTS_KEY` and `AZURE_TTS_REGION` in settings.
    """
    token = _get_azure_token()
    key = settings.AZURE_TTS_KEY
    region = settings.AZURE_TTS_REGION
    if not token and not key:
        raise RuntimeError("Azure TTS not configured (AZURE_TTS_KEY/AZURE_TTS_REGION)")

    tts_url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"

    ssml = f"""<speak version='1.0' xml:lang='zh-CN'>
  <voice name='{voice}'>{text}</voice>
</speak>"""

    headers = {
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": output_format,
        "User-Agent": "baiqipu-tts/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        headers["Ocp-Apim-Subscription-Key"] = key

    with httpx.Client(timeout=30.0) as client:
        r = client.post(tts_url, headers=headers, content=ssml.encode("utf-8"))
        r.raise_for_status()
        return r.content
