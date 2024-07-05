import logging
import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler

# Вставьте ваш API Token из переменных окружения
API_TOKEN = os.getenv('API_TOKEN')

# Email settings из переменных окружения
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
EMAIL_RECEIVER = os.getenv('EMAIL_RECEIVER')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT'))

# Включение логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Состояния разговора
(
    SENDER_NAME,
    DEPARTMENT,
    INVOICE_AMOUNT,
    INVOICE_DATE,
    COMMENTS,
    FILE,
) = range(6)

# Функция для приветствия пользователя и отображения меню
async def start(update: Update, context: CallbackContext):
    logging.info("Команда /start получена")
    user_first_name = update.message.chat.first_name
    menu_keyboard = [
        ["Отправить счет", "Помощь"]
    ]
    reply_markup = ReplyKeyboardMarkup(menu_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(f'Здравствуйте, {user_first_name}! Как я могу вам помочь?', reply_markup=reply_markup)
    return SENDER_NAME

async def sender_name(update: Update, context: CallbackContext):
    context.user_data['sender_name'] = update.message.text
    await update.message.reply_text('Введите отдел вашей компании.')
    return DEPARTMENT

async def department(update: Update, context: CallbackContext):
    context.user_data['department'] = update.message.text
    await update.message.reply_text('Введите сумму счета.')
    return INVOICE_AMOUNT

async def invoice_amount(update: Update, context: CallbackContext):
    context.user_data['invoice_amount'] = update.message.text
    await update.message.reply_text('Введите дату счета (например, 2024-07-05).')
    return INVOICE_DATE

async def invoice_date(update: Update, context: CallbackContext):
    context.user_data['invoice_date'] = update.message.text
    await update.message.reply_text('Введите комментарии к счету.')
    return COMMENTS

async def comments(update: Update, context: CallbackContext):
    context.user_data['comments'] = update.message.text
    await update.message.reply_text('Пожалуйста, загрузите файл счета.')
    return FILE

async def handle_file(update: Update, context: CallbackContext):
    file = await update.message.document.get_file()
    file_path = f'invoice_{update.message.document.file_name}'
    await file.download_to_drive(file_path)  # Сохраняем файл
    logging.info(f"Файл сохранен: {file_path}")
    
    # Отправляем файл на email гендиректора
    send_email(file_path, context.user_data)

    logging.info("Счет отправлен на согласование")
    await update.message.reply_text('Счет отправлен на согласование. Спасибо!')
    return ConversationHandler.END

def send_email(file_path, user_data):
    logging.info(f"Начало отправки email с файлом: {file_path}")
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = 'Новый счет на оплату'
        body = (
            f"ФИО отправителя: {user_data['sender_name']}\n"
            f"Отдел: {user_data['department']}\n"
            f"Сумма счета: {user_data['invoice_amount']}\n"
            f"Дата счета: {user_data['invoice_date']}\n"
            f"Комментарии: {user_data['comments']}\n"
        )
        msg.attach(MIMEText(body, 'plain'))

        with open(file_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename= {os.path.basename(file_path)}')
            msg.attach(part)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        logging.info("Email успешно отправлен")
    except Exception as e:
        logging.error(f"Ошибка при отправке email: {e}")

async def help_command(update: Update, context: CallbackContext):
    await update.message.reply_text('Я могу помочь вам с отправкой счета на оплату. Используйте команды: \n/start - начать процесс отправки счета \n/cancel - отменить процесс')

async def cancel(update: Update, context: CallbackContext):
    await update.message.reply_text('Операция отменена.')
    return ConversationHandler.END

def main():
    application = Application.builder().token(API_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SENDER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, sender_name)],
            DEPARTMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, department)],
            INVOICE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, invoice_amount)],
            INVOICE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, invoice_date)],
            COMMENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, comments)],
            FILE: [MessageHandler(filters.Document.ALL, handle_file)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))

    logging.info("Бот запущен, ожидает сообщений")
    application.run_polling()

if __name__ == '__main__':
    main()
