import logging
import os
from telegram import Update, Document
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.mime.text import MIMEText

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
    INVOICE_AMOUNT,
    INVOICE_DATE,
    COMMENTS,
    FILE,
) = range(4)

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text('Здравствуйте! Напишите "счет", чтобы начать процесс отправки счета.')

async def start_invoice(update: Update, context: CallbackContext):
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

    await update.message.reply_text('Счет отправлен на согласование. Спасибо!')
    return ConversationHandler.END

def send_email(file_path, user_data):
    logging.info(f"Начало отправки email с данными: {user_data}")
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = 'Новый счет на оплату'
        body = (
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

async def cancel(update: Update, context: CallbackContext):
    await update.message.reply_text('Операция отменена.')
    return ConversationHandler.END

def main():
    application = Application.builder().token(API_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('(?i)счет'), start_invoice)],
        states={
            INVOICE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, invoice_amount)],
            INVOICE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, invoice_date)],
            COMMENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, comments)],
            FILE: [MessageHandler(filters.Document.ALL, handle_file)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(CommandHandler('start', start))
    application.add_handler(conv_handler)

    logging.info("Бот запущен, ожидает сообщений")
    application.run_polling()

if __name__ == '__main__':
    main()
