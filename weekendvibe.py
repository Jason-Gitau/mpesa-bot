# Telegram Bot with M-Pesa (Daraja) Integration

from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, CallbackContext
import os
from daraja import Mpesa
import asyncio
from datetime import datetime
import aiomysql
from fastapi import FastAPI, Request
import httpx

# Load environment variables
CONSUMER_KEY = os.getenv('MPESA_CONSUMER_KEY')
CONSUMER_SECRET = os.getenv('MPESA_CONSUMER_SECRET')
SHORTCODE = os.getenv('MPESA_SHORTCODE')
PASSKEY = os.getenv('MPESA_PASSKEY')
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
SELLER_CHAT_ID = os.getenv('SELLER_CHAT_ID')
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')

# FastAPI app for callback handling
app = FastAPI()

@app.post('/mpesa-callback')
async def mpesa_callback(request: Request):
    data = await request.json()
    transaction_id = data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID', 'Unknown')
    result_code = data.get('Body', {}).get('stkCallback', {}).get('ResultCode', -1)
    buyer_name = data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {}).get('Item', [])[2].get('Value', 'Unknown')
    amount = data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {}).get('Item', [])[0].get('Value', 0)
    timestamp = datetime.now()
    status = 'Success' if result_code == 0 else 'Failed'

    await save_transaction(transaction_id, buyer_name, amount, timestamp, status, 'STK Push')

    message = f'Transaction {status}: {buyer_name} paid KES {amount} at {timestamp}' if status == 'Success' else f'Transaction failed for {buyer_name}.'
    await notify_seller(application.bot, message)
    return {'status': 'ok'}

# Initialize M-Pesa client
mpesa_client = Mpesa(CONSUMER_KEY, CONSUMER_SECRET, shortcode=SHORTCODE, passkey=PASSKEY)

# Asynchronous database connection
async def get_db_connection():
    return await aiomysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_NAME)

# Save transaction to database
async def save_transaction(transaction_id, buyer_name, amount, timestamp, status, payment_method):
    async with await get_db_connection() as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                'INSERT INTO transactions (transaction_id, buyer_name, amount, timestamp, status, payment_method) VALUES (%s, %s, %s, %s, %s, %s)',
                (transaction_id, buyer_name, amount, timestamp, status, payment_method)
            )
            await connection.commit()

# Notify Seller Function
async def notify_seller(bot: Bot, message: str) -> None:
    await bot.send_message(chat_id=SELLER_CHAT_ID, text=message)

# Start Command
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Welcome to the Payment Bot! Use /pay <amount> <phone> to initiate payment.')

# Help Command
async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = 'Available commands:\n'
    help_text += '/start - Start the bot\n'
    help_text += '/pay <amount> <phone> - Initiate a payment\n'
    help_text += '/help - Display available commands\n'
    await update.message.reply_text(help_text)

# Pay Command
async def pay(update: Update, context: CallbackContext) -> None:
    try:
        amount = float(context.args[0])
        phone = context.args[1]
        transaction = await asyncio.to_thread(mpesa_client.stk_push, phone_number=phone, amount=amount, account_reference='12345', transaction_desc='Payment for service')
        await update.message.reply_text(f'Payment initiated! Transaction ID: {transaction}')
    except IndexError:
        await update.message.reply_text('Usage: /pay <amount> <phone>')
    except ValueError:
        await update.message.reply_text('Invalid amount')
    except Exception as e:
        await update.message.reply_text(f'Error initiating payment: {str(e)}')

# Main function
def main():
    global application
    application = Application.builder().token(BOT_TOKEN).build()
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('pay', pay))
    application.add_handler(CommandHandler('help', help_command))
    application.run_polling()

if __name__ == '__main__':
    main()

print('Bot is running...')
