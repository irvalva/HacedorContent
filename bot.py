import json
import openai
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

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
        return {"configuracion": {"nombre": "", "etiqueta": "", "personalidad": "", "servicios": []}, "tipos_de_post": {}}

# Función para guardar la configuración en el JSON
def guardar_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=4, ensure_ascii=False)

config = cargar_config()

# Comando /start para iniciar la configuración
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Vamos a configurar tu bot. ¿Cómo se llama tu personaje?")
    context.user_data["esperando_nombre"] = True

# Manejo de respuestas del usuario
async def recibir_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if "esperando_nombre" in context.user_data:
        config["configuracion"]["nombre"] = text
        del context.user_data["esperando_nombre"]
        await update.message.reply_text(f"Nombre guardado: {text}\nAhora dime la etiqueta para CTA (@usuario).")
        context.user_data["esperando_etiqueta"] = True
        guardar_config(config)

    elif "esperando_etiqueta" in context.user_data:
        config["configuracion"]["etiqueta"] = text
        del context.user_data["esperando_etiqueta"]
        await update.message.reply_text("Etiqueta guardada. Ahora describe la personalidad del personaje.")
        context.user_data["esperando_personalidad"] = True
        guardar_config(config)

    elif "esperando_personalidad" in context.user_data:
        config["configuracion"]["personalidad"] = text
        del context.user_data["esperando_personalidad"]
        await update.message.reply_text("Personalidad guardada. ¿Qué servicios o productos vende? (Envíalos separados por comas)")
        context.user_data["esperando_servicios"] = True
        guardar_config(config)

    elif "esperando_servicios" in context.user_data:
        config["configuracion"]["servicios"] = [s.strip() for s in text.split(",")]
        del context.user_data["esperando_servicios"]
        await update.message.reply_text("Servicios guardados. ¡Configuración completada! Usa /menu para más opciones.")
        guardar_config(config)

    elif "esperando_tipo_post" in context.user_data:
        tipo_post = text.lower()
        if tipo_post in config["tipos_de_post"]:
            await update.message.reply_text("Ese tipo de post ya existe. Prueba con otro nombre.")
            return
        
        config["tipos_de_post"][tipo_post] = {"ejemplos": []}
        del context.user_data["esperando_tipo_post"]
        guardar_config(config)
        await update.message.reply_text(f"Tipo de post '{tipo_post}' agregado correctamente. Ahora puedes agregar ejemplos con /menu.")

    elif "esperando_ejemplo" in context.user_data:
        tipo_post = context.user_data["tipo_post"]
        
        # Si el usuario está en modo "crear post", evitar agregar como ejemplo
        if "esperando_post_tema" in context.user_data:
            await update.message.reply_text("Parece que quieres generar un post. Usa /menu para elegir la opción correcta.")
            return

        config["tipos_de_post"][tipo_post]["ejemplos"].append(text)
        guardar_config(config)
        await update.message.reply_text(f"Ejemplo agregado al tipo de post '{tipo_post}'. Puedes seguir agregando más o usar /menu para otras opciones.")

    elif "esperando_post_tema" in context.user_data:
        tipo_post = context.user_data["tipo_post"]
        del context.user_data["esperando_post_tema"]
        
        ejemplos = config["tipos_de_post"][tipo_post]["ejemplos"]
        
        if not ejemplos:
            await update.message.reply_text("No hay ejemplos en esta categoría. Agrega algunos antes de generar un post.")
            return

        prompt = f"Genera un post similar a estos ejemplos:\n" + "\n".join(ejemplos) + f"\n\nTema: {text}"

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": f"Habla como {config['configuracion']['nombre']}"},
                      {"role": "user", "content": prompt}]
        )

        resultado = response["choices"][0]["message"]["content"]
        await update.message.reply_text(resultado)

# Comando /menu para mostrar opciones
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Agregar Tipo de Post", callback_data="add_tipo_post")],
        [InlineKeyboardButton("➕ Agregar Ejemplo", callback_data="add_ejemplo")],
        [InlineKeyboardButton("✏️ Editar/Eliminar Ejemplo", callback_data="edit_ejemplo")],
        [InlineKeyboardButton("✏️ Editar/Eliminar Tipo de Post", callback_data="edit_tipo")],
        [InlineKeyboardButton("📝 Crear Post", callback_data="crear_post")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Corregimos el error: usamos effective_message para manejar tanto mensajes como botones
    await update.effective_message.reply_text("Selecciona una opción:", reply_markup=reply_markup)


# Función para editar o eliminar ejemplos (próxima implementación)
async def editar_ejemplo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Función en desarrollo...")

# Función para editar o eliminar tipos de post (próxima implementación)
async def editar_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Función en desarrollo...")

# Configurar el bot y añadir manejadores
app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("menu", menu))
app.add_handler(CommandHandler("editar_ejemplo", editar_ejemplo))
app.add_handler(CommandHandler("editar_tipo", editar_tipo))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_mensaje))
app.add_handler(CallbackQueryHandler(menu))

# Iniciar el bot
print("Bot en marcha...")
app.run_polling()
