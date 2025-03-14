import os
import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Configuración de logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Obtén el token del bot desde la variable de entorno
TOKEN = "7650649334:AAHXfWmyRyjAnTT7O-Bkc9Fr9FPUMvxBHBc"
if not TOKEN:
    logger.error("No se encontró TELEGRAM_BOT_TOKEN. Asegúrate de definirla correctamente.")
    exit(1)

def utf16_offset_to_index(text: str, utf16_offset: int) -> int:
    """
    Convierte un offset (en UTF-16 code units) al índice correcto en la cadena de Python.
    Telegram reporta los offsets basados en UTF-16, lo que puede provocar discrepancias.
    """
    count = 0
    for i, ch in enumerate(text):
        # Caracteres fuera del BMP se cuentan como 2 code units
        if ord(ch) >= 0x10000:
            count += 2
        else:
            count += 1
        if count >= utf16_offset:
            return i + 1
    return len(text)

def convert_entities_to_html(message) -> str:
    """
    Reconstruye el texto formateado en HTML a partir de las entidades que envía Telegram.
    Por ejemplo, si el mensaje es:
        Hola, ¿<b>cómo estás?</b>
    y se aplicó formato nativo (bold) sobre la frase "cómo estás", se reconstruirá:
        Hola, <b>cómo estás</b>
    Se ordenan las entidades (con offsets convertidos) en orden inverso para que al insertar
    las etiquetas no se alteren los offsets de las que aún no se han procesado.
    """
    if not message.entities:
        return message.text

    text = message.text
    # Ordenamos las entidades por su offset convertido (de menor a mayor)
    entities = sorted(message.entities, key=lambda ent: utf16_offset_to_index(text, ent.offset))
    # Iteramos en orden inverso para no afectar los offsets pendientes
    for ent in reversed(entities):
        start = utf16_offset_to_index(text, ent.offset)
        end = utf16_offset_to_index(text, ent.offset + ent.length)
        substring = text[start:end]
        if ent.type == "bold":
            formatted = f"<b>{substring}</b>"
        elif ent.type == "italic":
            formatted = f"<i>{substring}</i>"
        elif ent.type == "underline":
            formatted = f"<u>{substring}</u>"
        elif ent.type == "strikethrough":
            formatted = f"<s>{substring}</s>"
        elif ent.type == "code":
            formatted = f"<code>{substring}</code>"
        elif ent.type == "pre":
            formatted = f"<pre>{substring}</pre>"
        elif ent.type == "text_link":
            formatted = f'<a href="{ent.url}">{substring}</a>'
        else:
            formatted = substring
        text = text[:start] + formatted + text[end:]
    return text

async def auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Si se recibe un mensaje de texto (que no sea un comando) y proviene de un usuario,
    se convierte el contenido a HTML y se responde con el resultado.
    """
    # Evitar responder a otros bots (incluido el propio)
    if update.message.from_user.is_bot:
        return
    if not update.message.text:
        return

    html_text = convert_entities_to_html(update.message)
    await update.message.reply_text(html_text, parse_mode="HTML")

def main():
    app = Application.builder().token(TOKEN).build()
    # Se configura el handler para mensajes de texto (excluyendo comandos)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_reply))
    logger.info("PrettyHTML Bot: Responderá automáticamente con el texto convertido a HTML.")
    app.run_polling()

if __name__ == '__main__':
    main()
