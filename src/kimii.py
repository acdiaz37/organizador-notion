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

BASE_PROMPT = """Eres un asistente especializado en extraer datos de comprobantes de pago de imágenes.

Tu tarea es analizar la imagen y devolver **únicamente** un objeto JSON válido. No escribas nada más: ni markdown, ni explicaciones, ni saludos.

Si la imagen NO es un comprobante de pago, una factura, una transacción bancaria o algo relacionado con un pago, devuelve exactamente:
{"es_pago": false, "nombre": "No es un pago", "monto": 0}

Si la imagen SÍ es un comprobante de pago, devuelve este JSON exacto (rellena lo que veas, usa null para lo desconocido):
{
  "es_pago": true,
  "nombre": "descripción corta del pago",
  "monto": 45000,
  "fecha": "2026-07-01",
  "comercio": "comercio o destinatario",
  "categoria": "una de: Alimentación, Transporte, Servicios, Entretenimiento, Salud, Hogar, Otros",
  "referencia": "número de referencia",
  "estado": "Exitoso, Pendiente, Rechazado o Desconocido",
  "notas": "detalles breves"
}

Reglas importantes:
- "monto" debe ser un número, sin símbolos de moneda ni puntos de miles. Ejemplo: si ves $27.616,83 escribe 27616.83.
- "fecha" debe estar en formato ISO 8601 (YYYY-MM-DD). Si no hay año visible, usa 2026.
- "estado": si no aparece, usa "Exitoso" si es un comprobante de pago.
- "categoria": elige la más cercana. Si no estás seguro, usa "Otros".
- Sé breve en "nombre" y "notas".
"""

CONTEXT_INSTRUCTION = """
El usuario envió este mensaje de contexto junto con la imagen. Úsalo para completar o corregir la información del pago, pero nunca inventes datos que no estén en la imagen o en el mensaje:
"""


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

    def _build_prompt(self, context: Optional[str]) -> str:
        prompt = BASE_PROMPT
        if context and context.strip():
            prompt += "\n" + CONTEXT_INSTRUCTION + context.strip()
        return prompt

    def extract(self, image_path: Path, context: Optional[str] = None) -> PaymentData:
        """Extract payment data from an image file."""
        logger.info("Extracting data from image: %s", image_path)

        prompt = self._build_prompt(context)
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

        # If Kimi returns an empty object, treat it as "not a payment".
        if not data:
            data = {"es_pago": False, "nombre": "No es un pago", "monto": 0}

        # Normalize defaults.
        data.setdefault("es_pago", True)
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


def extract_payment(image_path: str | Path, context: Optional[str] = None) -> PaymentData:
    """Convenience function to extract payment data from an image path."""
    extractor = KimiExtractor()
    return extractor.extract(Path(image_path), context=context)


def test_kimi_connection() -> str:
    """Convenience function to test Kimi connectivity."""
    return KimiExtractor().test_connection()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    Config.validate()
    print("Testing Kimi connection...")
    print(test_kimi_connection())
