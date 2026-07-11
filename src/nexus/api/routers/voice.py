"""Voice router — transcribe and intent parsing."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel

from nexus.models.user import User
from nexus.services.voice import parse_intent, parse_intent_llm, speak_text, transcribe_audio
from nexus.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])


class TranscribeResponse(BaseModel):
    text: str | None
    intent: dict
    source: str  # "whisper" or "text_input"


@router.post("/transcribe", response_model=TranscribeResponse)
async def voice_transcribe(
    text: str | None = None,
    audio: UploadFile | None = None,
    use_llm: bool = False,
    user: User = Depends(get_current_user),
):
    """Transcribe audio or parse text input into a command intent.

    Provide either `text` (plain string) or `audio` (WAV/MP3 file upload).
    Set `use_llm=true` for LLM-powered intent parsing (fallback for complex commands).
    """
    transcribed: str | None = None

    if audio is not None:
        import tempfile
        from pathlib import Path

        content = await audio.read()
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(content)
        tmp.close()
        audio_path = Path(tmp.name)

        transcribed = transcribe_audio(audio_path)
        audio_path.unlink(missing_ok=True)

        if transcribed is None:
            raise HTTPException(
                status_code=503,
                detail="Transcription unavailable — OPENAI_API_KEY not configured or API error",
            )
    elif text is not None:
        transcribed = text.strip()
    else:
        raise HTTPException(status_code=400, detail="Provide 'text' or 'audio' file")

    if not transcribed:
        return TranscribeResponse(text=None, intent={"intent": "unknown", "entities": {}}, source="whisper")

    intent = parse_intent_llm(transcribed) if use_llm else parse_intent(transcribed)

    return TranscribeResponse(
        text=transcribed,
        intent=intent,
        source="whisper" if audio else "text_input",
    )


@router.post("/speak")
async def voice_speak(
    body: dict,
    user: User = Depends(get_current_user),
):
    """Convert text to speech and return MP3 audio.

    Body: {"text": "Hello world", "voice": "alloy"}
    Returns raw audio/mpeg bytes.
    """
    from fastapi.responses import Response

    text = body.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    voice = body.get("voice", "alloy")

    audio = speak_text(text, voice=voice)
    if audio is None:
        raise HTTPException(
            status_code=503,
            detail="TTS unavailable — OPENAI_API_KEY not configured or API error",
        )
    return Response(content=audio, media_type="audio/mpeg")
