"""Provider implementations for Gemini, Groq, and OpenRouter with unified interfaces."""

from abc import ABC, abstractmethod

from google import genai
from groq import Groq
from openai import OpenAI

from app.config import Settings


class BaseLLMProvider(ABC):
    """Abstract base provider for LLM calls."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if provider API keys and settings are configured."""

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the default model name for this provider."""

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.2,
        model_override: str | None = None,
    ) -> str:
        """Generate response text given prompt and system instructions."""


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider leveraging Gemini AI Studio / Pro capabilities."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_key = settings.GEMINI_API_KEY
        self.client: genai.Client | None = None
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)

    def is_configured(self) -> bool:
        return bool(self.api_key and self.client)

    def get_model_name(self) -> str:
        return self.settings.GEMINI_GENERATION_MODEL

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.2,
        model_override: str | None = None,
    ) -> str:
        if not self.client:
            raise RuntimeError("Gemini API key is not configured.")

        model = model_override or self.settings.GEMINI_GENERATION_MODEL
        config = {
            "temperature": temperature,
        }
        if system_instruction:
            config["system_instruction"] = system_instruction

        # In google-genai SDK:
        response = self.client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
        return response.text or ""


class GroqProvider(BaseLLMProvider):
    """Groq provider for ultra-fast, free-tier failover."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_key = settings.GROQ_API_KEY
        self.client: Groq | None = None
        if self.api_key:
            self.client = Groq(api_key=self.api_key)

    def is_configured(self) -> bool:
        return bool(self.api_key and self.client)

    def get_model_name(self) -> str:
        return self.settings.GROQ_MODEL

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.2,
        model_override: str | None = None,
    ) -> str:
        if not self.client:
            raise RuntimeError("Groq API key is not configured.")

        model = model_override or self.settings.GROQ_MODEL
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter provider for free-tier / wide catalog fallback."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_key = settings.OPENROUTER_API_KEY
        self.client: OpenAI | None = None
        if self.api_key:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key,
            )

    def is_configured(self) -> bool:
        return bool(self.api_key and self.client)

    def get_model_name(self) -> str:
        return self.settings.OPENROUTER_MODEL

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.2,
        model_override: str | None = None,
    ) -> str:
        if not self.client:
            raise RuntimeError("OpenRouter API key is not configured.")

        model = model_override or self.settings.OPENROUTER_MODEL
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""
