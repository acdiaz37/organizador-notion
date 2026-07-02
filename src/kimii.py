"""Extract structured payment data from images using Kimi API."""
import base64
import json
import logging
from pathlib import Path
from typing import Optional

from openai import OpenAI

from src.config import Config
from src.models import PaymentData

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """Analiza la captura de pantalla de un pago y devuelve **únicamente** un objeto JSON válido, sin texto extra, sin markdown, sin explicaciones.

{context_block}

Estructura exacta (valores desconocidos = null):
{{
  "nombre": "descripción corta",
  "monto": 45000,
  "fecha": "2026-07-01",
  "comercio": "comercio o destinatario",
  "categoria": "una de: Alimentación, Transporte, Servicios, Entretenimiento, Salud, Hogar, Otros",
  "referencia": "número de referencia",
  "estado": "Exitoso, Pendiente, Rechazado o Desconocido",
  "notas": "detalles breves"
}}

Reglas:
- "monto": número limpio, sin símbolos ni puntos de miles. Si ves $27.616,83 escribe 27616.83.
- "fecha": ISO 8601 (YYYY-MM-DD). Sin año visible: usa 2026.
- "estado": default "Exitoso" si es un comprobante.
- Sé breve en "nombre" y "notas"."""

CONTEXT_PREFIX = "El usuario envió este mensaje de contexto junto con la imagen. Úsalo para completar o corregir la información del pago:\n"""


class KimiExtractor:
    """Extract payment data from images using Kimi vision model."""

    def __init__(self) -> None:
        self.client = OpenAI(
            api_key=Config.KIMI_API_KEY,
            base_url=Config.KIMI_BASE_URL,
        )
        self.model = Config.KIMI_MODEL
        self.temperature = Config.KIMI_TEMPERATURE

    def _encode_image(self, image_path: Path) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _detect_mime_type(self, image_path: Path) -> str:
        suffix = image_path.suffix.lower()
        mapping = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        return mapping.get(suffix, "image/jpeg")

    def extract(self, image_path: Path, context: Optional[str] = None) -> PaymentData:
        """Extract payment data from an image file."""
        logger.info("Extracting data from image: %s", image_path)

        if context:
            context_block = CONTEXT_PREFIX + context
        else:
            context_block = "No hay contexto adicional. Extrae todo solo de la imagen."

        prompt = PROMPT_TEMPLATE.format(context_block=context_block)

        image_base64 = self._encode_image(image_path)
        mime_type = self._detect_mime_type(image_path)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}"
                            },
                        },
                    ],
                }
            ],
            temperature=self.temperature,
            max_completion_tokens=2048,
        )

        raw = response.choices[0].message.content or "{}"
        logger.info("Raw Kimi response (%d chars): %s", len(raw), raw[:500])

        # Sometimes Kimi wraps JSON in markdown code blocks; strip them.
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:])
            cleaned = cleaned.rstrip("`").strip()

        data = self._parse_json(cleaned)

        # Normalize keys: replace spaces or missing keys.
        data.setdefault("nombre", "Pago registrado")
        data.setdefault("monto", 0)

        return PaymentData.model_validate(data)

    def _parse_json(self, text: str) -> dict:
        """Parse JSON, trying a few recovery strategies if needed."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting the first {...} block.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass

        # Try to repair truncated JSON by closing strings and braces.
        repaired = self._repair_truncated_json(text[start : end + 1] if start != -1 and end != -1 else text)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse Kimi response as JSON: %s", text)
            raise ValueError(f"Kimi response is not valid JSON: {exc}") from exc

    @staticmethod
    def _repair_truncated_json(text: str) -> str:
        """Best-effort repair for JSON cut off mid-string."""
        text = text.strip()

        # Close unterminated strings.
        in_string = False
        escape = False
        for ch in text:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string

        if in_string:
            text += '"'

        # Close open braces/brackets.
        open_braces = text.count("{") - text.count("}")
        open_brackets = text.count("[") - text.count("]")
        text += "}" * max(open_braces, 0)
        text += "]" * max(open_brackets, 0)

        # Remove trailing comma before closing brace if present.
        if text.endswith(',}'):
            text = text[:-2] + '}'

        return text

    def test_connection(self) -> str:
        """Quickly test that the API key works."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": "Responde únicamente: OK"}],
            temperature=self.temperature,
            max_completion_tokens=10,
        )
        return response.choices[0].message.content or ""


def extract_payment(image_path: str | Path) -> PaymentData:
    """Convenience function to extract payment data from an image path."""
    extractor = KimiExtractor()
    return extractor.extract(Path(image_path))


def test_kimi_connection() -> str:
    """Convenience function to test Kimi connectivity."""
    return KimiExtractor().test_connection()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    Config.validate()
    print("Testing Kimi connection...")
    print(test_kimi_connection())
