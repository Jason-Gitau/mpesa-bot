#  import the modules we need
from telegram import Update,InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, Application,CallbackContext, MessageHandler,filters,CallbackQueryHandler, ContextTypes
import requests


# set the bot token
bot_token = "7805514118:AAHjxdGzS6t5Whfyr7SVY1ogb-OLDHBy1tA"
chat_memory = {}


# M-Pesa Configuration (Sandbox)
MPESA_CONSUMER_KEY = "HtUDPv3VclwhCX8UDHG8S17VG3cOm1cgubnup1S6cR5NTNWD"
MPESA_CONSUMER_SECRET = "xI2IXrlcjk4APmUar35Luj2eSRkIcu6SGKjDBduNR727SEAwTJChQlAgap496uHF"
MPESA_AUTH_URL = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
MPESA_STK_PUSH_URL = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"


# Generate M-Pesa Access Token
def get_mpesa_access_token():
    try:
        response = requests.get(
            MPESA_AUTH_URL,
            auth=(MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET)
        )
        response.raise_for_status()
        return response.json().get("access_token")
    except requests.RequestException as e:
        print(f"Error fetching M-Pesa access token: {e}")
        return None


# Initiate M-Pesa STK Push (Payment Request)
def initiate_stk_push(phone_number, amount):
    access_token = get_mpesa_access_token()
    if not access_token:
        return "Failed to authenticate with M-Pesa."

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "BusinessShortCode": "174379",  # Sandbox shortcode
        "Password": "MTc0Mzc5YmZiMjc5ZjlhYTliZGJjZjE1OGU5N2RkNzFhNDY3Y2QyZTBjODkzMDU5YjEwZjc4ZTZiNzJhZGExZWQyYzkxOTIwMjMwMjIxMTg1NjU0",  # Base64 encoded password
        "Timestamp": "20230221185654",  # Replace with current timestamp
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": "174379",  # Sandbox shortcode
        "PhoneNumber": phone_number,
        "CallBackURL": "https://your-callback-url.com/mpesa",  # Replace with your callback URL
        "AccountReference": "Test Payment",
        "TransactionDesc": "Payment for services"
    }

    try:
        response = requests.post(MPESA_STK_PUSH_URL, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error initiating STK push: {e}")
        return {"error": str(e)}


# /start command
async def start(update:Update,cotext:CallbackContext)->None:
    await update.message.reply_text("I am a telegram bot built with python")

# /help command
async def help_command(update:Update,context:CallbackContext)->None:
    await update.message.reply_text(
        "Here are the commands you can use:\n"
        "/start: to start the bot\n"
        "/help: to get list of commands\n"
        "/info: to get information about the bot\n"
        "/service: see what i can do!\n"
        "/pay: to initiate a payment\n"
        "/confirm: to confirm payment\n"
        "/status: to check payment status\n"

    )


# /pay command
async def pay(update: Update, context: CallbackContext) -> None:
     # Split the user's input into parts
    text = update.message.text.split()
    
    if len(text) == 3:  # User provided /pay <phone> <amount>
        _, phone, amount = text
        context.user_data["phone"] = phone
        context.user_data["amount"] = amount
        context.user_data["state"] = "payment_confirmed"

         # Create an inline keyboard with "Confirm" and "Cancel" buttons
        keyboard = [
            [InlineKeyboardButton("✅ Confirm", callback_data="confirm")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)



        await update.message.reply_text(f"Payment of {amount} to {phone} confirmed. Use /confirm to proceed.",
        reply_markup=reply_markup)
    else:
        # User only sent /pay without phone and amount
        await update.message.reply_text("Please enter your phone number and amount in the format: /pay <phone> <amount>")
        context.user_data["state"] = "awaiting_payment_details"


# /confirm command
async def confirm(update: Update, context: CallbackContext) -> None:
    phone = context.user_data.get("phone")
    amount = context.user_data.get("amount")

    if not phone or not amount:
        await update.message.reply_text("No payment details found. Please use /pay to start.")
        return
    
    elif not phone.startswith("254") or len(phone) != 12 or not phone.isdigit():
            raise ValueError("Invalid phone number. Please use the format 2547XXXXXXXX.")

    
    elif not amount.isdigit() or int(amount) <= 0:
            raise ValueError("Invalid amount. Please enter a positive number.")

    result = initiate_stk_push(phone, amount)
    if "errorCode" in result:
        await update.message.reply_text(f"Payment failed: {result.get('errorMessage')}")
    else:
        await update.message.reply_text("Payment request sent successfully. Please confirm on your phone.")


# /status command
async def status(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Payment status check is not implemented yet.")


# Handle Payment Details
async def handle_payment_details(update: Update, context: CallbackContext) -> None:
    if context.user_data.get("state") == "awaiting_payment_details":
        try:
            _, phone, amount = update.message.text.split()
            context.user_data["phone"] = phone
            context.user_data["amount"] = amount
            await update.message.reply_text(f"Payment of {amount} to {phone} confirmed. Use /confirm to proceed.")
            context.user_data["state"] = None
        except ValueError:
            await update.message.reply_text("Invalid format. Use /pay <phone> <amount>.")

    else:
        # Ignore messages that are not part of the payment flow
        pass


async def cancel(update: Update, context: CallbackContext) -> None:
    # Check if the bot is in a specific state
    if context.user_data.get("state") in ["awaiting_payment_details", "payment_confirmed"]:
        # Reset the state
        context.user_data.clear()
        await update.message.reply_text("Payment process canceled. You can start over with /pay.")
    else:
        # If no state is active, inform the user
        await update.message.reply_text("Nothing to cancel. Use /pay to start a new payment.")


async def button_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()  # Acknowledge the button press
    
    if query.data == "confirm":
        # Retrieve phone and amount from user data
        phone = context.user_data.get("phone")
        amount = context.user_data.get("amount")
        
        if not phone or not amount:
            await query.edit_message_text("No payment details found. Please use /pay to start.")
            return
        
        # Initiate M-Pesa payment
        result = initiate_stk_push(phone, amount)
        if "errorCode" in result:
            await query.edit_message_text(f"Payment failed: {result.get('errorMessage')}")
        else:
            await query.edit_message_text("Payment request sent successfully. Please confirm on your phone.")
    elif query.data == "cancel":
        # Clear user data and notify the user
        context.user_data.clear()
        await query.edit_message_text("Payment process canceled. You can start over with /pay.")


# /info command
async def info_command(update:Update,context:CallbackContext)->None:
    await update.message.reply_text("I am a Telegram automation bot built using Python! 🚀")

    
# /service command
async def service_command(update:Update,context:CallbackContext)->None:
    await update.message.reply_text("I can send messages, automate tasks, and more! 🤖"
                                    
)



# handle any messages
async def echo(update:Update,context:CallbackContext)->None:
    user_message=update.message.text.lower()
    user_id = update.message.chat_id

    if user_id not in chat_memory:
        chat_memory[user_id]=[]

    chat_memory[user_id].append(user_message)

    if user_message=="hi":
        await update.message.reply_text("Hello!")
    elif user_message=="how are you":
        await update.message.reply_text("I'm good, thank you!")
    elif user_message=="bye":
        await update.message.reply_text("Goodbye!")

    elif user_message == "tell me what i said before":
        await update.message.reply_text(f"Your past messages: {', '.join(chat_memory[user_id])}")

    else:
        await update.message.reply_text("I don't understand that command. Please use /help to see the list of commands.")



   





def main():
    application=Application.builder().token(bot_token).build()

    # add command handler
    application.add_handler(CommandHandler("start",start))
    application.add_handler(CommandHandler("help",help_command))
    application.add_handler(CommandHandler("info",info_command))
    application.add_handler(CommandHandler("service",service_command))
    application.add_handler(CommandHandler("pay", pay))  
    application.add_handler(CommandHandler("confirm", confirm)) 
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("cancel", cancel))

    # add message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,echo))

     # Add callback query handler for button presses
    application.add_handler(CallbackQueryHandler(button_callback))

    # start the bot
    application.run_polling()

if __name__ == '__main__':
    main()
