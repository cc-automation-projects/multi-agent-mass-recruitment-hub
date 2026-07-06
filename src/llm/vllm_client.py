"""
vLLM клиент для высокопроизводительного инференса LLM.
"""

from collections.abc import AsyncGenerator

from src.core.audit_logger import audit_log
from src.core.config import get_settings

_logger = audit_log()
_settings = get_settings()


class VLLMClient:
    """
    Клиент для vLLM (OpenAI-совместимый API).
    Если vLLM не установлен или нет GPU, возвращает заглушку.
    """

    def __init__(self, model_name: str | None = None, base_url: str | None = None):
        self.model_name = model_name or _settings.vllm_model
        self.base_url = base_url or _settings.vllm_base_url
        self._client = None

    async def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(
                    base_url=self.base_url,
                    api_key="EMPTY",
                )
                _logger.info(
                    "vLLM client initialized", base_url=self.base_url, model=self.model_name
                )
            except ImportError:
                _logger.warning("openai package not installed, vLLM client will be stub")
                self._client = None
        return self._client

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        """
        Генерирует ответ на промпт через vLLM.
        """
        client = await self._get_client()
        if client is None:
            _logger.warning("vLLM client unavailable, returning dummy response")
            return f"Заглушка LLM для промпта: {prompt[:50]}..."

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            _logger.error("vLLM generation failed", error=str(e))
            return ""

    async def stream_generate(
        self, prompt: str, system_prompt: str | None = None
    ) -> AsyncGenerator[str, None]:
        """
        Потоковая генерация (для future use).
        """
        client = await self._get_client()
        if client is None:
            yield "Заглушка: нет vLLM"
            return

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async for chunk in await client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            stream=True,
        ):
            content = chunk.choices[0].delta.content
            if content:
                yield content
