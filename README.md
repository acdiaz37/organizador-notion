# Organizador Notion

Bot de Telegram personal que recibe capturas de pantalla de pagos, extrae la información usando la API de Kimi y la guarda en una base de datos de Notion con la imagen adjunta.

## Características

- Solo responde a tu `chat_id` de Telegram.
- Soporta imágenes enviadas como foto o documento.
- Extrae automáticamente: monto, fecha, comercio, categoría, referencia, estado y notas.
- Guarda la imagen como archivo adjunto en la página de Notion.

## Requisitos

- Python 3.12+
- Token de bot de Telegram (@BotFather)
- API key de Kimi (kimi.com/code/console o platform.kimi.com)
- Token de integración interna de Notion

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuración

Copia o edita `.env`:

```env
TELEGRAM_BOT_TOKEN=tu-token-de-telegram
TELEGRAM_ALLOWED_CHAT_ID=tu-chat-id

KIMI_API_KEY=sk-...
KIMI_BASE_URL=https://api.kimi.com/coding/v1
KIMI_MODEL=kimi-for-coding
KIMI_TEMPERATURE=1.0

NOTION_TOKEN=ntn_...
NOTION_DATABASE_ID=
NOTION_PARENT_PAGE_ID=
```

### Crear la base de datos en Notion

1. Crea una página en Notion donde vivirá la base de datos.
2. Copia el ID de la página desde la URL.
3. Ejecuta:

```bash
source .venv/bin/activate
python scripts/create_notion_database.py <PARENT_PAGE_ID>
```

4. Guarda el `database_id` impreso en tu `.env` como `NOTION_DATABASE_ID`.

## Uso

Envía una captura de pantalla de un pago al bot. Puedes agregar un **mensaje de contexto** junto con la imagen (caption) para ayudar a Kimi, por ejemplo:

> *imagen*  
> pago crédito banco occidente

El bot usará ese texto para completar o corregir datos como el comercio, banco, categoría, etc.

El bot responderá con un resumen de cómo quedó categorizado el pago y el link a la página de Notion.

## Ejecutar el bot

```bash
source .venv/bin/activate
python -m src.telegram_bot
```

Presiona `/start` para ver el botón de estado del bot.

## Estructura del proyecto

```
organizador_notion/
├── .env
├── requirements.txt
├── scripts/
│   └── create_notion_database.py
└── src/
    ├── config.py
    ├── kimii.py
    ├── models.py
    ├── notion_service.py
    └── telegram_bot.py
```
