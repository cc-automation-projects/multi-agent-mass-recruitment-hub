"""
Конвертация аудио из различных форматов в PCM 16kHz mono.
Требует установленного ffmpeg.
"""

import io
import tempfile

from pydub import AudioSegment


async def convert_to_pcm(audio_bytes: bytes, input_format: str = "ogg") -> bytes | None:
    """
    Конвертирует аудио в PCM (16kHz, mono, 16-bit).
    Поддерживаемые форматы: ogg, mp3, m4a, webm и др. (через ffmpeg).
    """
    try:
        with tempfile.NamedTemporaryFile(suffix=f".{input_format}", delete=False) as tmp_in:
            tmp_in.write(audio_bytes)
            tmp_in_path = tmp_in.name

        audio = AudioSegment.from_file(tmp_in_path, format=input_format)
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        pcm_bytes = io.BytesIO()
        audio.export(pcm_bytes, format="raw")
        pcm_bytes.seek(0)
        return pcm_bytes.read()
    except Exception:
        return None
    finally:
        import os

        if "tmp_in_path" in locals():
            os.unlink(tmp_in_path)
