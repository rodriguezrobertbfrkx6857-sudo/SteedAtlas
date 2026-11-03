from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services import tts as tts_service

router = APIRouter(prefix="/tts", tags=["tts"])


class TTSReq(BaseModel):
    text: str
    voice: str | None = None
    format: str | None = None


@router.post("/synthesize")
def synthesize(req: TTSReq = Body(...)):
    try:
        audio = tts_service.synthesize_text(req.text, voice=req.voice or "zh-CN-XiaoxiaoNeural", output_format=req.format or "audio-16khz-32kbitrate-mono-mp3")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS error: {e}")

    return StreamingResponse(content=iter([audio]), media_type="audio/mpeg")
