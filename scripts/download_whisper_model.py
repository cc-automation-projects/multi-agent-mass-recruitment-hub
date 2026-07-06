"""
Скрипт для загрузки модели whisper-large-v3-ru-phone (или базовой) в локальную папку.
"""

import sys
from pathlib import Path

from faster_whisper import WhisperModel

def download_model(model_path: str, model_size: str = "large-v3"):
    """Загружает модель faster-whisper указанного размера в указанную директорию."""
    print(f"Loading model {model_size}...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    print("Model loaded successfully. Cached in Hugging Face cache.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        model_path = sys.argv[1]
    else:
        model_path = "models/whisper-large-v3-ru-phone"
    download_model(model_path)
