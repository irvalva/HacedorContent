import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Configurar logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Obtén el token del bot desde la variable de entorno
TOKEN = "7650649334:AAHXfWmyRyjAnTT7O-Bkc9Fr9FPUMvxBHBc"

def utf16_offset_to_index(text: str, utf16_offset: int) -> int:
    """
    Convierte un offset (en UTF-16 code units) a un índice correcto en la cadena de Python.
    Esto es necesario porque Telegram reporta los offsets de las entidades en UTF-16.
    """
    count = 0
    for i, ch in enumerate(text):
        # Si el carácter está fuera del BMP se cuenta como 2 code units
        if ord(ch) >= 0x10000:
            count += 2
        else:
            count += 1
        if count >= utf16_offset:
            return i + 1
    return len(text)

def convert_entities_to_html(message: Update.message) -> str:
    """
    Reconstruye el texto formateado en HTML a partir de las entidades que envía Telegram.
    Por ejemplo, si el usuario envía "Hola" con "como están" en negrita,
    se devolverá: "Hola <b>como están</b>".
    Se ordenan las entidades en orden inverso (según el índice convertido) para
    insertar las etiquetas sin afectar los offsets de las que aún no se procesan.
    """
    if not message.entities:
        return message.text

    text = message.text
    # Ordenar las entidades de menor a mayor offset (convertido a índice en Python),
    # pero luego iterar en orden inverso para no alterar los índices.
    entities = sorted(
        message.entities, key=lambda ent: utf16_offset_to_index(text, ent.offset)
    )
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
        # Reemplazar la parte correspondiente del texto con la versión formateada
        text = text[:start] + formatted + text[end:]
    return text

async def prettyhtml(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando que responde con la conversión a HTML del mensaje recibido.
    Por ejemplo, si envías un mensaje con formato (usando las opciones nativas de Telegram)
    y luego escribes /prettyhtml, el bot te devuelve el mismo contenido convertido a HTML.
    """
    # Convertir el mensaje recibido a HTML usando los datos de formateo (entities)
    html_text = convert_entities_to_html(update.message)
    await update.message.reply_text(html_text, parse_mode="HTML")

def main():
    # Crear la aplicación y registrar el manejador del comando /prettyhtml
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("prettyhtml", prettyhtml))
    logger.info("Bot PrettyHTML replicado en marcha...")
    app.run_polling()

if __name__ == '__main__':
    main()
