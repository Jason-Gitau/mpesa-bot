"""
Telegram Bot Command Handlers for M-Pesa Payment Bot

This module contains all command handlers and callback query handlers
for the Telegram bot, including payment processing, transaction history,
and admin functionality.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from decimal import Decimal

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackContext
from telegram.constants import ParseMode

# Import from project modules (to be created)
try:
    from config import (
        ADMIN_USER_IDS,
        MAX_PAYMENT_AMOUNT,
        MIN_PAYMENT_AMOUNT,
        RATE_LIMIT_SECONDS,
        TRANSACTIONS_HISTORY_LIMIT
    )
    from utils import (
        validate_phone_number,
        validate_amount,
        format_currency,
        format_datetime,
        sanitize_input
    )
    from database import (
        save_transaction,
        get_user_transactions,
        get_transaction_by_id,
        get_all_recent_transactions,
        get_statistics
    )
    from mpesa_service import (
        initiate_stk_push,
        check_transaction_status,
        MpesaError
    )
except ImportError as e:
    logging.warning(f"Import error: {e}. Some modules may not be available yet.")
    # Provide fallback values for development
    ADMIN_USER_IDS = []
    MAX_PAYMENT_AMOUNT = 150000
    MIN_PAYMENT_AMOUNT = 1
    RATE_LIMIT_SECONDS = 3
    TRANSACTIONS_HISTORY_LIMIT = 10


# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# Rate limiting decorator
def rate_limit(func):
    """Decorator to implement rate limiting for commands."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        current_time = datetime.now()

        # Initialize rate limit data if not exists
        if 'rate_limit' not in context.user_data:
            context.user_data['rate_limit'] = {}

        last_request_time = context.user_data['rate_limit'].get(func.__name__)

        if last_request_time:
            time_diff = (current_time - last_request_time).total_seconds()
            if time_diff < RATE_LIMIT_SECONDS:
                await update.message.reply_text(
                    f"⏳ Please wait {int(RATE_LIMIT_SECONDS - time_diff)} seconds before using this command again."
                )
                return

        # Update last request time
        context.user_data['rate_limit'][func.__name__] = current_time

        return await func(update, context, *args, **kwargs)

    return wrapper


def admin_only(func):
    """Decorator to restrict command access to admins only."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id

        if user_id not in ADMIN_USER_IDS:
            await update.message.reply_text(
                "🚫 <b>Access Denied</b>\n\n"
                "This command is only available to administrators.",
                parse_mode=ParseMode.HTML
            )
            logger.warning(f"Unauthorized admin access attempt by user {user_id}")
            return

        return await func(update, context, *args, **kwargs)

    return wrapper


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /start command - Welcome message with bot capabilities.

    Args:
        update: Telegram update object
        context: Callback context
    """
    user = update.effective_user

    welcome_message = (
        f"👋 <b>Welcome {user.first_name}!</b>\n\n"
        "🤖 <b>M-Pesa Payment Bot</b>\n\n"
        "I can help you with:\n"
        "💰 Making M-Pesa payments\n"
        "📊 Tracking transaction history\n"
        "🔍 Checking payment status\n\n"
        "Use /help to see all available commands.\n\n"
        "Let's get started! 🚀"
    )

    await update.message.reply_text(
        welcome_message,
        parse_mode=ParseMode.HTML
    )

    # Initialize user data
    context.user_data['state'] = None
    context.user_data['pending_payment'] = None

    logger.info(f"User {user.id} ({user.username}) started the bot")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /help command - Detailed help with all commands.

    Args:
        update: Telegram update object
        context: Callback context
    """
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_USER_IDS

    help_text = (
        "📚 <b>Available Commands</b>\n\n"

        "<b>💳 Payment Commands:</b>\n"
        "/pay &lt;amount&gt; &lt;phone&gt; - Initiate a payment\n"
        "   <i>Example: /pay 100 254712345678</i>\n\n"

        "/confirm - Confirm pending payment\n"
        "/cancel - Cancel pending payment\n\n"

        "<b>📊 Transaction Commands:</b>\n"
        "/history - View your last 10 transactions\n"
        "/status &lt;transaction_id&gt; - Check transaction status\n"
        "   <i>Example: /status TXN123456</i>\n\n"

        "<b>ℹ️ General Commands:</b>\n"
        "/start - Restart the bot\n"
        "/help - Show this help message\n\n"
    )

    if is_admin:
        help_text += (
            "<b>👨‍💼 Admin Commands:</b>\n"
            "/admin_stats - View system statistics\n"
            "/admin_transactions - View all recent transactions\n\n"
        )

    help_text += (
        "<b>💡 Tips:</b>\n"
        "• Phone numbers must be in format: 254XXXXXXXXX\n"
        f"• Minimum amount: KES {MIN_PAYMENT_AMOUNT}\n"
        f"• Maximum amount: KES {format_currency(MAX_PAYMENT_AMOUNT)}\n"
        "• All payments require confirmation\n\n"
        "Need assistance? Contact support."
    )

    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.HTML
    )


@rate_limit
async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /pay command - Initiate payment with inline confirmation buttons.

    Usage: /pay <amount> <phone>
    Example: /pay 100 254712345678

    Args:
        update: Telegram update object
        context: Callback context
    """
    user = update.effective_user

    try:
        # Check if user has pending payment
        if context.user_data.get('pending_payment'):
            await update.message.reply_text(
                "⚠️ You have a pending payment.\n"
                "Please /confirm or /cancel it first."
            )
            return

        # Parse arguments
        if len(context.args) != 2:
            await update.message.reply_text(
                "❌ <b>Invalid Format</b>\n\n"
                "Usage: /pay &lt;amount&gt; &lt;phone&gt;\n"
                "Example: /pay 100 254712345678\n\n"
                "• Amount: Number between 1 and 150,000\n"
                "• Phone: Kenyan number (254XXXXXXXXX)",
                parse_mode=ParseMode.HTML
            )
            return

        amount_str = sanitize_input(context.args[0])
        phone = sanitize_input(context.args[1])

        # Validate amount
        try:
            amount = validate_amount(amount_str)

            if amount < MIN_PAYMENT_AMOUNT or amount > MAX_PAYMENT_AMOUNT:
                await update.message.reply_text(
                    f"❌ <b>Invalid Amount</b>\n\n"
                    f"Amount must be between KES {MIN_PAYMENT_AMOUNT} "
                    f"and KES {format_currency(MAX_PAYMENT_AMOUNT)}",
                    parse_mode=ParseMode.HTML
                )
                return
        except ValueError as e:
            await update.message.reply_text(
                f"❌ <b>Invalid Amount</b>\n\n{str(e)}",
                parse_mode=ParseMode.HTML
            )
            return

        # Validate phone number
        try:
            phone = validate_phone_number(phone)
        except ValueError as e:
            await update.message.reply_text(
                f"❌ <b>Invalid Phone Number</b>\n\n{str(e)}",
                parse_mode=ParseMode.HTML
            )
            return

        # Store pending payment details
        context.user_data['pending_payment'] = {
            'amount': amount,
            'phone': phone,
            'created_at': datetime.now(),
            'user_id': user.id,
            'username': user.username or user.first_name
        }
        context.user_data['state'] = 'payment_pending'

        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm Payment", callback_data="confirm_payment"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        confirmation_message = (
            "💳 <b>Payment Confirmation</b>\n\n"
            f"<b>Amount:</b> KES {format_currency(amount)}\n"
            f"<b>Phone Number:</b> {phone}\n"
            f"<b>Initiated by:</b> {user.first_name}\n\n"
            "⚠️ Please confirm the details are correct.\n"
            "You will receive a payment prompt on your phone."
        )

        await update.message.reply_text(
            confirmation_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Payment initiated: User {user.id}, Amount: {amount}, Phone: {phone}")

    except Exception as e:
        logger.error(f"Error in pay command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>Error</b>\n\n"
            "An unexpected error occurred. Please try again later.",
            parse_mode=ParseMode.HTML
        )


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /confirm command - Confirm pending payment.

    Args:
        update: Telegram update object
        context: Callback context
    """
    user = update.effective_user

    try:
        # Check if there's a pending payment
        pending_payment = context.user_data.get('pending_payment')

        if not pending_payment:
            await update.message.reply_text(
                "⚠️ <b>No Pending Payment</b>\n\n"
                "Use /pay &lt;amount&gt; &lt;phone&gt; to initiate a payment.",
                parse_mode=ParseMode.HTML
            )
            return

        # Check if payment hasn't expired (5 minutes timeout)
        created_at = pending_payment['created_at']
        if datetime.now() - created_at > timedelta(minutes=5):
            context.user_data['pending_payment'] = None
            context.user_data['state'] = None
            await update.message.reply_text(
                "⏱️ <b>Payment Expired</b>\n\n"
                "Your payment request has expired.\n"
                "Please initiate a new payment with /pay",
                parse_mode=ParseMode.HTML
            )
            return

        # Send processing message
        processing_msg = await update.message.reply_text(
            "⏳ <b>Processing Payment...</b>\n\n"
            "Please wait while we process your request.",
            parse_mode=ParseMode.HTML
        )

        # Process the payment
        amount = pending_payment['amount']
        phone = pending_payment['phone']

        try:
            result = await initiate_stk_push(phone, amount, user.id)

            # Save transaction to database
            transaction_id = result.get('CheckoutRequestID', 'UNKNOWN')
            await save_transaction(
                transaction_id=transaction_id,
                user_id=user.id,
                username=pending_payment['username'],
                phone=phone,
                amount=amount,
                status='pending',
                timestamp=datetime.now()
            )

            # Clear pending payment
            context.user_data['pending_payment'] = None
            context.user_data['state'] = None

            # Update message
            await processing_msg.edit_text(
                "✅ <b>Payment Request Sent!</b>\n\n"
                f"<b>Transaction ID:</b> <code>{transaction_id}</code>\n"
                f"<b>Amount:</b> KES {format_currency(amount)}\n"
                f"<b>Phone:</b> {phone}\n\n"
                "📱 Please check your phone and enter your M-Pesa PIN.\n\n"
                f"Use /status {transaction_id} to check payment status.",
                parse_mode=ParseMode.HTML
            )

            logger.info(f"Payment confirmed: User {user.id}, Transaction: {transaction_id}")

        except MpesaError as e:
            await processing_msg.edit_text(
                "❌ <b>Payment Failed</b>\n\n"
                f"Error: {str(e)}\n\n"
                "Please try again or contact support.",
                parse_mode=ParseMode.HTML
            )
            logger.error(f"M-Pesa error for user {user.id}: {e}")

    except Exception as e:
        logger.error(f"Error in confirm command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>Error</b>\n\n"
            "An unexpected error occurred. Please try again.",
            parse_mode=ParseMode.HTML
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /cancel command - Cancel pending payment.

    Args:
        update: Telegram update object
        context: Callback context
    """
    user = update.effective_user

    if not context.user_data.get('pending_payment'):
        await update.message.reply_text(
            "ℹ️ <b>No Pending Payment</b>\n\n"
            "You don't have any pending payments to cancel.",
            parse_mode=ParseMode.HTML
        )
        return

    # Clear pending payment
    context.user_data['pending_payment'] = None
    context.user_data['state'] = None

    await update.message.reply_text(
        "✅ <b>Payment Cancelled</b>\n\n"
        "Your pending payment has been cancelled.\n"
        "Use /pay to initiate a new payment.",
        parse_mode=ParseMode.HTML
    )

    logger.info(f"Payment cancelled by user {user.id}")


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /history command - View transaction history (last 10).

    Args:
        update: Telegram update object
        context: Callback context
    """
    user = update.effective_user

    try:
        # Fetch user's transaction history
        transactions = await get_user_transactions(
            user.id,
            limit=TRANSACTIONS_HISTORY_LIMIT
        )

        if not transactions:
            await update.message.reply_text(
                "📭 <b>No Transaction History</b>\n\n"
                "You haven't made any transactions yet.\n"
                "Use /pay to initiate your first payment!",
                parse_mode=ParseMode.HTML
            )
            return

        # Format transaction history
        history_text = f"📊 <b>Transaction History</b>\n\n"
        history_text += f"Showing last {len(transactions)} transaction(s):\n\n"

        for i, txn in enumerate(transactions, 1):
            status_emoji = {
                'completed': '✅',
                'pending': '⏳',
                'failed': '❌',
                'cancelled': '🚫'
            }.get(txn['status'], '❓')

            history_text += (
                f"<b>{i}. {status_emoji} {txn['status'].upper()}</b>\n"
                f"   ID: <code>{txn['transaction_id']}</code>\n"
                f"   Amount: KES {format_currency(txn['amount'])}\n"
                f"   Phone: {txn['phone']}\n"
                f"   Date: {format_datetime(txn['timestamp'])}\n\n"
            )

        history_text += "Use /status &lt;transaction_id&gt; for details."

        await update.message.reply_text(
            history_text,
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Transaction history viewed by user {user.id}")

    except Exception as e:
        logger.error(f"Error in history command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>Error</b>\n\n"
            "Could not retrieve transaction history.\n"
            "Please try again later.",
            parse_mode=ParseMode.HTML
        )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /status command - Check specific transaction status.

    Usage: /status <transaction_id>

    Args:
        update: Telegram update object
        context: Callback context
    """
    user = update.effective_user

    try:
        # Validate arguments
        if len(context.args) != 1:
            await update.message.reply_text(
                "❌ <b>Invalid Format</b>\n\n"
                "Usage: /status &lt;transaction_id&gt;\n"
                "Example: /status ws_CO_12345678",
                parse_mode=ParseMode.HTML
            )
            return

        transaction_id = sanitize_input(context.args[0])

        # Send checking message
        checking_msg = await update.message.reply_text(
            "🔍 <b>Checking Status...</b>",
            parse_mode=ParseMode.HTML
        )

        # Fetch transaction from database
        transaction = await get_transaction_by_id(transaction_id, user.id)

        if not transaction:
            await checking_msg.edit_text(
                "❌ <b>Transaction Not Found</b>\n\n"
                f"Transaction ID: <code>{transaction_id}</code>\n\n"
                "Please check the ID and try again.",
                parse_mode=ParseMode.HTML
            )
            return

        # Get live status from M-Pesa if pending
        if transaction['status'] == 'pending':
            try:
                live_status = await check_transaction_status(transaction_id)
                # Update status if changed
                if live_status != transaction['status']:
                    transaction['status'] = live_status
            except Exception as e:
                logger.warning(f"Could not fetch live status: {e}")

        # Format status message
        status_emoji = {
            'completed': '✅',
            'pending': '⏳',
            'failed': '❌',
            'cancelled': '🚫'
        }.get(transaction['status'], '❓')

        status_text = (
            f"📋 <b>Transaction Status</b>\n\n"
            f"<b>Status:</b> {status_emoji} {transaction['status'].upper()}\n"
            f"<b>Transaction ID:</b> <code>{transaction['transaction_id']}</code>\n"
            f"<b>Amount:</b> KES {format_currency(transaction['amount'])}\n"
            f"<b>Phone:</b> {transaction['phone']}\n"
            f"<b>Date:</b> {format_datetime(transaction['timestamp'])}\n"
        )

        if transaction.get('mpesa_receipt'):
            status_text += f"<b>M-Pesa Receipt:</b> {transaction['mpesa_receipt']}\n"

        if transaction['status'] == 'pending':
            status_text += "\n⏳ Payment is still pending. Check again shortly."
        elif transaction['status'] == 'completed':
            status_text += "\n✅ Payment completed successfully!"
        elif transaction['status'] == 'failed':
            status_text += f"\n❌ Payment failed: {transaction.get('error_message', 'Unknown error')}"

        await checking_msg.edit_text(status_text, parse_mode=ParseMode.HTML)

        logger.info(f"Status checked: User {user.id}, Transaction {transaction_id}")

    except Exception as e:
        logger.error(f"Error in status command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>Error</b>\n\n"
            "Could not retrieve transaction status.\n"
            "Please try again later.",
            parse_mode=ParseMode.HTML
        )


@admin_only
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /admin_stats command - Show system statistics (Admin only).

    Args:
        update: Telegram update object
        context: Callback context
    """
    try:
        # Fetch statistics
        stats = await get_statistics()

        stats_text = (
            "📊 <b>System Statistics</b>\n\n"

            "<b>📈 Overall:</b>\n"
            f"Total Transactions: {stats['total_transactions']}\n"
            f"Total Users: {stats['total_users']}\n"
            f"Total Volume: KES {format_currency(stats['total_volume'])}\n\n"

            "<b>✅ Completed:</b>\n"
            f"Count: {stats['completed_count']}\n"
            f"Volume: KES {format_currency(stats['completed_volume'])}\n\n"

            "<b>⏳ Pending:</b>\n"
            f"Count: {stats['pending_count']}\n"
            f"Volume: KES {format_currency(stats['pending_volume'])}\n\n"

            "<b>❌ Failed:</b>\n"
            f"Count: {stats['failed_count']}\n"
            f"Volume: KES {format_currency(stats['failed_volume'])}\n\n"

            "<b>📅 Today:</b>\n"
            f"Transactions: {stats['today_count']}\n"
            f"Volume: KES {format_currency(stats['today_volume'])}\n\n"

            f"<b>Success Rate:</b> {stats['success_rate']:.1f}%\n"
            f"<b>Last Updated:</b> {format_datetime(datetime.now())}"
        )

        await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)

        logger.info(f"Admin stats viewed by user {update.effective_user.id}")

    except Exception as e:
        logger.error(f"Error in admin_stats command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>Error</b>\n\n"
            "Could not retrieve statistics.\n"
            "Please try again later.",
            parse_mode=ParseMode.HTML
        )


@admin_only
async def admin_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /admin_transactions command - View all recent transactions (Admin only).

    Args:
        update: Telegram update object
        context: Callback context
    """
    try:
        # Fetch recent transactions
        limit = 20
        transactions = await get_all_recent_transactions(limit)

        if not transactions:
            await update.message.reply_text(
                "📭 <b>No Transactions</b>\n\n"
                "No transactions found in the system.",
                parse_mode=ParseMode.HTML
            )
            return

        transactions_text = (
            f"📊 <b>Recent Transactions</b>\n\n"
            f"Showing last {len(transactions)} transaction(s):\n\n"
        )

        for i, txn in enumerate(transactions, 1):
            status_emoji = {
                'completed': '✅',
                'pending': '⏳',
                'failed': '❌',
                'cancelled': '🚫'
            }.get(txn['status'], '❓')

            transactions_text += (
                f"<b>{i}. {status_emoji} {txn['status'].upper()}</b>\n"
                f"   User: {txn['username']} (ID: {txn['user_id']})\n"
                f"   Amount: KES {format_currency(txn['amount'])}\n"
                f"   Phone: {txn['phone']}\n"
                f"   Date: {format_datetime(txn['timestamp'])}\n"
                f"   TXN: <code>{txn['transaction_id']}</code>\n\n"
            )

        await update.message.reply_text(
            transactions_text,
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Admin transactions viewed by user {update.effective_user.id}")

    except Exception as e:
        logger.error(f"Error in admin_transactions command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>Error</b>\n\n"
            "Could not retrieve transactions.\n"
            "Please try again later.",
            parse_mode=ParseMode.HTML
        )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle callback queries from inline keyboard buttons.

    Args:
        update: Telegram update object
        context: Callback context
    """
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    try:
        if query.data == "confirm_payment":
            # Check if there's a pending payment
            pending_payment = context.user_data.get('pending_payment')

            if not pending_payment:
                await query.edit_message_text(
                    "⚠️ <b>Payment Expired</b>\n\n"
                    "This payment request has expired.\n"
                    "Please use /pay to initiate a new payment.",
                    parse_mode=ParseMode.HTML
                )
                return

            # Update message to processing
            await query.edit_message_text(
                "⏳ <b>Processing Payment...</b>\n\n"
                "Please wait while we process your request.",
                parse_mode=ParseMode.HTML
            )

            # Process the payment
            amount = pending_payment['amount']
            phone = pending_payment['phone']

            try:
                result = await initiate_stk_push(phone, amount, user.id)

                # Save transaction to database
                transaction_id = result.get('CheckoutRequestID', 'UNKNOWN')
                await save_transaction(
                    transaction_id=transaction_id,
                    user_id=user.id,
                    username=pending_payment['username'],
                    phone=phone,
                    amount=amount,
                    status='pending',
                    timestamp=datetime.now()
                )

                # Clear pending payment
                context.user_data['pending_payment'] = None
                context.user_data['state'] = None

                # Update message
                await query.edit_message_text(
                    "✅ <b>Payment Request Sent!</b>\n\n"
                    f"<b>Transaction ID:</b> <code>{transaction_id}</code>\n"
                    f"<b>Amount:</b> KES {format_currency(amount)}\n"
                    f"<b>Phone:</b> {phone}\n\n"
                    "📱 Please check your phone and enter your M-Pesa PIN.\n\n"
                    f"Use /status {transaction_id} to check payment status.",
                    parse_mode=ParseMode.HTML
                )

                logger.info(f"Payment confirmed via button: User {user.id}, Transaction: {transaction_id}")

            except MpesaError as e:
                await query.edit_message_text(
                    "❌ <b>Payment Failed</b>\n\n"
                    f"Error: {str(e)}\n\n"
                    "Please try again or contact support.",
                    parse_mode=ParseMode.HTML
                )
                logger.error(f"M-Pesa error for user {user.id}: {e}")

        elif query.data == "cancel_payment":
            # Clear pending payment
            context.user_data['pending_payment'] = None
            context.user_data['state'] = None

            await query.edit_message_text(
                "✅ <b>Payment Cancelled</b>\n\n"
                "Your payment has been cancelled.\n"
                "Use /pay to initiate a new payment.",
                parse_mode=ParseMode.HTML
            )

            logger.info(f"Payment cancelled via button: User {user.id}")

    except Exception as e:
        logger.error(f"Error in button callback: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ <b>Error</b>\n\n"
            "An unexpected error occurred.\n"
            "Please try again later.",
            parse_mode=ParseMode.HTML
        )


# Export all handlers
__all__ = [
    'start',
    'help_command',
    'pay',
    'confirm',
    'cancel',
    'history',
    'status',
    'admin_stats',
    'admin_transactions',
    'button_callback'
]
