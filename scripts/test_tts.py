"""
Тест синтеза речи (Silero TTS).
Сохраняет output.wav в текущую директорию.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.voice.tts import SileroTTS


async def main():
    tts = SileroTTS()
    text = "Привет, это тестовый синтез речи с использованием Silero TTS v5."
    audio_bytes = await tts.synthesize(text, sample_rate=16000)
    if audio_bytes:
        import wave
        with wave.open("output.wav", "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(audio_bytes)
        print("WAV file saved: output.wav")
    else:
        print("Failed to synthesize")

if __name__ == "__main__":
    asyncio.run(main())
