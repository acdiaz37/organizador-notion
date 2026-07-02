"""Configuration loaded from environment variables."""
import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ALLOWED_CHAT_ID: int = int(os.getenv("TELEGRAM_ALLOWED_CHAT_ID", "0"))

    # Kimi / Moonshot
    KIMI_API_KEY: str = os.getenv("KIMI_API_KEY", "")
    KIMI_BASE_URL: str = os.getenv("KIMI_BASE_URL", "https://api.kimi.com/coding/v1")
    KIMI_MODEL: str = os.getenv("KIMI_MODEL", "kimi-for-coding")
    KIMI_TEMPERATURE: float = float(os.getenv("KIMI_TEMPERATURE", "1.0"))

    # Notion
    NOTION_TOKEN: str = os.getenv("NOTION_TOKEN", "")
    NOTION_DATABASE_ID: str = os.getenv("NOTION_DATABASE_ID", "")
    NOTION_PARENT_PAGE_ID: str = os.getenv("NOTION_PARENT_PAGE_ID", "")

    @classmethod
    def validate(cls) -> None:
        """Raise if required config is missing."""
        missing = []
        if not cls.TELEGRAM_BOT_TOKEN:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not cls.KIMI_API_KEY:
            missing.append("KIMI_API_KEY")
        if not cls.NOTION_TOKEN:
            missing.append("NOTION_TOKEN")
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
