"""Notion service: create databases and pages."""
import logging
from pathlib import Path
from typing import Optional

import httpx
from notion_client import Client

from src.config import Config
from src.models import PaymentData

logger = logging.getLogger(__name__)

DATABASE_TITLE = "Registro de Pagos"

# Use the 2022-06-28 API version because newer versions create databases as
# data sources without direct properties, breaking page creation.
NOTION_API_VERSION = "2022-06-28"

# Freeimage.host anonymous upload endpoint.
FREEIMAGE_UPLOAD_URL = "https://freeimage.host/json"


def upload_image_to_freeimage(image_path: Path) -> str:
    """Upload a local image to freeimage.host and return a public URL."""
    logger.info("Uploading image to freeimage.host: %s", image_path)
    with open(image_path, "rb") as f:
        files = {"source": f}
        data = {"type": "file", "action": "upload"}
        response = httpx.post(FREEIMAGE_UPLOAD_URL, data=data, files=files, timeout=60.0)
    response.raise_for_status()

    result = response.json()
    if result.get("status_code") != 200:
        raise ValueError(f"freeimage.host upload failed: {result}")

    image_url = result["image"]["url"]
    logger.info("Image uploaded to: %s", image_url)
    return image_url


class NotionService:
    """Wrapper around the Notion API."""

    def __init__(self) -> None:
        self.client = Client(
            auth=Config.NOTION_TOKEN,
            notion_version=NOTION_API_VERSION,
        )

    def create_database(self, parent_page_id: str) -> str:
        """Create the payments database under the given parent page."""
        logger.info("Creating database under page %s", parent_page_id)

        properties = {
            "Nombre": {"title": {}},
            "Monto": {"number": {"format": "colombian_peso"}},
            "Fecha del pago": {"date": {}},
            "Comercio / Destinatario": {"select": {"options": []}},
            "Categoría": {
                "select": {
                    "options": [
                        {"name": "Alimentación", "color": "green"},
                        {"name": "Transporte", "color": "blue"},
                        {"name": "Servicios", "color": "yellow"},
                        {"name": "Entretenimiento", "color": "purple"},
                        {"name": "Salud", "color": "red"},
                        {"name": "Hogar", "color": "brown"},
                        {"name": "Otros", "color": "gray"},
                    ]
                }
            },
            "Número de referencia": {"rich_text": {}},
            "Estado": {
                "select": {
                    "options": [
                        {"name": "Exitoso", "color": "green"},
                        {"name": "Pendiente", "color": "yellow"},
                        {"name": "Rechazado", "color": "red"},
                        {"name": "Desconocido", "color": "gray"},
                    ]
                }
            },
            "Imagen": {"files": {}},
            "Notas": {"rich_text": {}},
            "Fecha de registro": {"created_time": {}},
        }

        response = httpx.post(
            "https://api.notion.com/v1/databases",
            headers={
                "Authorization": f"Bearer {Config.NOTION_TOKEN}",
                "Notion-Version": NOTION_API_VERSION,
                "Content-Type": "application/json",
            },
            json={
                "parent": {"type": "page_id", "page_id": parent_page_id},
                "title": [{"type": "text", "text": {"content": DATABASE_TITLE}}],
                "properties": properties,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        db = response.json()
        database_id = db["id"]
        logger.info("Database created with ID: %s", database_id)
        return database_id

    def create_payment_page(
        self,
        database_id: str,
        payment: PaymentData,
        image_url: Optional[str],
    ) -> str:
        """Create a page in the database with the payment data."""
        logger.info("Creating payment page in database %s", database_id)

        properties: dict = {
            "Nombre": {"title": [{"text": {"content": payment.nombre}}]},
            "Monto": {"number": payment.monto},
        }

        if payment.fecha:
            properties["Fecha del pago"] = {"date": {"start": payment.fecha.isoformat()}}
        if payment.comercio:
            properties["Comercio / Destinatario"] = {"select": {"name": payment.comercio}}
        if payment.categoria:
            properties["Categoría"] = {"select": {"name": payment.categoria}}
        if payment.referencia:
            properties["Número de referencia"] = {"rich_text": [{"text": {"content": payment.referencia}}]}
        if payment.estado:
            properties["Estado"] = {"select": {"name": payment.estado}}
        if payment.notas:
            properties["Notas"] = {"rich_text": [{"text": {"content": payment.notas}}]}

        if image_url:
            properties["Imagen"] = {
                "files": [
                    {
                        "type": "external",
                        "name": Path(image_url).name or "captura.png",
                        "external": {"url": image_url},
                    }
                ]
            }

        page = self.client.pages.create(
            parent={"database_id": database_id},
            properties=properties,
        )
        page_id = page["id"]
        logger.info("Payment page created: %s", page_id)
        return page_id

    def search_database(self, query: str = "Registro de Pagos") -> Optional[str]:
        """Search for an existing database by title and return its ID."""
        results = self.client.search(query=query).get("results", [])
        for result in results:
            if result["object"] == "database":
                title_parts = result.get("title", [])
                title = "".join(t.get("plain_text", "") for t in title_parts)
                if query.lower() in title.lower():
                    db_id = result["id"]
                    # New API versions can create databases as data sources
                    # without direct properties; skip those.
                    db_details = self.client.databases.retrieve(database_id=db_id)
                    if "Nombre" in db_details.get("properties", {}):
                        logger.info("Found existing database: %s", db_id)
                        return db_id
        return None


def save_payment(
    payment: PaymentData,
    image_path: Path,
    database_id: Optional[str] = None,
) -> tuple[str, str]:
    """Upload image and create a Notion page. Returns (page_id, page_url)."""
    service = NotionService()

    if database_id is None:
        database_id = Config.NOTION_DATABASE_ID or service.search_database()

    if not database_id:
        raise ValueError("No Notion database ID configured or found.")

    image_url = upload_image_to_freeimage(image_path)
    page_id = service.create_payment_page(database_id, payment, image_url)
    page_url = f"https://notion.so/{page_id.replace('-', '')}"
    return page_id, page_url


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    Config.validate()
    svc = NotionService()
    db_id = svc.search_database()
    print("Database ID:", db_id)
