import json
import openai
import os
import random
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
import logging

# Configuración de logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    logger.error("Falta TELEGRAM_BOT_TOKEN u OPENAI_API_KEY")
    exit(1)
openai.api_key = OPENAI_API_KEY

CONFIG_FILE = "config.json"

# Funciones para cargar y guardar la configuración en JSON
def cargar_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {
            "configuracion": {
                "nombre": "",
                "etiqueta": "",
                "personalidad": "",
                "servicios": [],
                "idioma": ""
            },
            "tipos_de_post": {}
        }

def guardar_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=4, ensure_ascii=False)

config = cargar_config()

# --- Conversión de formato a HTML ---
def utf16_offset_to_index(text: str, utf16_offset: int) -> int:
    """
    Convierte un offset (en UTF-16 code units) al índice correcto en la cadena de Python.
    Telegram reporta los offsets basados en UTF-16.
    """
    count = 0
    for i, ch in enumerate(text):
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
    Se ordenan las entidades (usando offsets convertidos) en orden inverso para no afectar los índices.
    """
    if not message.entities:
        return message.text

    text = message.text
    # Ordenamos de menor a mayor (según índice convertido)
    entities = sorted(message.entities, key=lambda ent: utf16_offset_to_index(text, ent.offset))
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

def process_example_text(text: str) -> str:
    """
    Si el texto no tiene entidades, se asume que ya tiene el formato deseado (HTML) o se guarda tal cual.
    """
    return text

# --- Flujo de configuración inicial ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not config["configuracion"]["nombre"]:
        await update.message.reply_text(
            "¡Hola! Vamos a configurar tu bot.\nPrimero, ¿cómo se llama tu personaje?",
            parse_mode="HTML"
        )
        context.user_data["esperando_nombre"] = True
    else:
        await update.message.reply_text("La configuración ya existe. Usa /menu para ver las opciones.", parse_mode="HTML")

# --- Generación de Post con ChatGPT ---
async def generate_post(tipo_post: str, tema: str, idioma: str, previous_index: int = None):
    ejemplos = config["tipos_de_post"][tipo_post]["ejemplos"]
    if not ejemplos:
        return None, None

    indices_disponibles = list(range(len(ejemplos)))
    if previous_index is not None and len(ejemplos) > 1:
        indices_disponibles = [i for i in indices_disponibles if i != previous_index]
    elegido = random.choice(indices_disponibles)
    ejemplo_text = ejemplos[elegido]

    prompt = (
    f"Genera un post para Telegram en {config['configuracion']['idioma']} utilizando HTML para el formato "
    f"(por ejemplo, <b> para negrita, <i> para cursiva, <u> para subrayado, etc.).\n"
    f"El post debe inspirarse en el siguiente ejemplo para mantener un estilo y extensión similares, "
    f"pero el contenido final debe ser 100% original y adaptado a la idea principal que se proporciona a continuación.\n\n"
    f"Idea principal (interpreta y corrige posibles errores ortográficos o de redacción):\n\"{tema}\"\n\n"
    f"Ejemplo (solo para inspirarte en el formato y la extensión):\n{ejemplo_text}\n\n"
    f"Utiliza internamente los siguientes datos para adaptar el tono y estilo, pero no los muestres directamente en el resultado final:\n"
    f"- Personalidad del personaje: {config['configuracion']['personalidad']}\n"
    f"- Servicios o productos que ofrece: {', '.join(config['configuracion']['servicios'])}\n\n"
    f"En el post, incorpora de forma natural la etiqueta \"{config['configuracion']['etiqueta']}\" en el llamado a la acción (CTA), "
    f"asegurándote de que el CTA sea breve.\n\n"
    f"⚠️ **Importante:** Redacta únicamente el contenido final del post para Telegram, sin encabezados ni detalles internos "
    f"(no incluyas palabras como 'Idea principal:', 'Ejemplo:', 'Personalidad:' o 'Servicios:'). No uses hashtags ni puntos finales innecesarios. "
    f"El post debe basarse en la idea proporcionada, interpretándola de forma coherente (por ejemplo, si la idea es 'Hoy ganaremos', "
    f"el texto debe transmitir que 'hoy se ganará')."
    )
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"Habla como {config['configuracion']['nombre']}. No incluyas datos internos; responde solo con el contenido final del post."},
                {"role": "user", "content": prompt}
            ]
        )
        post_text = response["choices"][0]["message"]["content"].strip()
        return post_text, elegido
    except Exception as e:
        return f"Ocurrió un error al generar el post: {e}", elegido

async def presentar_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_text: str):
    keyboard = [
        [
            InlineKeyboardButton("✅ Aceptar", callback_data="aceptar_post"),
            InlineKeyboardButton("♻️ Reescribir", callback_data="reescribir_post")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_message.reply_text(post_text, reply_markup=reply_markup, parse_mode="HTML")

# --- Manejo de mensajes según el estado ---
async def recibir_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # Si se espera el tema para generar el post, tiene prioridad
    if context.user_data.get("esperando_post_tema"):
        tipo_post = context.user_data.get("tipo_post")
        tema = text
        idioma = config["configuracion"].get("idioma", "Español")
        context.user_data.pop("esperando_post_tema")
        context.user_data.pop("esperando_ejemplo", None)

        post_text, indice_ejemplo = await generate_post(tipo_post, tema, idioma)
        if post_text is None:
            await update.message.reply_text("No hay ejemplos en esta categoría. Agrega algunos antes de generar un post.", parse_mode="HTML")
            return
        context.user_data["ultimo_tipo_post"] = tipo_post
        context.user_data["ultimo_tema"] = tema
        context.user_data["ultimo_ejemplo_index"] = indice_ejemplo
        context.user_data["ultimo_post"] = post_text
        await presentar_post(update, context, post_text)
        return

    # Si se espera un ejemplo para agregar
    if context.user_data.get("esperando_ejemplo"):
        tipo_post = context.user_data.get("tipo_post")
        if not tipo_post:
            await update.message.reply_text("Error: No se ha seleccionado un tipo de post.", parse_mode="HTML")
            context.user_data.pop("esperando_ejemplo", None)
            return
        if update.message.entities:
            processed_text = convert_entities_to_html(update.message)
        else:
            processed_text = process_example_text(text)
        if processed_text in config["tipos_de_post"][tipo_post]["ejemplos"]:
            await update.message.reply_text("Este ejemplo ya existe. No se ha agregado duplicado.", parse_mode="HTML")
            context.user_data.pop("esperando_ejemplo", None)
            return
        config["tipos_de_post"][tipo_post]["ejemplos"].append(processed_text)
        guardar_config(config)
        await update.message.reply_text(f"Ejemplo agregado al tipo de post '{tipo_post}'.", parse_mode="HTML")
        context.user_data.pop("esperando_ejemplo", None)
        return

    # Flujo de configuración del personaje
    if context.user_data.get("esperando_nombre"):
        config["configuracion"]["nombre"] = text
        guardar_config(config)
        context.user_data.pop("esperando_nombre")
        await update.message.reply_text("Perfecto. Ahora ingresa la etiqueta (ejemplo: @ejemplo):", parse_mode="HTML")
        context.user_data["esperando_etiqueta"] = True
        return

    if context.user_data.get("esperando_etiqueta"):
        config["configuracion"]["etiqueta"] = text
        guardar_config(config)
        context.user_data.pop("esperando_etiqueta")
        await update.message.reply_text("Muy bien. Escribe una breve descripción de la personalidad del personaje:", parse_mode="HTML")
        context.user_data["esperando_personalidad"] = True
        return

    if context.user_data.get("esperando_personalidad"):
        config["configuracion"]["personalidad"] = text
        guardar_config(config)
        context.user_data.pop("esperando_personalidad")
        await update.message.reply_text("Por último, ingresa los servicios o productos que ofrece (separados por comas):", parse_mode="HTML")
        context.user_data["esperando_servicios"] = True
        return

    if context.user_data.get("esperando_servicios"):
        servicios = [s.strip() for s in text.split(",") if s.strip()]
        config["configuracion"]["servicios"] = servicios
        guardar_config(config)
        context.user_data.pop("esperando_servicios")
        await update.message.reply_text("Ahora, ingresa el idioma en el que deseas redactar los posts (ejemplo: Español, Inglés, etc.):", parse_mode="HTML")
        context.user_data["esperando_idioma"] = True
        return

    if context.user_data.get("esperando_idioma"):
        config["configuracion"]["idioma"] = text
        guardar_config(config)
        context.user_data.pop("esperando_idioma")
        await update.message.reply_text("¡Configuración completada! Usa /menu para ver las opciones.", parse_mode="HTML")
        return

    # Agregar Tipo de Post
    if context.user_data.get("esperando_tipo_post"):
        tipo_post = text.lower()
        if tipo_post in config["tipos_de_post"]:
            await update.message.reply_text("Ese tipo de post ya existe. Prueba con otro nombre.", parse_mode="HTML")
            return
        config["tipos_de_post"][tipo_post] = {"ejemplos": []}
        guardar_config(config)
        context.user_data.pop("esperando_tipo_post")
        await update.message.reply_text(f"Tipo de post '{tipo_post}' agregado correctamente.", parse_mode="HTML")
        return

    # Edición de la configuración del personaje
    if context.user_data.get("edit_nombre"):
        config["configuracion"]["nombre"] = text
        guardar_config(config)
        context.user_data.pop("edit_nombre")
        await update.message.reply_text("Nombre actualizado.", parse_mode="HTML")
        return

    if context.user_data.get("edit_etiqueta"):
        config["configuracion"]["etiqueta"] = text
        guardar_config(config)
        context.user_data.pop("edit_etiqueta")
        await update.message.reply_text("Etiqueta actualizada.", parse_mode="HTML")
        return

    if context.user_data.get("edit_personalidad"):
        config["configuracion"]["personalidad"] = text
        guardar_config(config)
        context.user_data.pop("edit_personalidad")
        await update.message.reply_text("Personalidad actualizada.", parse_mode="HTML")
        return

    if context.user_data.get("edit_servicios"):
        servicios = [s.strip() for s in text.split(",") if s.strip()]
        config["configuracion"]["servicios"] = servicios
        guardar_config(config)
        context.user_data.pop("edit_servicios")
        await update.message.reply_text("Servicios actualizados.", parse_mode="HTML")
        return

    if context.user_data.get("edit_idioma"):
        config["configuracion"]["idioma"] = text
        guardar_config(config)
        context.user_data.pop("edit_idioma")
        await update.message.reply_text("Idioma actualizado.", parse_mode="HTML")
        return

    # Edición de Tipo de Post (renombrar)
    if context.user_data.get("edit_nombre_tipo"):
        tipo_actual = context.user_data.get("tipo_editar")
        if tipo_actual not in config["tipos_de_post"]:
            await update.message.reply_text("Error: Tipo de post no encontrado.", parse_mode="HTML")
            context.user_data.pop("edit_nombre_tipo")
            return
        config["tipos_de_post"][text] = config["tipos_de_post"].pop(tipo_actual)
        guardar_config(config)
        context.user_data.pop("edit_nombre_tipo")
        await update.message.reply_text(f"El tipo de post se ha renombrado a '{text}'.", parse_mode="HTML")
        return

    # Edición de Ejemplo
    if context.user_data.get("editar_ejemplo_indice") is not None:
        indice = context.user_data.get("editar_ejemplo_indice")
        tipo_post = context.user_data.get("tipo_editar")
        try:
            config["tipos_de_post"][tipo_post]["ejemplos"][indice] = process_example_text(text)
            guardar_config(config)
            await update.message.reply_text("Ejemplo actualizado correctamente.", parse_mode="HTML")
        except IndexError:
            await update.message.reply_text("Error al actualizar el ejemplo.", parse_mode="HTML")
        context.user_data.pop("editar_ejemplo_indice")
        return

    await update.message.reply_text("No se reconoce la acción. Usa /menu para ver las opciones.", parse_mode="HTML")

# --- Menú Principal ---
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Agregar Tipo de Post", callback_data="add_tipo_post")],
        [InlineKeyboardButton("➕ Agregar Ejemplo", callback_data="add_ejemplo")],
        [InlineKeyboardButton("📝 Crear Post", callback_data="crear_post")],
        [InlineKeyboardButton("✏️ Editar Configuración", callback_data="editar_config")],
        [InlineKeyboardButton("🌐 Configurar Idioma", callback_data="configurar_idioma")],
        [InlineKeyboardButton("✏️ Editar Tipos de Post", callback_data="editar_tipos")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_message.reply_text("Selecciona una opción:", reply_markup=reply_markup, parse_mode="HTML")

# --- Manejo de botones (CallbackQuery) ---
async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "add_tipo_post":
        await query.message.reply_text("Escribe el nombre del nuevo tipo de post:", parse_mode="HTML")
        context.user_data["esperando_tipo_post"] = True

    elif data == "add_ejemplo":
        tipos = list(config["tipos_de_post"].keys())
        if not tipos:
            await query.message.reply_text("No hay tipos de post registrados. Agrégalo con /menu.", parse_mode="HTML")
            return
        keyboard = [[InlineKeyboardButton(t, callback_data=f"ejemplo_{t}")] for t in tipos]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Selecciona el tipo de post para agregar un ejemplo:", reply_markup=reply_markup, parse_mode="HTML")

    elif data.startswith("ejemplo_"):
        tipo_post = data.split("_", 1)[1]
        context.user_data["tipo_post"] = tipo_post
        context.user_data["esperando_ejemplo"] = True
        await query.message.reply_text(f"Envíame un ejemplo para el tipo de post '{tipo_post}':", parse_mode="HTML")

    elif data == "crear_post":
        tipos = list(config["tipos_de_post"].keys())
        if not tipos:
            await query.message.reply_text("No hay tipos de post registrados. Agrégalo con /menu.", parse_mode="HTML")
            return
        keyboard = [[InlineKeyboardButton(t, callback_data=f"post_{t}")] for t in tipos]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Selecciona el tipo de post:", reply_markup=reply_markup, parse_mode="HTML")

    elif data.startswith("post_"):
        tipo_post = data.split("_", 1)[1]
        context.user_data["tipo_post"] = tipo_post
        context.user_data["esperando_post_tema"] = True
        context.user_data.pop("esperando_ejemplo", None)
        await query.message.reply_text(f"Escribe el tema para el post de tipo '{tipo_post}':", parse_mode="HTML")

    elif data == "editar_config":
        keyboard = [
            [InlineKeyboardButton("Nombre", callback_data="edit_nombre_menu")],
            [InlineKeyboardButton("Etiqueta", callback_data="edit_etiqueta_menu")],
            [InlineKeyboardButton("Personalidad", callback_data="edit_personalidad_menu")],
            [InlineKeyboardButton("Servicios", callback_data="edit_servicios_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Selecciona el campo a editar:", reply_markup=reply_markup, parse_mode="HTML")

    elif data == "edit_nombre_menu":
        context.user_data["edit_nombre"] = True
        await query.message.reply_text("Ingresa el nuevo nombre:", parse_mode="HTML")
    elif data == "edit_etiqueta_menu":
        context.user_data["edit_etiqueta"] = True
        await query.message.reply_text("Ingresa la nueva etiqueta:", parse_mode="HTML")
    elif data == "edit_personalidad_menu":
        context.user_data["edit_personalidad"] = True
        await query.message.reply_text("Ingresa la nueva descripción de personalidad:", parse_mode="HTML")
    elif data == "edit_servicios_menu":
        context.user_data["edit_servicios"] = True
        await query.message.reply_text("Ingresa los nuevos servicios (separados por comas):", parse_mode="HTML")

    elif data == "configurar_idioma":
        context.user_data["edit_idioma"] = True
        await query.message.reply_text("Ingresa el idioma en el que deseas redactar los posts:", parse_mode="HTML")

    elif data == "editar_tipos":
        if not config["tipos_de_post"]:
            await query.message.reply_text("No hay tipos de post para editar.", parse_mode="HTML")
            return
        keyboard = []
        for t in config["tipos_de_post"]:
            keyboard.append([InlineKeyboardButton(t, callback_data=f"edit_tipo_{t}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Selecciona el tipo de post a editar:", reply_markup=reply_markup, parse_mode="HTML")

    elif data.startswith("edit_tipo_"):
        tipo_post = data.split("_", 2)[2]
        context.user_data["tipo_editar"] = tipo_post
        keyboard = [
            [InlineKeyboardButton("Editar nombre", callback_data="editar_nombre_tipo")],
            [InlineKeyboardButton("Eliminar tipo", callback_data="eliminar_tipo")],
            [InlineKeyboardButton("Ver ejemplos", callback_data="ver_ejemplos")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(f"Opciones para el tipo '{tipo_post}':", reply_markup=reply_markup, parse_mode="HTML")

    elif data == "editar_nombre_tipo":
        context.user_data["edit_nombre_tipo"] = True
        await query.message.reply_text("Ingresa el nuevo nombre para este tipo de post:", parse_mode="HTML")

    elif data == "eliminar_tipo":
        tipo_post = context.user_data.get("tipo_editar")
        keyboard = [
            [InlineKeyboardButton("Sí, eliminar", callback_data="confirm_eliminar_tipo")],
            [InlineKeyboardButton("No", callback_data="cancel_eliminar_tipo")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            f"¿Estás seguro de eliminar el tipo de post '{tipo_post}'? Se borrarán también todos sus ejemplos.",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

    elif data == "confirm_eliminar_tipo":
        tipo_post = context.user_data.get("tipo_editar")
        if tipo_post in config["tipos_de_post"]:
            del config["tipos_de_post"][tipo_post]
            guardar_config(config)
            await query.message.reply_text(f"Tipo de post '{tipo_post}' eliminado.", parse_mode="HTML")
        else:
            await query.message.reply_text("Error: Tipo de post no encontrado.", parse_mode="HTML")
        context.user_data.pop("tipo_editar", None)

    elif data == "cancel_eliminar_tipo":
        await query.message.reply_text("Eliminación cancelada.", parse_mode="HTML")
        context.user_data.pop("tipo_editar", None)

    elif data == "ver_ejemplos":
        tipo_post = context.user_data.get("tipo_editar")
        ejemplos = config["tipos_de_post"][tipo_post]["ejemplos"]
        if not ejemplos:
            await query.message.reply_text("No hay ejemplos para este tipo de post.", parse_mode="HTML")
            return
        keyboard = []
        for idx, ej in enumerate(ejemplos, start=1):
            boton_text = f"{idx}. {ej[:20]}{'...' if len(ej) > 20 else ''}"
            keyboard.append([InlineKeyboardButton(boton_text, callback_data=f"editar_ejemplos_{idx-1}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Selecciona el ejemplo a editar/eliminar:", reply_markup=reply_markup, parse_mode="HTML")

    elif data.startswith("editar_ejemplos_"):
        indice = int(data.split("_")[-1])
        tipo_post = context.user_data.get("tipo_editar")
        try:
            ejemplo = config["tipos_de_post"][tipo_post]["ejemplos"][indice]
        except IndexError:
            await query.message.reply_text("Ejemplo no encontrado.", parse_mode="HTML")
            return
        await query.message.reply_text(f"Ejemplo seleccionado:\n{ejemplo}", parse_mode="HTML")
        keyboard = [
            [InlineKeyboardButton("Editar", callback_data=f"modificar_ejemplo_{indice}")],
            [InlineKeyboardButton("Eliminar", callback_data=f"borrar_ejemplo_{indice}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("¿Qué deseas hacer con este ejemplo?", reply_markup=reply_markup, parse_mode="HTML")

    elif data.startswith("modificar_ejemplo_"):
        indice = int(data.split("_")[-1])
        context.user_data["editar_ejemplo_indice"] = indice
        await query.message.reply_text("Envía el nuevo texto para este ejemplo:", parse_mode="HTML")

    elif data.startswith("borrar_ejemplos_") or data.startswith("borrar_ejemplo_"):
        indice = int(data.split("_")[-1])
        tipo_post = context.user_data.get("tipo_editar")
        try:
            borrado = config["tipos_de_post"][tipo_post]["ejemplos"].pop(indice)
            guardar_config(config)
            await query.message.reply_text(f"Ejemplo borrado:\n{borrado}", parse_mode="HTML")
        except IndexError:
            await query.message.reply_text("Error al borrar el ejemplo.", parse_mode="HTML")

    # Aceptar Post: al aceptar, se muestran los mensajes finales y se muestra el menú
    elif data == "aceptar_post":
        post = context.user_data.get("ultimo_post", "")
        await query.message.reply_text("Post aceptado:", parse_mode="HTML")
        await query.message.reply_text(post, parse_mode="HTML")
        context.user_data.pop("ultimo_post", None)
        context.user_data.pop("ultimo_tipo_post", None)
        context.user_data.pop("ultimo_tema", None)
        context.user_data.pop("ultimo_ejemplo_index", None)
        # Mostrar el menú automáticamente
        await menu(update, context)

    elif data == "reescribir_post":
        tipo_post = context.user_data.get("ultimo_tipo_post")
        tema = context.user_data.get("ultimo_tema")
        idioma = config["configuracion"].get("idioma", "Español")
        prev_index = context.user_data.get("ultimo_ejemplo_index")
        new_post, new_index = await generate_post(tipo_post, tema, idioma, previous_index=prev_index)
        context.user_data["ultimo_post"] = new_post
        context.user_data["ultimo_ejemplo_index"] = new_index
        await presentar_post(update, context, new_post)

# --- Manejo adicional para editar textos (mensaje) ---
async def editar_textos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("edit_nombre_tipo"):
        tipo_actual = context.user_data.get("tipo_editar")
        if tipo_actual not in config["tipos_de_post"]:
            await update.message.reply_text("Error: Tipo de post no encontrado.", parse_mode="HTML")
            context.user_data.pop("edit_nombre_tipo")
            return
        config["tipos_de_post"][update.message.text.strip()] = config["tipos_de_post"].pop(tipo_actual)
        guardar_config(config)
        context.user_data.pop("edit_nombre_tipo")
        await update.message.reply_text(f"El tipo de post se ha renombrado a '{update.message.text.strip()}'.", parse_mode="HTML")
        return
    await recibir_mensaje(update, context)

# --- Configuración del Bot ---
app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("menu", menu))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, editar_textos))
app.add_handler(CallbackQueryHandler(botones))

logger.info("Bot en marcha...")
app.run_polling()
