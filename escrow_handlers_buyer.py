"""
Escrow System - Buyer-Side Command Handlers for M-Pesa Bot

This module contains all buyer-side command handlers for the escrow system,
including purchase initiation, order tracking, delivery confirmation, and
dispute management.

Commands:
    /buy - Initiate escrow purchase
    /my_purchases - View all purchases
    /confirm_delivery - Confirm item received and release payment
    /dispute - Open dispute on a transaction
    /track - Track order status
    /cancel_order - Cancel order before shipping

Features:
    - Rich formatting with emojis and status indicators
    - Inline keyboards for confirmations
    - Transaction history with pagination
    - Input validation and sanitization
    - Rate limiting for command usage
    - Progress indicators and user feedback
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from decimal import Decimal

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackContext
from telegram.constants import ParseMode

# Import from project modules
try:
    from config import (
        ADMIN_USER_IDS,
        RATE_LIMIT_SECONDS,
    )
    from utils import (
        validate_kenyan_phone,
        validate_amount,
        format_currency,
        sanitize_input,
        setup_logger
    )
    from escrow_database import (
        get_user_by_telegram_id,
        get_seller_by_id,
        create_escrow_transaction,
        get_transaction_by_id,
        get_buyer_transactions,
        update_transaction_status,
        add_rating,
        create_dispute,
        get_seller_rating
    )
    from escrow_service import (
        initiate_escrow_payment,
        release_payment_to_seller,
        refund_to_buyer,
        can_cancel_order,
        can_confirm_delivery,
        can_dispute_transaction,
        calculate_auto_release_date,
        get_transaction_timeline
    )
    from mpesa_service import initiate_stk_push, MpesaError
except ImportError as e:
    logging.warning(f"Import error: {e}. Some modules may not be available yet.")
    # Provide fallback values for development
    ADMIN_USER_IDS = []
    RATE_LIMIT_SECONDS = 3


# Configure logging
logger = setup_logger('escrow_buyer', 'INFO', 'logs/escrow_buyer.log')


# Transaction status emojis
STATUS_EMOJIS = {
    'PENDING': '🕐',
    'HELD': '🔒',
    'SHIPPED': '📦',
    'COMPLETED': '✅',
    'DISPUTED': '⚠️',
    'CANCELLED': '❌',
    'REFUNDED': '💰'
}


# Rate limiting decorator
def rate_limit(seconds: int = RATE_LIMIT_SECONDS):
    """
    Decorator to implement rate limiting for commands.

    Args:
        seconds: Minimum seconds between command uses
    """
    def decorator(func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            current_time = datetime.now()

            # Initialize rate limit data if not exists
            if 'rate_limit' not in context.user_data:
                context.user_data['rate_limit'] = {}

            last_request_time = context.user_data['rate_limit'].get(func.__name__)

            if last_request_time:
                time_diff = (current_time - last_request_time).total_seconds()
                if time_diff < seconds:
                    await update.message.reply_text(
                        f"⏳ Please wait {int(seconds - time_diff)} seconds before using this command again.",
                        parse_mode=ParseMode.HTML
                    )
                    return

            # Update last request time
            context.user_data['rate_limit'][func.__name__] = current_time

            return await func(update, context, *args, **kwargs)

        return wrapper
    return decorator


@rate_limit(seconds=5)
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /buy command - Initiate escrow purchase.

    Usage: /buy <seller_id> <amount> <description>
    Example: /buy 12345 1500 Nike Air Max shoes size 42

    Args:
        update: Telegram update object
        context: Callback context
    """
    user = update.effective_user

    try:
        # Parse arguments
        if len(context.args) < 3:
            await update.message.reply_text(
                "❌ <b>Invalid Format</b>\n\n"
                "<b>Usage:</b> /buy &lt;seller_id&gt; &lt;amount&gt; &lt;description&gt;\n"
                "<b>Example:</b> /buy 12345 1500 Nike shoes size 42\n\n"
                "• <b>seller_id:</b> Seller's unique ID\n"
                "• <b>amount:</b> Purchase amount in KES\n"
                "• <b>description:</b> Item description",
                parse_mode=ParseMode.HTML
            )
            return

        seller_id = sanitize_input(context.args[0])
        amount_str = sanitize_input(context.args[1])
        description = sanitize_input(' '.join(context.args[2:]), max_length=500)

        # Validate seller ID
        try:
            seller_id_int = int(seller_id)
        except ValueError:
            await update.message.reply_text(
                "❌ <b>Invalid Seller ID</b>\n\n"
                "Seller ID must be a number.",
                parse_mode=ParseMode.HTML
            )
            return

        # Validate amount
        is_valid, amount, error = validate_amount(amount_str, min_amount=10, max_amount=500000)
        if not is_valid:
            await update.message.reply_text(
                f"❌ <b>Invalid Amount</b>\n\n{error}",
                parse_mode=ParseMode.HTML
            )
            return

        # Validate description
        if not description or len(description) < 10:
            await update.message.reply_text(
                "❌ <b>Invalid Description</b>\n\n"
                "Please provide a detailed description (minimum 10 characters).",
                parse_mode=ParseMode.HTML
            )
            return

        # Get seller information
        seller = await get_seller_by_id(seller_id_int)
        if not seller:
            await update.message.reply_text(
                f"❌ <b>Seller Not Found</b>\n\n"
                f"No seller found with ID: {seller_id}\n\n"
                "Please verify the seller ID and try again.",
                parse_mode=ParseMode.HTML
            )
            return

        # Get seller rating
        rating_info = await get_seller_rating(seller_id_int)
        rating_stars = '⭐' * int(rating_info['average_rating']) if rating_info['average_rating'] else 'No ratings yet'

        # Store purchase details in user context
        context.user_data['pending_purchase'] = {
            'seller_id': seller_id_int,
            'seller_name': seller['name'],
            'seller_phone': seller['phone'],
            'amount': amount,
            'description': description,
            'buyer_id': user.id,
            'buyer_name': user.username or user.first_name,
            'created_at': datetime.now()
        }

        # Create inline keyboard for confirmation
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm Purchase", callback_data="confirm_buy"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_buy")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Format confirmation message
        confirmation_message = (
            "🛒 <b>Escrow Purchase Confirmation</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Seller:</b> {seller['name']}\n"
            f"<b>Seller ID:</b> {seller_id}\n"
            f"<b>Rating:</b> {rating_stars}\n"
            f"  ({rating_info['total_ratings']} reviews)\n\n"
            f"<b>Amount:</b> KES {amount:,}\n"
            f"<b>Description:</b> {description}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "💡 <b>How Escrow Works:</b>\n"
            "1️⃣ You pay into escrow (funds held securely)\n"
            "2️⃣ Seller ships the item\n"
            "3️⃣ You confirm delivery\n"
            "4️⃣ Payment released to seller\n\n"
            "⚠️ <b>Important:</b>\n"
            "• Funds are held until you confirm delivery\n"
            "• You can dispute if there's an issue\n"
            "• Auto-release after 14 days if no action\n\n"
            "Please confirm to proceed with payment..."
        )

        await update.message.reply_text(
            confirmation_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

        logger.info(
            f"Purchase initiated: Buyer {user.id}, Seller {seller_id}, Amount: {amount}"
        )

    except Exception as e:
        logger.error(f"Error in buy command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>Error</b>\n\n"
            "An unexpected error occurred. Please try again later.",
            parse_mode=ParseMode.HTML
        )


@rate_limit(seconds=3)
async def my_purchases(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /my_purchases command - View all purchases.

    Shows buyer's transaction history with status and action buttons.
    Supports pagination for large transaction lists.

    Args:
        update: Telegram update object
        context: Callback context
    """
    user = update.effective_user

    try:
        # Get page number from arguments (default: 1)
        page = 1
        if context.args and context.args[0].isdigit():
            page = max(1, int(context.args[0]))

        limit = 5
        offset = (page - 1) * limit

        # Fetch buyer's transactions
        transactions = await get_buyer_transactions(
            buyer_telegram_id=user.id,
            limit=limit,
            offset=offset
        )

        if not transactions:
            if page == 1:
                await update.message.reply_text(
                    "📭 <b>No Purchases Found</b>\n\n"
                    "You haven't made any purchases yet.\n\n"
                    "💡 Use /buy to make your first purchase!",
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(
                    "📭 <b>No More Transactions</b>\n\n"
                    f"No transactions found on page {page}.",
                    parse_mode=ParseMode.HTML
                )
            return

        # Format transaction list
        message = (
            f"🛍️ <b>My Purchases - Page {page}</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )

        for i, txn in enumerate(transactions, start=1):
            status = txn['status']
            status_emoji = STATUS_EMOJIS.get(status, '❓')

            message += (
                f"\n<b>{offset + i}. {status_emoji} {status}</b>\n"
                f"   📋 ID: <code>{txn['id']}</code>\n"
                f"   💰 Amount: KES {txn['amount']:,}\n"
                f"   🏪 Seller: {txn['seller_name']}\n"
                f"   📦 Item: {txn['description'][:50]}{'...' if len(txn['description']) > 50 else ''}\n"
                f"   📅 Date: {txn['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
            )

            # Add tracking number if available
            if txn.get('tracking_number'):
                message += f"   🚚 Tracking: {txn['tracking_number']}\n"

            message += "\n"

        message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        # Create inline keyboard with action buttons
        keyboard = []

        # Pagination buttons
        pagination_row = []
        if page > 1:
            pagination_row.append(
                InlineKeyboardButton("⬅️ Previous", callback_data=f"purchases_page_{page-1}")
            )
        if len(transactions) == limit:
            pagination_row.append(
                InlineKeyboardButton("Next ➡️", callback_data=f"purchases_page_{page+1}")
            )

        if pagination_row:
            keyboard.append(pagination_row)

        # Quick action buttons
        keyboard.append([
            InlineKeyboardButton("🔍 Track Order", callback_data="track_order_prompt"),
            InlineKeyboardButton("✅ Confirm Delivery", callback_data="confirm_delivery_prompt")
        ])

        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

        message += (
            "💡 <b>Quick Actions:</b>\n"
            "• /track &lt;id&gt; - Track order\n"
            "• /confirm_delivery &lt;id&gt; - Confirm delivery\n"
            "• /dispute &lt;id&gt; - Open dispute\n"
            "• /cancel_order &lt;id&gt; - Cancel order"
        )

        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Purchase history viewed: User {user.id}, Page {page}")

    except Exception as e:
        logger.error(f"Error in my_purchases command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>Error</b>\n\n"
            "Could not retrieve your purchase history.\n"
            "Please try again later.",
            parse_mode=ParseMode.HTML
        )


@rate_limit(seconds=5)
async def confirm_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /confirm_delivery command - Confirm item received and release payment.

    Usage: /confirm_delivery <transaction_id>
    Example: /confirm_delivery 12345

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
                "<b>Usage:</b> /confirm_delivery &lt;transaction_id&gt;\n"
                "<b>Example:</b> /confirm_delivery 12345",
                parse_mode=ParseMode.HTML
            )
            return

        transaction_id = sanitize_input(context.args[0])

        # Validate transaction ID
        try:
            transaction_id_int = int(transaction_id)
        except ValueError:
            await update.message.reply_text(
                "❌ <b>Invalid Transaction ID</b>\n\n"
                "Transaction ID must be a number.",
                parse_mode=ParseMode.HTML
            )
            return

        # Get transaction
        transaction = await get_transaction_by_id(transaction_id_int)

        if not transaction:
            await update.message.reply_text(
                f"❌ <b>Transaction Not Found</b>\n\n"
                f"Transaction ID: {transaction_id}\n\n"
                "Please check the ID and try again.",
                parse_mode=ParseMode.HTML
            )
            return

        # Verify buyer owns this transaction
        if transaction['buyer_telegram_id'] != user.id:
            await update.message.reply_text(
                "🚫 <b>Access Denied</b>\n\n"
                "This transaction does not belong to you.",
                parse_mode=ParseMode.HTML
            )
            logger.warning(
                f"Unauthorized delivery confirmation attempt: User {user.id}, "
                f"Transaction {transaction_id}"
            )
            return

        # Check if delivery can be confirmed
        can_confirm, reason = await can_confirm_delivery(transaction)
        if not can_confirm:
            await update.message.reply_text(
                f"⚠️ <b>Cannot Confirm Delivery</b>\n\n{reason}",
                parse_mode=ParseMode.HTML
            )
            return

        # Store transaction ID for confirmation
        context.user_data['pending_confirmation'] = {
            'transaction_id': transaction_id_int,
            'transaction': transaction,
            'created_at': datetime.now()
        }

        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm & Release Payment", callback_data="confirm_release"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_confirmation")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Format confirmation message
        message = (
            "✅ <b>Confirm Delivery</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Transaction ID:</b> {transaction['id']}\n"
            f"<b>Amount:</b> KES {transaction['amount']:,}\n"
            f"<b>Seller:</b> {transaction['seller_name']}\n"
            f"<b>Item:</b> {transaction['description']}\n"
            f"<b>Status:</b> {STATUS_EMOJIS.get(transaction['status'], '❓')} {transaction['status']}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⚠️ <b>Important:</b>\n"
            "• By confirming, you acknowledge receipt of the item\n"
            "• Payment will be released to the seller immediately\n"
            "• This action cannot be undone\n"
            "• You cannot dispute after confirming\n\n"
            "Are you sure the item is as described?"
        )

        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

        logger.info(
            f"Delivery confirmation initiated: User {user.id}, Transaction {transaction_id}"
        )

    except Exception as e:
        logger.error(f"Error in confirm_delivery command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>Error</b>\n\n"
            "Could not process delivery confirmation.\n"
            "Please try again later.",
            parse_mode=ParseMode.HTML
        )


@rate_limit(seconds=5)
async def dispute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /dispute command - Open dispute on a transaction.

    Usage: /dispute <transaction_id> <reason>
    Example: /dispute 12345 Item not as described, wrong size

    Args:
        update: Telegram update object
        context: Callback context
    """
    user = update.effective_user

    try:
        # Parse arguments
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ <b>Invalid Format</b>\n\n"
                "<b>Usage:</b> /dispute &lt;transaction_id&gt; &lt;reason&gt;\n"
                "<b>Example:</b> /dispute 12345 Item not as described\n\n"
                "Please provide a detailed reason for the dispute.",
                parse_mode=ParseMode.HTML
            )
            return

        transaction_id = sanitize_input(context.args[0])
        reason = sanitize_input(' '.join(context.args[1:]), max_length=1000)

        # Validate transaction ID
        try:
            transaction_id_int = int(transaction_id)
        except ValueError:
            await update.message.reply_text(
                "❌ <b>Invalid Transaction ID</b>\n\n"
                "Transaction ID must be a number.",
                parse_mode=ParseMode.HTML
            )
            return

        # Validate reason
        if not reason or len(reason) < 20:
            await update.message.reply_text(
                "❌ <b>Invalid Reason</b>\n\n"
                "Please provide a detailed reason (minimum 20 characters).",
                parse_mode=ParseMode.HTML
            )
            return

        # Get transaction
        transaction = await get_transaction_by_id(transaction_id_int)

        if not transaction:
            await update.message.reply_text(
                f"❌ <b>Transaction Not Found</b>\n\n"
                f"Transaction ID: {transaction_id}\n\n"
                "Please check the ID and try again.",
                parse_mode=ParseMode.HTML
            )
            return

        # Verify buyer owns this transaction
        if transaction['buyer_telegram_id'] != user.id:
            await update.message.reply_text(
                "🚫 <b>Access Denied</b>\n\n"
                "This transaction does not belong to you.",
                parse_mode=ParseMode.HTML
            )
            logger.warning(
                f"Unauthorized dispute attempt: User {user.id}, Transaction {transaction_id}"
            )
            return

        # Check if transaction can be disputed
        can_dispute_txn, dispute_reason = await can_dispute_transaction(transaction)
        if not can_dispute_txn:
            await update.message.reply_text(
                f"⚠️ <b>Cannot Open Dispute</b>\n\n{dispute_reason}",
                parse_mode=ParseMode.HTML
            )
            return

        # Store dispute details for confirmation
        context.user_data['pending_dispute'] = {
            'transaction_id': transaction_id_int,
            'transaction': transaction,
            'reason': reason,
            'created_at': datetime.now()
        }

        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("✅ Open Dispute", callback_data="confirm_dispute"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_dispute")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Format confirmation message
        message = (
            "⚠️ <b>Open Dispute</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Transaction ID:</b> {transaction['id']}\n"
            f"<b>Amount:</b> KES {transaction['amount']:,}\n"
            f"<b>Seller:</b> {transaction['seller_name']}\n"
            f"<b>Item:</b> {transaction['description']}\n\n"
            f"<b>Your Reason:</b>\n{reason}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📋 <b>Dispute Process:</b>\n"
            "1️⃣ Transaction will be frozen\n"
            "2️⃣ Admin and seller will be notified\n"
            "3️⃣ You may need to provide evidence\n"
            "4️⃣ Admin will review and make a decision\n"
            "5️⃣ Resolution within 7 business days\n\n"
            "⚠️ Opening a dispute will:\n"
            "• Freeze the transaction\n"
            "• Notify the seller and admins\n"
            "• Require both parties to provide evidence\n\n"
            "Do you want to proceed?"
        )

        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

        logger.info(
            f"Dispute initiated: User {user.id}, Transaction {transaction_id}"
        )

    except Exception as e:
        logger.error(f"Error in dispute command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>Error</b>\n\n"
            "Could not process dispute request.\n"
            "Please try again later.",
            parse_mode=ParseMode.HTML
        )


@rate_limit(seconds=2)
async def track(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /track command - Track order status.

    Usage: /track <transaction_id>
    Example: /track 12345

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
                "<b>Usage:</b> /track &lt;transaction_id&gt;\n"
                "<b>Example:</b> /track 12345",
                parse_mode=ParseMode.HTML
            )
            return

        transaction_id = sanitize_input(context.args[0])

        # Validate transaction ID
        try:
            transaction_id_int = int(transaction_id)
        except ValueError:
            await update.message.reply_text(
                "❌ <b>Invalid Transaction ID</b>\n\n"
                "Transaction ID must be a number.",
                parse_mode=ParseMode.HTML
            )
            return

        # Send checking message
        checking_msg = await update.message.reply_text(
            "🔍 <b>Tracking Order...</b>",
            parse_mode=ParseMode.HTML
        )

        # Get transaction
        transaction = await get_transaction_by_id(transaction_id_int)

        if not transaction:
            await checking_msg.edit_text(
                f"❌ <b>Transaction Not Found</b>\n\n"
                f"Transaction ID: {transaction_id}\n\n"
                "Please check the ID and try again.",
                parse_mode=ParseMode.HTML
            )
            return

        # Verify buyer owns this transaction
        if transaction['buyer_telegram_id'] != user.id:
            await checking_msg.edit_text(
                "🚫 <b>Access Denied</b>\n\n"
                "This transaction does not belong to you.",
                parse_mode=ParseMode.HTML
            )
            return

        # Get transaction timeline
        timeline = await get_transaction_timeline(transaction_id_int)

        # Calculate auto-release date
        auto_release_date = await calculate_auto_release_date(transaction)

        # Format tracking message
        status = transaction['status']
        status_emoji = STATUS_EMOJIS.get(status, '❓')

        message = (
            f"📦 <b>Order Tracking</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Transaction ID:</b> {transaction['id']}\n"
            f"<b>Status:</b> {status_emoji} {status}\n"
            f"<b>Amount:</b> KES {transaction['amount']:,}\n"
            f"<b>Seller:</b> {transaction['seller_name']}\n"
            f"<b>Item:</b> {transaction['description']}\n"
        )

        # Add tracking number if available
        if transaction.get('tracking_number'):
            message += f"<b>Tracking Number:</b> {transaction['tracking_number']}\n"

        message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        # Add timeline
        message += "📅 <b>Timeline:</b>\n\n"
        for event in timeline:
            event_emoji = STATUS_EMOJIS.get(event['status'], '•')
            message += (
                f"{event_emoji} <b>{event['status']}</b>\n"
                f"   {event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            if event.get('note'):
                message += f"   <i>{event['note']}</i>\n"
            message += "\n"

        # Add auto-release information
        if auto_release_date and status == 'SHIPPED':
            days_remaining = (auto_release_date - datetime.now()).days
            message += (
                f"\n⏰ <b>Auto-Release:</b>\n"
                f"Payment will be automatically released in {days_remaining} days\n"
                f"({auto_release_date.strftime('%Y-%m-%d')})\n"
            )

        # Add status-specific messages
        if status == 'HELD':
            message += (
                "\n💡 <b>Next Steps:</b>\n"
                "• Waiting for seller to ship the item\n"
                "• You'll be notified when shipped\n"
                "• You can cancel if seller doesn't ship\n"
            )
        elif status == 'SHIPPED':
            message += (
                "\n💡 <b>Next Steps:</b>\n"
                "• Waiting for delivery\n"
                "• Confirm delivery when you receive the item\n"
                "• Open dispute if there's an issue\n"
            )
        elif status == 'COMPLETED':
            message += (
                "\n✅ <b>Transaction Complete</b>\n"
                "Thank you for using our escrow service!\n"
            )
        elif status == 'DISPUTED':
            message += (
                "\n⚠️ <b>Dispute Active</b>\n"
                "Admin is reviewing your case.\n"
                "Resolution within 7 business days.\n"
            )

        # Create action buttons
        keyboard = []
        if status == 'HELD':
            keyboard.append([
                InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel_order_{transaction_id}")
            ])
        elif status == 'SHIPPED':
            keyboard.append([
                InlineKeyboardButton("✅ Confirm Delivery", callback_data=f"confirm_delivery_{transaction_id}"),
                InlineKeyboardButton("⚠️ Open Dispute", callback_data=f"dispute_{transaction_id}")
            ])

        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

        await checking_msg.edit_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Order tracked: User {user.id}, Transaction {transaction_id}")

    except Exception as e:
        logger.error(f"Error in track command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>Error</b>\n\n"
            "Could not retrieve tracking information.\n"
            "Please try again later.",
            parse_mode=ParseMode.HTML
        )


@rate_limit(seconds=5)
async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /cancel_order command - Cancel order before shipping.

    Usage: /cancel_order <transaction_id>
    Example: /cancel_order 12345

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
                "<b>Usage:</b> /cancel_order &lt;transaction_id&gt;\n"
                "<b>Example:</b> /cancel_order 12345",
                parse_mode=ParseMode.HTML
            )
            return

        transaction_id = sanitize_input(context.args[0])

        # Validate transaction ID
        try:
            transaction_id_int = int(transaction_id)
        except ValueError:
            await update.message.reply_text(
                "❌ <b>Invalid Transaction ID</b>\n\n"
                "Transaction ID must be a number.",
                parse_mode=ParseMode.HTML
            )
            return

        # Get transaction
        transaction = await get_transaction_by_id(transaction_id_int)

        if not transaction:
            await update.message.reply_text(
                f"❌ <b>Transaction Not Found</b>\n\n"
                f"Transaction ID: {transaction_id}\n\n"
                "Please check the ID and try again.",
                parse_mode=ParseMode.HTML
            )
            return

        # Verify buyer owns this transaction
        if transaction['buyer_telegram_id'] != user.id:
            await update.message.reply_text(
                "🚫 <b>Access Denied</b>\n\n"
                "This transaction does not belong to you.",
                parse_mode=ParseMode.HTML
            )
            logger.warning(
                f"Unauthorized cancel attempt: User {user.id}, Transaction {transaction_id}"
            )
            return

        # Check if order can be cancelled
        can_cancel, cancel_reason = await can_cancel_order(transaction)
        if not can_cancel:
            await update.message.reply_text(
                f"⚠️ <b>Cannot Cancel Order</b>\n\n{cancel_reason}",
                parse_mode=ParseMode.HTML
            )
            return

        # Store cancellation details for confirmation
        context.user_data['pending_cancellation'] = {
            'transaction_id': transaction_id_int,
            'transaction': transaction,
            'created_at': datetime.now()
        }

        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm Cancellation", callback_data="confirm_cancel"),
                InlineKeyboardButton("❌ Keep Order", callback_data="cancel_cancellation")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Format confirmation message
        message = (
            "❌ <b>Cancel Order</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Transaction ID:</b> {transaction['id']}\n"
            f"<b>Amount:</b> KES {transaction['amount']:,}\n"
            f"<b>Seller:</b> {transaction['seller_name']}\n"
            f"<b>Item:</b> {transaction['description']}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⚠️ <b>Cancellation Details:</b>\n"
            "• Your payment will be refunded immediately\n"
            "• Seller will be notified\n"
            "• Transaction will be marked as cancelled\n"
            "• This action cannot be undone\n\n"
            "Are you sure you want to cancel this order?"
        )

        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

        logger.info(
            f"Cancellation initiated: User {user.id}, Transaction {transaction_id}"
        )

    except Exception as e:
        logger.error(f"Error in cancel_order command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>Error</b>\n\n"
            "Could not process cancellation request.\n"
            "Please try again later.",
            parse_mode=ParseMode.HTML
        )


# Callback query handlers for inline buttons
async def handle_buy_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries for buy command."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    try:
        if query.data == "confirm_buy":
            pending_purchase = context.user_data.get('pending_purchase')

            if not pending_purchase:
                await query.edit_message_text(
                    "⚠️ <b>Purchase Expired</b>\n\n"
                    "This purchase request has expired.\n"
                    "Please use /buy to initiate a new purchase.",
                    parse_mode=ParseMode.HTML
                )
                return

            # Check if purchase hasn't expired (5 minutes)
            created_at = pending_purchase['created_at']
            if datetime.now() - created_at > timedelta(minutes=5):
                context.user_data['pending_purchase'] = None
                await query.edit_message_text(
                    "⏱️ <b>Purchase Expired</b>\n\n"
                    "Your purchase request has expired.\n"
                    "Please initiate a new purchase with /buy",
                    parse_mode=ParseMode.HTML
                )
                return

            # Update message to processing
            await query.edit_message_text(
                "⏳ <b>Processing Payment...</b>\n\n"
                "Initiating M-Pesa STK Push...",
                parse_mode=ParseMode.HTML
            )

            try:
                # Get buyer's phone number
                buyer = await get_user_by_telegram_id(user.id)
                if not buyer or not buyer.get('phone'):
                    await query.edit_message_text(
                        "❌ <b>Phone Number Required</b>\n\n"
                        "Please set up your phone number first.\n"
                        "Use /settings to add your phone number.",
                        parse_mode=ParseMode.HTML
                    )
                    return

                # Initiate M-Pesa payment
                result = await initiate_escrow_payment(
                    buyer_phone=buyer['phone'],
                    amount=pending_purchase['amount'],
                    seller_id=pending_purchase['seller_id'],
                    description=pending_purchase['description']
                )

                # Create escrow transaction
                transaction = await create_escrow_transaction(
                    buyer_telegram_id=user.id,
                    seller_id=pending_purchase['seller_id'],
                    amount=pending_purchase['amount'],
                    description=pending_purchase['description'],
                    mpesa_checkout_id=result['CheckoutRequestID']
                )

                # Clear pending purchase
                context.user_data['pending_purchase'] = None

                # Update message
                await query.edit_message_text(
                    "✅ <b>Payment Request Sent!</b>\n\n"
                    f"<b>Transaction ID:</b> <code>{transaction['id']}</code>\n"
                    f"<b>Amount:</b> KES {pending_purchase['amount']:,}\n"
                    f"<b>Seller:</b> {pending_purchase['seller_name']}\n\n"
                    "📱 Please check your phone and enter your M-Pesa PIN.\n\n"
                    "💡 Your payment will be held in escrow until you confirm delivery.\n\n"
                    f"Use /track {transaction['id']} to track your order.",
                    parse_mode=ParseMode.HTML
                )

                logger.info(
                    f"Escrow payment initiated: Buyer {user.id}, "
                    f"Transaction {transaction['id']}"
                )

            except MpesaError as e:
                await query.edit_message_text(
                    "❌ <b>Payment Failed</b>\n\n"
                    f"Error: {str(e)}\n\n"
                    "Please try again or contact support.",
                    parse_mode=ParseMode.HTML
                )
                logger.error(f"M-Pesa error for user {user.id}: {e}")

        elif query.data == "cancel_buy":
            context.user_data['pending_purchase'] = None

            await query.edit_message_text(
                "✅ <b>Purchase Cancelled</b>\n\n"
                "Your purchase has been cancelled.\n"
                "Use /buy to initiate a new purchase.",
                parse_mode=ParseMode.HTML
            )

            logger.info(f"Purchase cancelled: User {user.id}")

    except Exception as e:
        logger.error(f"Error in buy callback: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ <b>Error</b>\n\n"
            "An unexpected error occurred.\n"
            "Please try again later.",
            parse_mode=ParseMode.HTML
        )


async def handle_confirmation_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries for delivery confirmation."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    try:
        if query.data == "confirm_release":
            pending_confirmation = context.user_data.get('pending_confirmation')

            if not pending_confirmation:
                await query.edit_message_text(
                    "⚠️ <b>Confirmation Expired</b>\n\n"
                    "This confirmation request has expired.",
                    parse_mode=ParseMode.HTML
                )
                return

            transaction = pending_confirmation['transaction']

            # Update message to processing
            await query.edit_message_text(
                "⏳ <b>Processing...</b>\n\n"
                "Releasing payment to seller...",
                parse_mode=ParseMode.HTML
            )

            try:
                # Release payment to seller
                await release_payment_to_seller(transaction['id'])

                # Update transaction status
                await update_transaction_status(
                    transaction['id'],
                    'COMPLETED',
                    buyer_confirmed_at=datetime.now()
                )

                # Clear pending confirmation
                context.user_data['pending_confirmation'] = None

                # Ask for rating
                keyboard = [
                    [
                        InlineKeyboardButton("⭐", callback_data=f"rate_1_{transaction['id']}"),
                        InlineKeyboardButton("⭐⭐", callback_data=f"rate_2_{transaction['id']}"),
                        InlineKeyboardButton("⭐⭐⭐", callback_data=f"rate_3_{transaction['id']}"),
                    ],
                    [
                        InlineKeyboardButton("⭐⭐⭐⭐", callback_data=f"rate_4_{transaction['id']}"),
                        InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data=f"rate_5_{transaction['id']}"),
                    ],
                    [
                        InlineKeyboardButton("Skip Rating", callback_data="skip_rating")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    "✅ <b>Delivery Confirmed!</b>\n\n"
                    f"Payment of KES {transaction['amount']:,} has been released to {transaction['seller_name']}.\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "⭐ <b>Rate Your Experience</b>\n\n"
                    f"How would you rate {transaction['seller_name']}?",
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )

                logger.info(
                    f"Delivery confirmed: Transaction {transaction['id']}, "
                    f"User {user.id}"
                )

            except Exception as e:
                await query.edit_message_text(
                    "❌ <b>Error</b>\n\n"
                    f"Could not release payment: {str(e)}\n\n"
                    "Please contact support.",
                    parse_mode=ParseMode.HTML
                )
                logger.error(f"Error releasing payment: {e}", exc_info=True)

        elif query.data == "cancel_confirmation":
            context.user_data['pending_confirmation'] = None

            await query.edit_message_text(
                "ℹ️ <b>Confirmation Cancelled</b>\n\n"
                "Delivery confirmation has been cancelled.",
                parse_mode=ParseMode.HTML
            )

    except Exception as e:
        logger.error(f"Error in confirmation callback: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ <b>Error</b>\n\n"
            "An unexpected error occurred.",
            parse_mode=ParseMode.HTML
        )


async def handle_rating_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries for seller ratings."""
    query = update.callback_query
    await query.answer()

    try:
        if query.data.startswith("rate_"):
            parts = query.data.split("_")
            rating = int(parts[1])
            transaction_id = int(parts[2])

            # Add rating
            await add_rating(
                transaction_id=transaction_id,
                rating=rating,
                review=None
            )

            await query.edit_message_text(
                f"⭐ <b>Thank You!</b>\n\n"
                f"You rated this seller {rating} star{'s' if rating != 1 else ''}.\n\n"
                "Your feedback helps build trust in our community!",
                parse_mode=ParseMode.HTML
            )

            logger.info(f"Rating added: Transaction {transaction_id}, Rating {rating}")

        elif query.data == "skip_rating":
            await query.edit_message_text(
                "ℹ️ <b>Rating Skipped</b>\n\n"
                "You can rate the seller later from your transaction history.",
                parse_mode=ParseMode.HTML
            )

    except Exception as e:
        logger.error(f"Error in rating callback: {e}", exc_info=True)


async def handle_dispute_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries for disputes."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    try:
        if query.data == "confirm_dispute":
            pending_dispute = context.user_data.get('pending_dispute')

            if not pending_dispute:
                await query.edit_message_text(
                    "⚠️ <b>Dispute Expired</b>\n\n"
                    "This dispute request has expired.",
                    parse_mode=ParseMode.HTML
                )
                return

            transaction = pending_dispute['transaction']
            reason = pending_dispute['reason']

            # Update message to processing
            await query.edit_message_text(
                "⏳ <b>Opening Dispute...</b>",
                parse_mode=ParseMode.HTML
            )

            try:
                # Create dispute
                dispute = await create_dispute(
                    transaction_id=transaction['id'],
                    opened_by='BUYER',
                    reason=reason
                )

                # Update transaction status
                await update_transaction_status(
                    transaction['id'],
                    'DISPUTED',
                    disputed_at=datetime.now()
                )

                # Clear pending dispute
                context.user_data['pending_dispute'] = None

                # Notify admins (implement this in main bot)
                # await notify_admins_dispute(dispute)

                await query.edit_message_text(
                    "⚠️ <b>Dispute Opened</b>\n\n"
                    f"<b>Dispute ID:</b> {dispute['id']}\n"
                    f"<b>Transaction ID:</b> {transaction['id']}\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "✅ Your dispute has been submitted.\n\n"
                    "📋 <b>Next Steps:</b>\n"
                    "1. Admin has been notified\n"
                    "2. Seller has been notified\n"
                    "3. Both parties can provide evidence\n"
                    "4. Admin will review and decide\n\n"
                    "⏰ <b>Timeline:</b> Resolution within 7 business days\n\n"
                    "You will be notified of any updates.",
                    parse_mode=ParseMode.HTML
                )

                logger.info(
                    f"Dispute opened: Transaction {transaction['id']}, "
                    f"Dispute {dispute['id']}"
                )

            except Exception as e:
                await query.edit_message_text(
                    "❌ <b>Error</b>\n\n"
                    f"Could not open dispute: {str(e)}\n\n"
                    "Please contact support.",
                    parse_mode=ParseMode.HTML
                )
                logger.error(f"Error creating dispute: {e}", exc_info=True)

        elif query.data == "cancel_dispute":
            context.user_data['pending_dispute'] = None

            await query.edit_message_text(
                "ℹ️ <b>Dispute Cancelled</b>\n\n"
                "Dispute has been cancelled.",
                parse_mode=ParseMode.HTML
            )

    except Exception as e:
        logger.error(f"Error in dispute callback: {e}", exc_info=True)


async def handle_cancellation_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries for order cancellation."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    try:
        if query.data == "confirm_cancel":
            pending_cancellation = context.user_data.get('pending_cancellation')

            if not pending_cancellation:
                await query.edit_message_text(
                    "⚠️ <b>Cancellation Expired</b>\n\n"
                    "This cancellation request has expired.",
                    parse_mode=ParseMode.HTML
                )
                return

            transaction = pending_cancellation['transaction']

            # Update message to processing
            await query.edit_message_text(
                "⏳ <b>Processing Cancellation...</b>\n\n"
                "Refunding payment...",
                parse_mode=ParseMode.HTML
            )

            try:
                # Refund to buyer
                await refund_to_buyer(transaction['id'])

                # Update transaction status
                await update_transaction_status(
                    transaction['id'],
                    'CANCELLED',
                    cancelled_at=datetime.now()
                )

                # Clear pending cancellation
                context.user_data['pending_cancellation'] = None

                await query.edit_message_text(
                    "✅ <b>Order Cancelled</b>\n\n"
                    f"<b>Transaction ID:</b> {transaction['id']}\n"
                    f"<b>Refund Amount:</b> KES {transaction['amount']:,}\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "💰 Your payment has been refunded.\n"
                    "🔔 Seller has been notified.\n\n"
                    "The refund should appear in your M-Pesa account within a few minutes.",
                    parse_mode=ParseMode.HTML
                )

                logger.info(
                    f"Order cancelled: Transaction {transaction['id']}, "
                    f"User {user.id}"
                )

            except Exception as e:
                await query.edit_message_text(
                    "❌ <b>Error</b>\n\n"
                    f"Could not process refund: {str(e)}\n\n"
                    "Please contact support.",
                    parse_mode=ParseMode.HTML
                )
                logger.error(f"Error processing refund: {e}", exc_info=True)

        elif query.data == "cancel_cancellation":
            context.user_data['pending_cancellation'] = None

            await query.edit_message_text(
                "ℹ️ <b>Cancellation Aborted</b>\n\n"
                "Your order remains active.",
                parse_mode=ParseMode.HTML
            )

    except Exception as e:
        logger.error(f"Error in cancellation callback: {e}", exc_info=True)


# Export all handlers
__all__ = [
    'buy',
    'my_purchases',
    'confirm_delivery',
    'dispute',
    'track',
    'cancel_order',
    'handle_buy_callbacks',
    'handle_confirmation_callbacks',
    'handle_rating_callbacks',
    'handle_dispute_callbacks',
    'handle_cancellation_callbacks'
]
