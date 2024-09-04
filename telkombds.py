import logging
import os
import mysql.connector
from mysql.connector import Error
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters
import datetime

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Define states for the conversation
NAMA, ASAL_INSTANSI, KEPERLUAN, GAMBAR, CONFIRMATION = range(5)

# Directory to store images
IMAGE_DIR = "visitor_images"
os.makedirs(IMAGE_DIR, exist_ok=True)

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'visitor_management'
}

# Function to create database connection
def create_db_connection():
    try:
        connection = mysql.connector.connect(**db_config)
        return connection if connection else None
    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
        return None

# Function to insert a visitor record into the database
def insert_visitor(visitor_data):
    connection = create_db_connection()
    if connection is None:
        return False

    try:
        cursor = connection.cursor()
        query = """INSERT INTO visitors (tanggal, nama, asal_instansi, keperluan, gambar) 
                   VALUES (%s, %s, %s, %s, %s)"""
        cursor.execute(query, (visitor_data['Tanggal'], visitor_data['Nama'], 
                               visitor_data['Asal Instansi'], visitor_data['Keperluan'],
                               visitor_data['Gambar']))
        connection.commit()
        return True
    except Error as e:
        print(f"Error while inserting visitor: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Welcome to the Site Visitor Bot! Use /help to see available commands.')

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('This bot helps track site visitors. Use /inputvisit to add new visitor data.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
    Available commands:
    /start - Start the bot
    /info - Get information about the bot
    /help - Show this help message
    /status - Check the current status
    /inputvisit - Input new site visitor data
    """
    await update.message.reply_text(help_text)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    connection = create_db_connection()
    if connection is None:
        await update.message.reply_text('Unable to connect to the database.')
        return

    try:
        cursor = connection.cursor()
        cursor.execute('SELECT COUNT(*) FROM visitors')
        visitor_count = cursor.fetchone()[0]
        await update.message.reply_text(f'Current status: {visitor_count} visitors recorded.')
    except Error as e:
        print(f"Error while getting status: {e}")
        await update.message.reply_text('Error retrieving visitor count.')
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Conversation handlers
async def input_visit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Please enter the visitor data:\nNama:')
    return NAMA

async def nama(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['nama'] = update.message.text
    if 'asal_instansi' not in context.user_data:
        await update.message.reply_text('Asal Instansi:')
        return ASAL_INSTANSI
    return await confirm_data(update, context)

async def asal_instansi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['asal_instansi'] = update.message.text
    if 'keperluan' not in context.user_data:
        await update.message.reply_text('Keperluan:')
        return KEPERLUAN
    return await confirm_data(update, context)

async def keperluan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['keperluan'] = update.message.text
    if 'gambar' not in context.user_data:
        await update.message.reply_text('Please upload the visitor’s image (selfie):')
        return GAMBAR
    return await confirm_data(update, context)

async def gambar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.photo:
        photo = update.message.photo[-1]  # Get the highest resolution photo
        file = await photo.get_file()
        image_path = os.path.join(IMAGE_DIR, f"{context.user_data['nama']}.jpg")
        await file.download_to_drive(image_path)
        context.user_data['gambar'] = image_path
    else:
        await update.message.reply_text('Please upload a valid image.')
        return GAMBAR

    return await confirm_data(update, context)

async def confirm_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    confirmation_text = (
        f"Please confirm the visitor data:\n\n"
        f"1. Nama: {context.user_data.get('nama', 'Not provided')}\n"
        f"2. Asal Instansi: {context.user_data.get('asal_instansi', 'Not provided')}\n"
        f"3. Keperluan: {context.user_data.get('keperluan', 'Not provided')}\n"
        f"4. Gambar: {'(Image saved)' if 'gambar' in context.user_data else 'Not uploaded'}\n\n"
        "Please select an option:\n"
        "1 - Confirm\n"
        "2 - Edit Nama\n"
        "3 - Edit Asal Instansi\n"
        "4 - Edit Keperluan\n"
        "5 - Edit Gambar"
    )

    await update.message.reply_text(confirmation_text)
    return CONFIRMATION

async def confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text.strip()

    if choice == "1":
        current_datetime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        context.user_data['tanggal'] = current_datetime

        visitor_data = {
            'Tanggal': context.user_data['tanggal'],
            'Nama': context.user_data['nama'],
            'Asal Instansi': context.user_data['asal_instansi'],
            'Keperluan': context.user_data['keperluan'],
            'Gambar': context.user_data['gambar']
        }
        
        if insert_visitor(visitor_data):
            await update.message.reply_text(f"Visit recorded in the database at {current_datetime}.")
        else:
            await update.message.reply_text("Failed to record the visit. Please try again.")
        return ConversationHandler.END

    elif choice == "2":
        await update.message.reply_text("Please enter the correct Nama:")
        return NAMA
    elif choice == "3":
        await update.message.reply_text("Please enter the correct Asal Instansi:")
        return ASAL_INSTANSI
    elif choice == "4":
        await update.message.reply_text("Please enter the correct Keperluan:")
        return KEPERLUAN
    elif choice == "5":
        await update.message.reply_text("Please upload the correct image:")
        return GAMBAR
    else:
        await update.message.reply_text("Invalid choice. Please select a valid option (1-5).")
        return CONFIRMATION

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Input cancelled.')
    return ConversationHandler.END

def main() -> None:
    application = Application.builder().token('6717889021:AAHiFg2JS37cxd2ZYYWgqXG7-mol9qfgcaU').build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('inputvisit', input_visit)],
        states={
            NAMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, nama)],
            ASAL_INSTANSI: [MessageHandler(filters.TEXT & ~filters.COMMAND, asal_instansi)],
            KEPERLUAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, keperluan)],
            GAMBAR: [MessageHandler(filters.PHOTO & ~filters.COMMAND, gambar)],
            CONFIRMATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmation)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))

    application.run_polling()

if __name__ == '__main__':
    main()
