"""Telegram bot that receives payment screenshots and saves them to Notion."""
import logging
import tempfile
from pathlib import Path
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.config import Config
from src.kimii import KimiExtractor
from src.models import PaymentData
from src.notion_service import save_payment

logger = logging.getLogger(__name__)

WELCOME_MESSAGE = """👋 Hola. Soy tu bot de registro de pagos.

Envíame una captura de pantalla de un pago y yo:
1. Extraeré los datos con Kimi
2. Crearé una entrada en tu base de Notion
3. Adjuntaré la imagen

Solo respondo a ti."""

UNAUTHORIZED_MESSAGE = "⛔ No estás autorizado para usar este bot."
PROCESSING_MESSAGE = "⏳ Procesando captura..."


def is_authorized(update: Update) -> bool:
    """Check if the incoming message is from the allowed user."""
    chat_id = update.effective_chat.id if update.effective_chat else None
    return chat_id == Config.TELEGRAM_ALLOWED_CHAT_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await update.message.reply_text(UNAUTHORIZED_MESSAGE)
        return

    keyboard = [
        [InlineKeyboardButton("📊 Estado del bot", callback_data="status")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=reply_markup)


async def status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'Status' inline button press."""
    query = update.callback_query
    await query.answer()

    if not is_authorized(update):
        await query.edit_message_text(UNAUTHORIZED_MESSAGE)
        return

    status_text = (
        "📊 Estado del bot\n\n"
        "✅ Bot activo y escuchando\n"
        "✅ Conexión con Kimi configurada\n"
        "✅ Conexión con Notion configurada\n"
        "🆔 Chat autorizado\n\n"
        "Envíame una captura de pantalla de un pago para registrarlo."
    )
    await query.edit_message_text(status_text)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await update.message.reply_text(UNAUTHORIZED_MESSAGE)
        return

    status_message = await update.message.reply_text(PROCESSING_MESSAGE)
    caption = update.message.caption or update.message.text or None

    try:
        # Get largest available photo.
        photo = update.message.photo[-1]
        file = await photo.get_file()
        local_path = await _download_file(file)

        await _process_image(update, status_message, local_path, caption)
    except Exception as exc:
        logger.exception("Error processing photo")
        await status_message.edit_text(f"❌ Error procesando la imagen: {exc}")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await update.message.reply_text(UNAUTHORIZED_MESSAGE)
        return

    document = update.message.document
    if not document or not document.mime_type or not document.mime_type.startswith("image/"):
        await update.message.reply_text("⚠️ Envía una imagen, por favor.")
        return

    status_message = await update.message.reply_text(PROCESSING_MESSAGE)
    caption = update.message.caption or None

    try:
        file = await document.get_file()
        local_path = await _download_file(file)

        await _process_image(update, status_message, local_path, caption)
    except Exception as exc:
        logger.exception("Error processing document")
        await status_message.edit_text(f"❌ Error procesando el documento: {exc}")


async def _download_file(file) -> Path:
    """Download a Telegram file to a temporary path."""
    suffix = ".jpg"
    if file.file_path:
        suffix = Path(file.file_path).suffix or ".jpg"

    fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix="pago_")
    await file.download_to_drive(tmp_path)
    return Path(tmp_path)


async def _process_image(
    update: Update,
    status_message,
    image_path: Path,
    caption: Optional[str] = None,
) -> None:
    """Run Kimi extraction + Notion save, then reply to the user."""
    extractor = KimiExtractor()
    payment = extractor.extract(image_path, context=caption)

    context_hint = f"📝 Contexto usado: {caption}\n" if caption else ""

    await status_message.edit_text(
        f"✅ Datos extraídos:\n"
        f"• {payment.nombre}\n"
        f"• Monto: ${payment.monto:,.0f}\n"
        f"• Comercio: {payment.comercio or 'N/A'}\n"
        f"• Categoría: {payment.categoria or 'N/A'}\n"
        f"{context_hint}\n"
        f"Guardando en Notion..."
    )

    page_id, page_url = save_payment(payment, image_path)

    final_message = (
        f"✅ Pago guardado en Notion\n\n"
        f"📄 {payment.nombre}\n"
        f"💰 Monto: ${payment.monto:,.0f}\n"
        f"📅 Fecha del pago: {payment.fecha.isoformat() if payment.fecha else 'N/A'}\n"
        f"🏪 Comercio: {payment.comercio or 'N/A'}\n"
        f"🏷️ Categoría: {payment.categoria or 'N/A'}\n"
        f"📌 Estado: {payment.estado or 'N/A'}\n"
        f"🔖 Referencia: {payment.referencia or 'N/A'}\n"
    )
    if payment.notas:
        final_message += f"📝 Notas: {payment.notas}\n"
    final_message += f"\n🔗 {page_url}"

    await status_message.edit_text(final_message)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    Config.validate()

    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(status_callback, pattern="^status$"))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))

    logger.info("Bot started. Waiting for screenshots...")
    application.run_polling()


if __name__ == "__main__":
    main()
