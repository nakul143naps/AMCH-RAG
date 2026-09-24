"""Vision captioning pass for charts and images using Gemini Multimodal."""

import asyncio
import io
import logging

from PIL import Image

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

VISION_PROMPT = """You are an expert technical visual analyst for an enterprise RAG knowledge base.
Analyze the provided image, chart, or diagram thoroughly:
1. Figure Type & Title (e.g., Bar chart, Line graph, Scatter plot, Architecture schematic, Workflow diagram)
2. Exact Data Points & Metrics: Extract specific numbers, percentages, dates, axis categories, and table values.
3. Trends & Key Insights: Describe trends, comparisons, peaks, dips, growth rates, and structural conclusions.
4. Comprehensive Searchable Caption: A concise yet dense factual summary enabling semantic search and keyword queries to find this figure.

Context surrounding this figure in the document:
{context_hint}

Respond with a structured, factual breakdown:
[Figure: <Title/Type>]
Metrics: <Extracted data points>
Trends: <Key insights and trends>
Summary: <Searchable caption>"""


class VisionCaptioner:
    """Extracts structured text descriptions, data points, and trends from images and charts."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def caption_image_sync(
        self, image_bytes: bytes, mime_type: str = "image/png", context_hint: str = ""
    ) -> str:
        """Call Gemini multimodal to caption an image synchronously."""
        return self._sync_caption_image(image_bytes, mime_type, context_hint)

    def _sync_caption_image(
        self, image_bytes: bytes, mime_type: str = "image/png", context_hint: str = ""
    ) -> str:
        """Call Gemini multimodal to caption an image synchronously."""
        # 1. Inspect image using PIL to ensure valid format and dimensions
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                width, height = img.size
                img_format = img.format or "PNG"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to read image bytes with PIL: {e}")
            width, height, img_format = 0, 0, "UNKNOWN"

        # 2. Attempt Gemini Multimodal Vision API if API key is present
        api_key = self.settings.GEMINI_API_KEY
        if api_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=api_key)
                prompt = VISION_PROMPT.format(context_hint=context_hint or "None provided")
                image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

                response = client.models.generate_content(
                    model=self.settings.GEMINI_GENERATION_MODEL,
                    contents=[prompt, image_part],
                )
                if response.text and response.text.strip():
                    logger.info("VisionCaptioner generated caption via Gemini Multimodal")
                    return response.text.strip()
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Gemini multimodal vision call failed: {e}. Falling back to metadata.")

        # 3. Fallback caption when offline or during test mock
        hint_str = f" Context: {context_hint}" if context_hint else ""
        return (
            f"[Chart / Figure]\n"
            f"Format: {img_format}, Dimensions: {width}x{height}px.{hint_str}\n"
            "Summary: Visual figure extracted from document."
        )

    async def async_caption_image(
        self, image_bytes: bytes, mime_type: str = "image/png", context_hint: str = ""
    ) -> str:
        """Asynchronously generate a structured caption offloaded to a worker thread."""
        if not image_bytes:
            return ""
        return await asyncio.to_thread(
            self._sync_caption_image, image_bytes, mime_type, context_hint
        )
