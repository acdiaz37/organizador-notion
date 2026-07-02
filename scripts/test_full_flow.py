"""End-to-end test: create a fake payment screenshot, extract data with Kimi,
and save it to Notion.

Usage:
    .venv/bin/python scripts/test_full_flow.py
"""
import logging
import os
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import Config
from src.kimii import KimiExtractor
from src.notion_service import save_payment

logger = logging.getLogger(__name__)


def create_test_image(path: Path) -> None:
    """Generate a fake payment receipt image."""
    width, height = 600, 700
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        font_body = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except OSError:
        font_title = ImageFont.load_default()
        font_body = font_title

    y = 40
    line_height = 35

    lines = [
        ("Comprobante de Pago", font_title),
        ("", font_body),
        ("Fecha: 2026-07-01", font_body),
        ("Comercio: Éxito Calle 100", font_body),
        ("Monto: $45.000 COP", font_body),
        ("Referencia: 1234567890", font_body),
        ("Estado: Exitoso", font_body),
        ("Metodo: Tarjeta debito", font_body),
        ("Categoria: Alimentacion", font_body),
        ("", font_body),
        ("Gracias por su compra", font_body),
    ]

    for text, font in lines:
        draw.text((40, y), text, fill="black", font=font)
        y += line_height + 10

    img.save(path)
    logger.info("Test image saved to %s", path)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    Config.validate()

    fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix="test_pago_")
    os.close(fd)
    image_path = Path(tmp_path)

    try:
        create_test_image(image_path)

        logger.info("Extracting payment data with Kimi...")
        extractor = KimiExtractor()
        payment = extractor.extract(image_path)
        logger.info("Extracted: %s", payment.model_dump_json(indent=2))

        logger.info("Saving to Notion...")
        page_id, page_url = save_payment(payment, image_path)
        logger.info("Page created: %s", page_url)

        print(f"\n✅ Flujo completo funcionó")
        print(f"Página: {page_url}")
    finally:
        image_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
