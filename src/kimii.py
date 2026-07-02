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

PROMPT_TEMPLATE = """Analiza la siguiente captura de pantalla de un pago y extrae la información en formato JSON.

{context_block}

Devuelve **únicamente** un objeto JSON válido, sin texto adicional, sin markdown, sin explicaciones.

El JSON debe tener esta estructura exacta:
{{
  "nombre": "descripción corta del pago",
  "monto": 45000,
  "fecha": "2026-07-01",
  "comercio": "nombre del comercio o destinatario",
  "categoria": "una de: Alimentación, Transporte, Servicios, Entretenimiento, Salud, Hogar, Otros",
  "referencia": "número de referencia o transacción si aparece",
  "estado": "una de: Exitoso, Pendiente, Rechazado, Desconocido",
  "notas": "cualquier información adicional relevante"
}}

Reglas:
- "monto" debe ser un número, sin símbolos de moneda ni puntos de miles. Ej: 45000, 1250000.5
- "fecha" debe estar en formato ISO 8601 (YYYY-MM-DD). Si no hay año visible, asume el año actual.
- Si algún dato no aparece en la imagen, usa null para campos opcionales.
- Para "categoria", elige la opción más cercana. Si no estás seguro, usa "Otros".
- Para "estado", si no aparece información de estado, usa "Exitoso" si parece un comprobante de pago, o "Desconocido" si no puedes determinarlo.
- En "notas" puedes incluir texto extraído o detalles como "tarjeta terminada en 1234", "propina incluida", etc.
"""

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
            max_completion_tokens=1024,
        )

        raw = response.choices[0].message.content or "{}"
        logger.debug("Raw Kimi response: %s", raw)

        # Sometimes Kimi wraps JSON in markdown code blocks; strip them.
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:])
            cleaned = cleaned.rstrip("`").strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse Kimi response as JSON: %s", raw)
            raise ValueError(f"Kimi response is not valid JSON: {exc}") from exc

        # Normalize keys: replace spaces or missing keys.
        data.setdefault("nombre", "Pago registrado")
        data.setdefault("monto", 0)

        return PaymentData.model_validate(data)

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
