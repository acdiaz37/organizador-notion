"""Script to create the Notion database for payments.

Usage:
    .venv/bin/python scripts/create_notion_database.py <parent_page_id>

The parent_page_id is the ID of an existing Notion page where the database
will live. You can get it from the Notion URL:
    https://www.notion.so/Workspace-Name-1234567890abcdef1234567890abcdef
                                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import Config
from src.notion_service import NotionService

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    Config.validate()

    parser = argparse.ArgumentParser(description="Create the payments database in Notion.")
    parser.add_argument("parent_page_id", help="Notion parent page ID")
    args = parser.parse_args()

    service = NotionService()
    existing = service.search_database()
    if existing:
        print(f"Database already exists: {existing}")
        print("Add this to your .env as NOTION_DATABASE_ID")
        return

    database_id = service.create_database(args.parent_page_id)
    print(f"Database created: {database_id}")
    print("Add this to your .env as NOTION_DATABASE_ID")


if __name__ == "__main__":
    main()
