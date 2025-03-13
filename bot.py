import json
import openai
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes
)

# Cargar variables de entorno
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

CONFIG_FILE = "config.json"

# Función para cargar la configuración desde el JSON
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
                "servicios": []
            },
            "tipos_de_post": {}
        }

# Función para guardar la configuración en el JSON
def guardar_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=4, ensure_ascii=False)

config = cargar_config()

# ----------------------
# FLUJO DE CONFIGURACIÓN
# ----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Si la configuración está incompleta se pregunta por el nombre
    if not config["configuracion"]["nombre"]:
        await update.message.reply_text("¡Hola! Vamos a configurar tu bot.\nPrimero, ¿cómo se llama tu personaje?")
        context.user_data["esperando_nombre"] = True
    else:
        await update.message.reply_text("La configuración ya existe. Usa /menu para ver las opciones.")

async def recibir_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # ----------------------
    # CONFIGURACIÓN DEL PERSONAJE
    # ----------------------
    if context.user_data.get("esperando_nombre"):
        config["configuracion"]["nombre"] = text
        guardar_config(config)
        await update.message.reply_text("Perfecto. Ahora ingresa la etiqueta (ejemplo: @ejemplo):")
        context.user_data.pop("esperando_nombre")
        context.user_data["esperando_etiqueta"] = True
        return

    if context.user_data.get("esperando_etiqueta"):
        config["configuracion"]["etiqueta"] = text
        guardar_config(config)
        await update.message.reply_text("Muy bien. Escribe una breve descripción de la personalidad del personaje:")
        context.user_data.pop("esperando_etiqueta")
        context.user_data["esperando_personalidad"] = True
        return

    if context.user_data.get("esperando_personalidad"):
        config["configuracion"]["personalidad"] = text
        guardar_config(config)
        await update.message.reply_text("Por último, ingresa los servicios o productos que ofrece (separados por comas):")
        context.user_data.pop("esperando_personalidad")
        context.user_data["esperando_servicios"] = True
        return

    if context.user_data.get("esperando_servicios"):
        servicios = [s.strip() for s in text.split(",") if s.strip()]
        config["configuracion"]["servicios"] = servicios
        guardar_config(config)
        context.user_data.pop("esperando_servicios")
        await update.message.reply_text("Configuración completada. Usa /menu para ver las opciones.")
        return

    # ----------------------
    # AGREGAR TIPO DE POST
    # ----------------------
    if context.user_data.get("esperando_tipo_post"):
        tipo_post = text.lower()
        if tipo_post in config["tipos_de_post"]:
            await update.message.reply_text("Ese tipo de post ya existe. Prueba con otro nombre.")
            return
        
        config["tipos_de_post"][tipo_post] = {"ejemplos": []}
        guardar_config(config)
        context.user_data.pop("esperando_tipo_post")
        await update.message.reply_text(f"Tipo de post '{tipo_post}' agregado correctamente.\nUsa /menu para más opciones.")
        return

    # ----------------------
    # AGREGAR EJEMPLO A UN TIPO DE POST
    # ----------------------
    if context.user_data.get("esperando_ejemplo"):
        tipo_post = context.user_data.get("tipo_post")
        if not tipo_post:
            await update.message.reply_text("Error: No se ha seleccionado un tipo de post.")
            return

        if text in config["tipos_de_post"][tipo_post]["ejemplos"]:
            await update.message.reply_text("Este ejemplo ya existe. No se ha agregado duplicado.")
            return

        config["tipos_de_post"][tipo_post]["ejemplos"].append(text)
        guardar_config(config)
        await update.message.reply_text(f"Ejemplo agregado al tipo de post '{tipo_post}'.\nPuedes seguir agregando más o usar /menu.")
        return

    # ----------------------
    # GENERAR POST CON CHATGPT
    # ----------------------
    if context.user_data.get("esperando_post_tema"):
        tipo_post = context.user_data.get("tipo_post")
        context.user_data.pop("esperando_post_tema")
        ejemplos = config["tipos_de_post"][tipo_post]["ejemplos"]

        if not ejemplos:
            await update.message.reply_text("No hay ejemplos en esta categoría. Agrega algunos antes de generar un post.")
            return

        # Selecciona aleatoriamente un ejemplo para inspirar el post
        import random
        ejemplo_seleccionado = random.choice(ejemplos)

        # Se arma el prompt combinando el ejemplo y el tema ingresado
        prompt = (
    f"Genera un post para Telegram inspirado en el siguiente ejemplo. "
    f"El post NO debe ser una copia exacta, pero debe mantener la misma magnitud en tamaño y estilo. "
    f"Debe respetar la estructura y el formato, uso de negritas, cursivas, mayúsculas, espaciado del ejemplo, entre otros. "
    f"NO uses signos de punto (.) ni hashtags.\n\n"
    f"Ejemplo:\n{ejemplo_seleccionado}\n\n"
    f"Ahora, genera un post sobre el siguiente tema manteniendo el estilo del ejemplo:\n"
    f"{text}\n\n"
    f"---\n"
    f"Datos del personaje:\n"
    f"Nombre: {config['configuracion']['nombre']}\n"
    f"Etiqueta: {config['configuracion']['etiqueta']}\n"
    f"Personalidad: {config['configuracion']['personalidad']}\n"
    f"Servicios: {', '.join(config['configuracion']['servicios'])}"
)


        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"Habla como {config['configuracion']['nombre']}."},
                    {"role": "user", "content": prompt}
                ]
            )
            resultado = response["choices"][0]["message"]["content"]
            await update.message.reply_text(resultado)
        except Exception as e:
            await update.message.reply_text(f"Ocurrió un error al generar el post: {e}")
        return

    # ----------------------
    # EDITAR CONFIGURACIÓN
    # ----------------------
    if context.user_data.get("edit_nombre"):
        config["configuracion"]["nombre"] = text
        guardar_config(config)
        context.user_data.pop("edit_nombre")
        await update.message.reply_text("Nombre actualizado.")
        return

    if context.user_data.get("edit_etiqueta"):
        config["configuracion"]["etiqueta"] = text
        guardar_config(config)
        context.user_data.pop("edit_etiqueta")
        await update.message.reply_text("Etiqueta actualizada.")
        return

    if context.user_data.get("edit_personalidad"):
        config["configuracion"]["personalidad"] = text
        guardar_config(config)
        context.user_data.pop("edit_personalidad")
        await update.message.reply_text("Personalidad actualizada.")
        return

    if context.user_data.get("edit_servicios"):
        servicios = [s.strip() for s in text.split(",") if s.strip()]
        config["configuracion"]["servicios"] = servicios
        guardar_config(config)
        context.user_data.pop("edit_servicios")
        await update.message.reply_text("Servicios actualizados.")
        return

    # Si no coincide con ninguna bandera, se indica que no se reconoce el mensaje
    await update.message.reply_text("No se reconoce la acción. Usa /menu para ver las opciones.")

# ----------------------
# MENÚ PRINCIPAL
# ----------------------
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Agregar Tipo de Post", callback_data="add_tipo_post")],
        [InlineKeyboardButton("➕ Agregar Ejemplo", callback_data="add_ejemplo")],
        [InlineKeyboardButton("📝 Crear Post", callback_data="crear_post")],
        [InlineKeyboardButton("✏️ Editar Configuración", callback_data="editar_config")],
        [InlineKeyboardButton("✏️ Editar Tipos de Post", callback_data="editar_tipos")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_message.reply_text("Selecciona una opción:", reply_markup=reply_markup)

# ----------------------
# MANEJO DE BOTONES (CALLBACK)
# ----------------------
async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # Agregar tipo de post
    if data == "add_tipo_post":
        await query.message.reply_text("Escribe el nombre del nuevo tipo de post:")
        context.user_data["esperando_tipo_post"] = True

    # Agregar ejemplo a un tipo de post
    elif data == "add_ejemplo":
        tipos = list(config["tipos_de_post"].keys())
        if not tipos:
            await query.message.reply_text("No hay tipos de post registrados. Agrega uno con /menu.")
            return
        keyboard = [[InlineKeyboardButton(t, callback_data=f"ejemplo_{t}")] for t in tipos]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Selecciona el tipo de post para agregar un ejemplo:", reply_markup=reply_markup)

    elif data.startswith("ejemplo_"):
        tipo_post = data.split("_", 1)[1]
        context.user_data["tipo_post"] = tipo_post
        context.user_data["esperando_ejemplo"] = True
        await query.message.reply_text(f"Envíame un ejemplo para el tipo de post '{tipo_post}'.")

    # Generar post
    elif data == "crear_post":
        tipos = list(config["tipos_de_post"].keys())
        if not tipos:
            await query.message.reply_text("No hay tipos de post registrados. Agrega uno con /menu.")
            return
        keyboard = [[InlineKeyboardButton(t, callback_data=f"post_{t}")] for t in tipos]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Selecciona el tipo de post:", reply_markup=reply_markup)

    elif data.startswith("post_"):
        tipo_post = data.split("_", 1)[1]
        context.user_data["tipo_post"] = tipo_post
        context.user_data["esperando_post_tema"] = True
        await query.message.reply_text(f"Escribe el tema para el post de tipo '{tipo_post}':")

    # Editar configuración del personaje
    elif data == "editar_config":
        keyboard = [
            [InlineKeyboardButton("Nombre", callback_data="edit_nombre_menu")],
            [InlineKeyboardButton("Etiqueta", callback_data="edit_etiqueta_menu")],
            [InlineKeyboardButton("Personalidad", callback_data="edit_personalidad_menu")],
            [InlineKeyboardButton("Servicios", callback_data="edit_servicios_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Selecciona el campo a editar:", reply_markup=reply_markup)

    elif data == "edit_nombre_menu":
        context.user_data["edit_nombre"] = True
        await query.message.reply_text("Ingresa el nuevo nombre:")
    elif data == "edit_etiqueta_menu":
        context.user_data["edit_etiqueta"] = True
        await query.message.reply_text("Ingresa la nueva etiqueta:")
    elif data == "edit_personalidad_menu":
        context.user_data["edit_personalidad"] = True
        await query.message.reply_text("Ingresa la nueva descripción de personalidad:")
    elif data == "edit_servicios_menu":
        context.user_data["edit_servicios"] = True
        await query.message.reply_text("Ingresa los nuevos servicios (separados por comas):")

    # Editar tipos de post
    elif data == "editar_tipos":
        if not config["tipos_de_post"]:
            await query.message.reply_text("No hay tipos de post para editar.")
            return
        # Se listan los tipos de post para editar
        keyboard = []
        for t in config["tipos_de_post"]:
            keyboard.append([InlineKeyboardButton(t, callback_data=f"edit_tipo_{t}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Selecciona el tipo de post a editar:", reply_markup=reply_markup)

    elif data.startswith("edit_tipo_"):
        tipo_post = data.split("_", 2)[2]
        context.user_data["tipo_editar"] = tipo_post
        keyboard = [
            [InlineKeyboardButton("Editar nombre", callback_data="editar_nombre_tipo")],
            [InlineKeyboardButton("Eliminar tipo", callback_data="eliminar_tipo")],
            [InlineKeyboardButton("Ver ejemplos", callback_data="ver_ejemplos")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(f"Opciones para el tipo '{tipo_post}':", reply_markup=reply_markup)

    # Editar nombre del tipo de post
    elif data == "editar_nombre_tipo":
        context.user_data["edit_nombre_tipo"] = True
        await query.message.reply_text("Ingresa el nuevo nombre para este tipo de post:")

    # Confirmar eliminación del tipo de post
    elif data == "eliminar_tipo":
        tipo_post = context.user_data.get("tipo_editar")
        keyboard = [
            [InlineKeyboardButton("Sí, eliminar", callback_data="confirm_eliminar_tipo")],
            [InlineKeyboardButton("No", callback_data="cancel_eliminar_tipo")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(f"¿Estás seguro de eliminar el tipo de post '{tipo_post}'? Se borrarán también todos sus ejemplos.", reply_markup=reply_markup)

    elif data == "confirm_eliminar_tipo":
        tipo_post = context.user_data.get("tipo_editar")
        if tipo_post in config["tipos_de_post"]:
            del config["tipos_de_post"][tipo_post]
            guardar_config(config)
            await query.message.reply_text(f"Tipo de post '{tipo_post}' eliminado.")
        else:
            await query.message.reply_text("Error: Tipo de post no encontrado.")
        context.user_data.pop("tipo_editar", None)

    elif data == "cancel_eliminar_tipo":
        await query.message.reply_text("Eliminación cancelada.")
        context.user_data.pop("tipo_editar", None)

    # Ver y editar ejemplos del tipo de post
    elif data == "ver_ejemplos":
        tipo_post = context.user_data.get("tipo_editar")
        ejemplos = config["tipos_de_post"][tipo_post]["ejemplos"]
        if not ejemplos:
            await query.message.reply_text("No hay ejemplos para este tipo de post.")
            return
        keyboard = []
        for idx, ej in enumerate(ejemplos, start=1):
            # Se muestra el número y un adelanto del texto (primeros 20 caracteres)
            boton_text = f"{idx}. {ej[:20]}{'...' if len(ej) > 20 else ''}"
            keyboard.append([InlineKeyboardButton(boton_text, callback_data=f"editar_ejemplo_{idx-1}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Selecciona el ejemplo a editar/eliminar:", reply_markup=reply_markup)

    # Editar o eliminar un ejemplo específico
    elif data.startswith("editar_ejemplo_"):
        indice = int(data.split("_")[-1])
        tipo_post = context.user_data.get("tipo_editar")
        try:
            ejemplo = config["tipos_de_post"][tipo_post]["ejemplos"][indice]
        except IndexError:
            await query.message.reply_text("Ejemplo no encontrado.")
            return
        # Opciones para el ejemplo seleccionado
        keyboard = [
            [InlineKeyboardButton("Editar", callback_data=f"modificar_ejemplo_{indice}")],
            [InlineKeyboardButton("Eliminar", callback_data=f"borrar_ejemplo_{indice}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(f"Ejemplo seleccionado:\n{ejemplo}\n¿Qué deseas hacer?", reply_markup=reply_markup)

    elif data.startswith("modificar_ejemplo_"):
        indice = int(data.split("_")[-1])
        context.user_data["editar_ejemplo_indice"] = indice
        await query.message.reply_text("Envía el nuevo texto para este ejemplo:")

    elif data.startswith("borrar_ejemplo_"):
        indice = int(data.split("_")[-1])
        tipo_post = context.user_data.get("tipo_editar")
        try:
            borrado = config["tipos_de_post"][tipo_post]["ejemplos"].pop(indice)
            guardar_config(config)
            await query.message.reply_text(f"Ejemplo borrado:\n{borrado}")
        except IndexError:
            await query.message.reply_text("Error al borrar el ejemplo.")

    return

# Manejo adicional para editar el nombre del tipo de post y modificar ejemplos
async def editar_textos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # Editar nombre del tipo de post
    if context.user_data.get("edit_nombre_tipo"):
        tipo_actual = context.user_data.get("tipo_editar")
        if tipo_actual not in config["tipos_de_post"]:
            await update.message.reply_text("Error: Tipo de post no encontrado.")
            context.user_data.pop("edit_nombre_tipo", None)
            return
        # Actualizar la clave en el diccionario
        config["tipos_de_post"][text] = config["tipos_de_post"].pop(tipo_actual)
        guardar_config(config)
        context.user_data.pop("edit_nombre_tipo", None)
        await update.message.reply_text(f"El tipo de post se ha renombrado a '{text}'.")
        return

    # Modificar un ejemplo específico
    if context.user_data.get("editar_ejemplo_indice") is not None:
        indice = context.user_data.get("editar_ejemplo_indice")
        tipo_post = context.user_data.get("tipo_editar")
        try:
            config["tipos_de_post"][tipo_post]["ejemplos"][indice] = text
            guardar_config(config)
            await update.message.reply_text("Ejemplo actualizado correctamente.")
        except IndexError:
            await update.message.reply_text("Error al actualizar el ejemplo.")
        context.user_data.pop("editar_ejemplo_indice", None)
        return

    # Si llega aquí y no se reconoce la acción, delega al handler principal
    await recibir_mensaje(update, context)

# ----------------------
# CONFIGURACIÓN DEL BOT
# ----------------------
app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("menu", menu))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, editar_textos))
app.add_handler(CallbackQueryHandler(botones))

print("Bot en marcha...")
app.run_polling()
