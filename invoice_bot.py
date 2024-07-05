import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.mime.text import MIMEText

# Вставьте ваши учетные данные
API_TOKEN = '7399678662:AAGhvtbvC0ovTuLtj12bN5nJFDiKJfNH9qA'
GEN_DIR_ID = 593169165  # ID гендиректора в Telegram
EMAIL_USER = 'madi.turysbek.00@mail.ru'
EMAIL_PASSWORD = 'ykmVMzhVih9Jz3YbpE7d'
EMAIL_RECEIVER = 'zhanaurpak2021@gmail.com'
SMTP_SERVER = 'smtp.mail.ru'
SMTP_PORT = 587

# Включение логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levellevel)s - %(message)s',
    level=logging.INFO
)

# Состояния разговора
(
    INVOICE_AMOUNT,
    INVOICE_DATE,
    COMMENTS,
    FILE,
    WAIT_CONFIRMATION,
) = range(5)

async def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id == GEN_DIR_ID:
        await update.message.reply_text('Здравствуйте! Вы можете только согласовывать счета.')
    else:
        await update.message.reply_text('Здравствуйте! Пожалуйста, загрузите счет для согласования.')
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
    await update.message.reply_text('Пожалуйста, загрузите файл счета в формате Excel.')
    return FILE

async def handle_file(update: Update, context: CallbackContext):
    document = update.message.document

    logging.info(f"Получен файл: {document.file_name}")

    # Проверяем MIME-тип документа
    mime_type = document.mime_type if document.mime_type else document.get_file().mime_type
    logging.info(f"MIME-тип файла: {mime_type}")
    valid_mime_types = [
        'application/vnd.ms-excel', 
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    ]
    
    if mime_type not in valid_mime_types:
        await update.message.reply_text('Пожалуйста, загрузите файл в формате Excel.')
        return FILE

    file = await document.get_file()
    file_name = document.file_name if document.file_name else f"file_{document.file_id}.xlsx"
    file_path = f'invoice_{file_name}'
    await file.download_to_drive(file_path)  # Сохраняем файл
    logging.info(f"Файл сохранен: {file_path}")

    context.user_data['file_path'] = file_path
    context.user_data['file_name'] = file_name

    # Отправляем сообщение гендиректору на согласование
    await send_confirmation_request(update, context)
    return ConversationHandler.END

async def send_confirmation_request(update: Update, context: CallbackContext):
    message = (
        f"Новый счет на согласование:\n\n"
        f"Сумма счета: {context.user_data['invoice_amount']}\n"
        f"Дата счета: {context.user_data['invoice_date']}\n"
        f"Комментарии: {context.user_data['comments']}\n\n"
        "Пожалуйста, подтвердите или отклоните, отправив '+' или '-'."
    )
    
    try:
        logging.info(f"Отправляем документ на согласование гендиректору. ID: {GEN_DIR_ID}, Файл: {context.user_data['file_path']}")
        await context.bot.send_document(
            chat_id=GEN_DIR_ID,
            document=open(context.user_data['file_path'], 'rb'),
            caption=message
        )
        logging.info("Сообщение отправлено гендиректору на согласование.")
    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения гендиректору: {e}")

async def confirm_invoice(update: Update, context: CallbackContext):
    logging.info("Получено подтверждение счета.")
    await update.message.reply_text("Счет согласован. Отправляем на почту.")
    # Отправляем файл на email
    send_email(context.user_data['file_path'], context.user_data['file_name'], context.user_data)
    await context.bot.send_message(chat_id=GEN_DIR_ID, text="Счет отправлен на почту.")
    return ConversationHandler.END

async def reject_invoice(update: Update, context: CallbackContext):
    logging.info("Получено отклонение счета.")
    await update.message.reply_text("Счет отклонен.")
    await context.bot.send_message(chat_id=GEN_DIR_ID, text="Счет отклонен.")
    return ConversationHandler.END

def send_email(file_path, file_name, user_data):
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
            part = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{file_name}"')
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
        entry_points=[CommandHandler('start', start)],
        states={
            INVOICE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, invoice_amount)],
            INVOICE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, invoice_date)],
            COMMENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, comments)],
            FILE: [MessageHandler(filters.Document.ALL, handle_file)],
            WAIT_CONFIRMATION: [
                MessageHandler(filters.Regex(r'\+'), confirm_invoice),
                MessageHandler(filters.Regex(r'-'), reject_invoice)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)

    logging.info("Бот запущен, ожидает сообщений")
    application.run_polling()

if __name__ == '__main__':
    main()
