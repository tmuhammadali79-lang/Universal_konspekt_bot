"""OpenAI Whisper API — audio to text transcription with dialect normalization."""

import logging
from pathlib import Path
from openai import AsyncOpenAI
from config import OPENAI_API_KEY, WHISPER_MODEL, GPT_MODEL, MAX_FILE_SIZE_MB
from services.media_processor import split_audio

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

DIALECT_NORMALIZE_PROMPT = """Sen o'zbek tili bo'yicha lingvist-ekspertsan.
Quyidagi matn ovozli xabardan transkripsiya qilingan. Unda shevaga xos so'zlar, noto'g'ri grammatika yoki nutq xatolari bo'lishi mumkin.

Sening vazifang:
1. Shevadagi so'zlarni adabiy o'zbek tiliga o'gir (masalan: "ketyapti" → "ketyapti", "buam" → "buvam", "manavi" → "mana bu", "qiyvotdi" → "qilyapti").
2. Mantiqiy xatolarni to'g'irla.
3. Takroriy so'zlar va to'ldirgich so'zlarni ("ee", "mm", "nima deydi", "shunday") olib tashla.
4. Gapning ma'nosini o'zgartirma, faqat shaklini tuzat.
5. Natijani toza, ravon va tushunarli qilib yoz.

MUHIM: Faqat tozalangan matnni qaytar. Hech qanday izoh yoki tushuntirish yozma."""


async def transcribe_audio(file_path: Path) -> str:
    """Transcribe an audio file using Whisper.

    Automatically splits files larger than MAX_FILE_SIZE_MB.
    Returns the full transcript text.
    """
    file_size_mb = file_path.stat().st_size / (1024 * 1024)

    if file_size_mb > MAX_FILE_SIZE_MB:
        logger.info("File %.1f MB > %d MB, splitting...", file_size_mb, MAX_FILE_SIZE_MB)
        chunks = await split_audio(file_path)
        texts: list[str] = []
        for chunk in chunks:
            text = await _transcribe_single(chunk)
            texts.append(text)
        raw_text = " ".join(texts)
    else:
        raw_text = await _transcribe_single(file_path)

    # Apply dialect normalization
    if raw_text.strip():
        raw_text = await normalize_dialect(raw_text)

    return raw_text


async def _transcribe_single(file_path: Path) -> str:
    """Send a single file to Whisper API."""
    logger.info("Transcribing: %s (%.1f MB)", file_path.name, file_path.stat().st_size / 1024 / 1024)

    with open(file_path, "rb") as audio_file:
        response = await client.audio.transcriptions.create(
            model=WHISPER_MODEL,
            file=audio_file,
            # No language hint — auto-detect (supports uz, ru, en, tr, etc.)
        )

    return response.text


async def normalize_dialect(text: str) -> str:
    """Normalize Uzbek dialect/slang to literary language using GPT.

    This step cleans up transcription artifacts, removes filler words,
    and converts regional dialect to standard Uzbek.
    """
    if len(text.strip()) < 20:
        # Too short to normalize — probably just a few words
        return text

    logger.info("Normalizing dialect for %d chars...", len(text))

    try:
        response = await client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": DIALECT_NORMALIZE_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.1,
            max_tokens=4000,
        )
        normalized = response.choices[0].message.content
        if normalized and len(normalized.strip()) > 10:
            return normalized.strip()
    except Exception as e:
        logger.warning("Dialect normalization failed, using raw text: %s", e)

    return text
