"""
Escrow Seller-Side Command Handlers for M-Pesa Bot

This module contains all seller-specific command handlers for the escrow system,
including seller registration, sales management, shipping updates, fund releases,
and withdrawal functionality.

Features:
    - Seller registration and verification
    - Sales and earnings dashboard
    - Order management (mark shipped, request release)
    - Seller statistics and analytics
    - Fund withdrawal via M-Pesa B2C
    - Comprehensive validation and error handling

Dependencies:
    - escrow_service: Core escrow business logic
    - escrow_database: Escrow-specific database operations
    - mpesa_service: M-Pesa B2C payment integration
    - database: User and transaction management
    - utils: Validation and formatting utilities
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
    from config import get_config, Config
    config = get_config()
    ADMIN_USER_IDS = [int(config.admin_chat_id)] if config.admin_chat_id else []
    MIN_WITHDRAWAL_AMOUNT = 100
    MAX_WITHDRAWAL_AMOUNT = 150000
    EARLY_RELEASE_HOURS = 24
except ImportError as e:
    logging.warning(f"Config import error: {e}")
    ADMIN_USER_IDS = []
    MIN_WITHDRAWAL_AMOUNT = 100
    MAX_WITHDRAWAL_AMOUNT = 150000
    EARLY_RELEASE_HOURS = 24

try:
    from utils import (
        validate_kenyan_phone,
        validate_amount,
        format_currency,
        sanitize_input,
        mask_sensitive_data,
        setup_logger
    )
except ImportError as e:
    logging.warning(f"Utils import error: {e}")

try:
    from database import Database, get_database
except ImportError as e:
    logging.warning(f"Database import error: {e}")

# Import escrow-specific modules
try:
    from escrow_service import (
        EscrowService,
        EscrowError,
        EscrowStatus,
        initiate_seller_withdrawal
    )
    from escrow_database import (
        EscrowDatabase,
        get_seller_by_user_id,
        create_seller,
        update_seller_status,
        get_seller_transactions,
        get_seller_statistics,
        mark_transaction_shipped,
        request_early_release,
        get_transaction_by_id,
        record_withdrawal
    )
except ImportError as e:
    logging.warning(f"Escrow module import error: {e}. These modules need to be created.")
    # Placeholder classes for development
    class EscrowError(Exception):
        pass

    class EscrowStatus:
        PENDING = 'PENDING'
        HELD = 'HELD'
        SHIPPED = 'SHIPPED'
        COMPLETED = 'COMPLETED'
        DISPUTED = 'DISPUTED'
        REFUNDED = 'REFUNDED'
        CANCELLED = 'CANCELLED'


# Configure logging
logger = setup_logger('escrow_seller', 'INFO', 'logs/escrow_seller.log') if 'setup_logger' in dir() else logging.getLogger(__name__)


# Decorators
def seller_only(func):
    """Decorator to restrict command access to registered sellers only."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id

        try:
            seller = await get_seller_by_user_id(user_id)

            if not seller:
                await update.message.reply_text(
                    "🚫 <b>Seller Access Required</b>\n\n"
                    "You need to be a registered seller to use this command.\n\n"
                    "Use /register_seller to get started!",
                    parse_mode=ParseMode.HTML
                )
                logger.warning(f"Non-seller user {user_id} attempted to access seller command: {func.__name__}")
                return

            if seller['status'] != 'APPROVED':
                status_messages = {
                    'PENDING': '⏳ Your seller registration is pending admin approval.',
                    'SUSPENDED': '🚫 Your seller account has been suspended. Contact support.',
                    'REJECTED': '❌ Your seller registration was rejected. Contact support.'
                }
                await update.message.reply_text(
                    f"<b>Account Status: {seller['status']}</b>\n\n"
                    f"{status_messages.get(seller['status'], 'Your account is not active.')}\n\n"
                    "Contact support for more information.",
                    parse_mode=ParseMode.HTML
                )
                return

            # Add seller info to context for use in handler
            context.user_data['seller'] = seller
            return await func(update, context, *args, **kwargs)

        except Exception as e:
            logger.error(f"Error in seller_only decorator: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ <b>Error</b>\n\n"
                "Could not verify seller status. Please try again.",
                parse_mode=ParseMode.HTML
            )

    return wrapper


def rate_limit(seconds: int = 3):
    """Decorator to implement rate limiting for commands."""
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
                        f"⏳ Please wait {int(seconds - time_diff)} seconds before using this command again."
                    )
                    return

            # Update last request time
            context.user_data['rate_limit'][func.__name__] = current_time

            return await func(update, context, *args, **kwargs)

        return wrapper
    return decorator


# ============================================================================
# COMMAND HANDLERS
# ============================================================================

@rate_limit(5)
async def register_seller(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /register_seller command - Register as a seller.

    Usage: /register_seller <business_name> <mpesa_number>
    Example: /register_seller "MyShop Kenya" 254712345678

    Collects business details, requests verification documents, and submits
    for admin approval.
    """
    user = update.effective_user
    user_id = user.id

    try:
        # Check if already registered
        try:
            existing_seller = await get_seller_by_user_id(user_id)
            if existing_seller:
                status_emoji = {
                    'APPROVED': '✅',
                    'PENDING': '⏳',
                    'SUSPENDED': '🚫',
                    'REJECTED': '❌'
                }.get(existing_seller['status'], '❓')

                await update.message.reply_text(
                    f"ℹ️ <b>Already Registered</b>\n\n"
                    f"<b>Status:</b> {status_emoji} {existing_seller['status']}\n"
                    f"<b>Business:</b> {existing_seller['business_name']}\n"
                    f"<b>Seller ID:</b> <code>{existing_seller['seller_id']}</code>\n\n"
                    f"Use /seller_stats to view your dashboard.",
                    parse_mode=ParseMode.HTML
                )
                return
        except Exception:
            pass  # Not registered, continue

        # Parse arguments
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ <b>Invalid Format</b>\n\n"
                "<b>Usage:</b> /register_seller &lt;business_name&gt; &lt;mpesa_number&gt;\n\n"
                "<b>Example:</b>\n"
                "/register_seller \"MyShop Kenya\" 254712345678\n\n"
                "<b>Requirements:</b>\n"
                "• Business name (use quotes if it contains spaces)\n"
                "• M-Pesa number for receiving payments (254XXXXXXXXX)\n\n"
                "After registration, an admin will review and approve your application.",
                parse_mode=ParseMode.HTML
            )
            return

        # Extract business name and phone number
        # Handle quoted business names
        args_text = ' '.join(context.args)
        if '"' in args_text:
            # Extract quoted business name
            import re
            match = re.match(r'"([^"]+)"\s+(\S+)', args_text)
            if match:
                business_name = match.group(1)
                phone = match.group(2)
            else:
                await update.message.reply_text(
                    "❌ Invalid format. Use quotes around business name if it contains spaces.",
                    parse_mode=ParseMode.HTML
                )
                return
        else:
            # Last argument is phone, rest is business name
            phone = context.args[-1]
            business_name = ' '.join(context.args[:-1])

        # Validate business name
        business_name = sanitize_input(business_name, max_length=100)
        if len(business_name) < 3:
            await update.message.reply_text(
                "❌ <b>Invalid Business Name</b>\n\n"
                "Business name must be at least 3 characters long.",
                parse_mode=ParseMode.HTML
            )
            return

        # Validate phone number
        is_valid, formatted_phone, error = validate_kenyan_phone(phone)
        if not is_valid:
            await update.message.reply_text(
                f"❌ <b>Invalid Phone Number</b>\n\n{error}\n\n"
                "Please use format: 254XXXXXXXXX",
                parse_mode=ParseMode.HTML
            )
            return

        # Send processing message
        processing_msg = await update.message.reply_text(
            "⏳ <b>Processing Registration...</b>",
            parse_mode=ParseMode.HTML
        )

        # Create seller record
        seller = await create_seller(
            user_id=user_id,
            username=user.username or user.first_name,
            business_name=business_name,
            mpesa_number=formatted_phone,
            email=None,  # Can be collected later
            status='PENDING'
        )

        # Notify admins
        admin_notification = (
            "🔔 <b>New Seller Registration</b>\n\n"
            f"<b>Seller ID:</b> <code>{seller['seller_id']}</code>\n"
            f"<b>Business:</b> {business_name}\n"
            f"<b>User:</b> {user.first_name} (@{user.username})\n"
            f"<b>User ID:</b> <code>{user_id}</code>\n"
            f"<b>M-Pesa:</b> {mask_sensitive_data(formatted_phone, 4)}\n\n"
            f"Review and approve/reject this seller."
        )

        for admin_id in ADMIN_USER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_notification,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

        # Update success message
        await processing_msg.edit_text(
            "✅ <b>Registration Submitted!</b>\n\n"
            f"<b>Business:</b> {business_name}\n"
            f"<b>Seller ID:</b> <code>{seller['seller_id']}</code>\n"
            f"<b>M-Pesa Number:</b> {formatted_phone}\n"
            f"<b>Status:</b> ⏳ Pending Approval\n\n"
            "Your application has been submitted for admin review.\n"
            "You'll be notified once approved.\n\n"
            "<b>Next Steps:</b>\n"
            "• Wait for admin approval (usually within 24 hours)\n"
            "• Prepare verification documents if requested\n"
            "• Once approved, you can start selling!\n\n"
            "Questions? Contact support.",
            parse_mode=ParseMode.HTML
        )

        logger.info(f"New seller registered: {seller['seller_id']} - {business_name} (User: {user_id})")

    except Exception as e:
        logger.error(f"Error in register_seller: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>Registration Failed</b>\n\n"
            "An error occurred during registration. Please try again later.",
            parse_mode=ParseMode.HTML
        )


@seller_only
@rate_limit(3)
async def my_sales(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /my_sales command - View all sales and orders.

    Displays active orders (HELD, SHIPPED), completed sales, earnings,
    disputed transactions, and action buttons for each order.
    """
    user = update.effective_user
    seller = context.user_data.get('seller')

    if not seller:
        await update.message.reply_text(
            "❌ Error: Seller information not found.",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        # Fetch seller transactions
        transactions = await get_seller_transactions(
            seller_id=seller['seller_id'],
            limit=50
        )

        if not transactions:
            await update.message.reply_text(
                "📭 <b>No Sales Yet</b>\n\n"
                "You haven't made any sales yet.\n"
                "Your sales will appear here once customers make purchases.",
                parse_mode=ParseMode.HTML
            )
            return

        # Categorize transactions
        active_orders = []
        completed_sales = []
        disputed_transactions = []

        total_held = Decimal('0')
        total_released = Decimal('0')

        for txn in transactions:
            status = txn['status']
            amount = Decimal(str(txn['amount']))

            if status in ['HELD', 'SHIPPED']:
                active_orders.append(txn)
                total_held += amount
            elif status == 'COMPLETED':
                completed_sales.append(txn)
                total_released += amount
            elif status == 'DISPUTED':
                disputed_transactions.append(txn)

        # Build summary message
        summary = (
            f"📊 <b>Sales Dashboard - {seller['business_name']}</b>\n\n"
            f"<b>💰 Earnings Summary:</b>\n"
            f"  • Held in Escrow: KES {total_held:,}\n"
            f"  • Released: KES {total_released:,}\n"
            f"  • Total Earnings: KES {total_held + total_released:,}\n\n"
        )

        # Active orders
        if active_orders:
            summary += f"<b>📦 Active Orders ({len(active_orders)}):</b>\n"
            for i, txn in enumerate(active_orders[:5], 1):
                status_emoji = '🔒' if txn['status'] == 'HELD' else '🚚'
                summary += (
                    f"\n{i}. {status_emoji} <b>{txn['status']}</b>\n"
                    f"   ID: <code>{txn['transaction_id']}</code>\n"
                    f"   Amount: KES {Decimal(str(txn['amount'])):,}\n"
                    f"   Date: {txn['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
                )

                # Add action buttons hint
                if txn['status'] == 'HELD':
                    summary += f"   ➡️ /mark_shipped {txn['transaction_id']} [tracking]\n"
                elif txn['status'] == 'SHIPPED':
                    summary += f"   ➡️ /request_release {txn['transaction_id']}\n"

            if len(active_orders) > 5:
                summary += f"\n...and {len(active_orders) - 5} more\n"

        # Completed sales
        if completed_sales:
            summary += f"\n<b>✅ Completed Sales ({len(completed_sales)}):</b>\n"
            for i, txn in enumerate(completed_sales[:3], 1):
                summary += (
                    f"{i}. KES {Decimal(str(txn['amount'])):,} - "
                    f"{txn['completed_at'].strftime('%Y-%m-%d') if txn.get('completed_at') else 'N/A'}\n"
                )

            if len(completed_sales) > 3:
                summary += f"...and {len(completed_sales) - 3} more\n"

        # Disputed transactions
        if disputed_transactions:
            summary += f"\n<b>⚠️ Disputed Transactions ({len(disputed_transactions)}):</b>\n"
            for i, txn in enumerate(disputed_transactions[:3], 1):
                summary += (
                    f"{i}. <code>{txn['transaction_id']}</code> - "
                    f"KES {Decimal(str(txn['amount'])):,}\n"
                )

        summary += (
            f"\n<b>Quick Actions:</b>\n"
            f"• /mark_shipped &lt;txn_id&gt; &lt;tracking&gt; - Mark order shipped\n"
            f"• /request_release &lt;txn_id&gt; - Request early release\n"
            f"• /withdraw - Withdraw available funds\n"
            f"• /seller_stats - View detailed statistics"
        )

        await update.message.reply_text(summary, parse_mode=ParseMode.HTML)

        logger.info(f"Sales dashboard viewed by seller {seller['seller_id']}")

    except Exception as e:
        logger.error(f"Error in my_sales: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>Error</b>\n\n"
            "Could not retrieve sales data. Please try again.",
            parse_mode=ParseMode.HTML
        )


@seller_only
@rate_limit(3)
async def mark_shipped(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /mark_shipped command - Mark order as shipped.

    Usage: /mark_shipped <transaction_id> <tracking_number>
    Example: /mark_shipped TXN123456 TK987654321

    Verifies seller owns transaction, updates status to SHIPPED,
    adds tracking info, and notifies buyer.
    """
    user = update.effective_user
    seller = context.user_data.get('seller')

    if not seller:
        await update.message.reply_text(
            "❌ Error: Seller information not found.",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        # Validate arguments
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ <b>Invalid Format</b>\n\n"
                "<b>Usage:</b> /mark_shipped &lt;transaction_id&gt; &lt;tracking_number&gt;\n\n"
                "<b>Example:</b>\n"
                "/mark_shipped TXN123456 TK987654321\n\n"
                "This will mark the order as shipped and notify the buyer.",
                parse_mode=ParseMode.HTML
            )
            return

        transaction_id = sanitize_input(context.args[0])
        tracking_number = sanitize_input(' '.join(context.args[1:]), max_length=50)

        if len(tracking_number) < 3:
            await update.message.reply_text(
                "❌ <b>Invalid Tracking Number</b>\n\n"
                "Tracking number must be at least 3 characters long.",
                parse_mode=ParseMode.HTML
            )
            return

        # Send processing message
        processing_msg = await update.message.reply_text(
            "⏳ <b>Processing...</b>",
            parse_mode=ParseMode.HTML
        )

        # Get transaction
        transaction = await get_transaction_by_id(transaction_id)

        if not transaction:
            await processing_msg.edit_text(
                f"❌ <b>Transaction Not Found</b>\n\n"
                f"Transaction ID: <code>{transaction_id}</code>\n\n"
                "Please verify the transaction ID and try again.",
                parse_mode=ParseMode.HTML
            )
            return

        # Verify seller owns this transaction
        if transaction['seller_id'] != seller['seller_id']:
            await processing_msg.edit_text(
                "🚫 <b>Access Denied</b>\n\n"
                "This transaction does not belong to you.",
                parse_mode=ParseMode.HTML
            )
            logger.warning(
                f"Seller {seller['seller_id']} attempted to access transaction {transaction_id} "
                f"owned by {transaction['seller_id']}"
            )
            return

        # Verify transaction is in HELD state
        if transaction['status'] != 'HELD':
            status_messages = {
                'SHIPPED': 'This order has already been marked as shipped.',
                'COMPLETED': 'This order has already been completed.',
                'DISPUTED': 'This order is under dispute. Contact support.',
                'REFUNDED': 'This order has been refunded.',
                'CANCELLED': 'This order has been cancelled.'
            }
            await processing_msg.edit_text(
                f"⚠️ <b>Invalid Status</b>\n\n"
                f"{status_messages.get(transaction['status'], 'Cannot mark this order as shipped.')}\n\n"
                f"Current Status: {transaction['status']}",
                parse_mode=ParseMode.HTML
            )
            return

        # Mark as shipped
        updated_transaction = await mark_transaction_shipped(
            transaction_id=transaction_id,
            tracking_number=tracking_number,
            shipped_by=seller['seller_id']
        )

        # Calculate auto-release date
        auto_release_hours = updated_transaction.get('auto_release_hours', 72)
        auto_release_date = datetime.now() + timedelta(hours=auto_release_hours)

        # Notify buyer
        if transaction.get('buyer_user_id'):
            buyer_notification = (
                "📦 <b>Order Shipped!</b>\n\n"
                f"<b>Order ID:</b> <code>{transaction_id}</code>\n"
                f"<b>Seller:</b> {seller['business_name']}\n"
                f"<b>Amount:</b> KES {Decimal(str(transaction['amount'])):,}\n"
                f"<b>Tracking Number:</b> <code>{tracking_number}</code>\n\n"
                f"Your order has been shipped!\n\n"
                f"<b>Auto-release:</b> {auto_release_date.strftime('%Y-%m-%d %H:%M')}\n"
                f"Funds will be released to seller automatically in {auto_release_hours} hours "
                f"unless you report an issue.\n\n"
                f"Track your order with the tracking number above.\n"
                f"Contact the seller if you have any questions."
            )

            try:
                await context.bot.send_message(
                    chat_id=transaction['buyer_user_id'],
                    text=buyer_notification,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Failed to notify buyer {transaction['buyer_user_id']}: {e}")

        # Success message
        await processing_msg.edit_text(
            "✅ <b>Order Marked as Shipped!</b>\n\n"
            f"<b>Transaction ID:</b> <code>{transaction_id}</code>\n"
            f"<b>Tracking Number:</b> <code>{tracking_number}</code>\n"
            f"<b>Amount:</b> KES {Decimal(str(transaction['amount'])):,}\n\n"
            f"<b>Status:</b> 🚚 SHIPPED\n\n"
            f"<b>Auto-release Date:</b>\n"
            f"{auto_release_date.strftime('%Y-%m-%d at %H:%M')}\n\n"
            f"Funds will be automatically released in {auto_release_hours} hours.\n\n"
            "The buyer has been notified with tracking information.\n\n"
            f"You can request early release after 24 hours:\n"
            f"/request_release {transaction_id}",
            parse_mode=ParseMode.HTML
        )

        logger.info(
            f"Transaction {transaction_id} marked as shipped by seller {seller['seller_id']} "
            f"with tracking: {tracking_number}"
        )

    except Exception as e:
        logger.error(f"Error in mark_shipped: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>Error</b>\n\n"
            "Could not mark order as shipped. Please try again.",
            parse_mode=ParseMode.HTML
        )


@seller_only
@rate_limit(3)
async def request_release(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /request_release command - Request early release of funds.

    Usage: /request_release <transaction_id>
    Example: /request_release TXN123456

    For established sellers, allows requesting early fund release after
    order has been shipped for 24+ hours. Sends notification to buyer.
    """
    user = update.effective_user
    seller = context.user_data.get('seller')

    if not seller:
        await update.message.reply_text(
            "❌ Error: Seller information not found.",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        # Validate arguments
        if len(context.args) != 1:
            await update.message.reply_text(
                "❌ <b>Invalid Format</b>\n\n"
                "<b>Usage:</b> /request_release &lt;transaction_id&gt;\n\n"
                "<b>Example:</b>\n"
                "/request_release TXN123456\n\n"
                "<b>Requirements:</b>\n"
                "• Order must be marked as SHIPPED\n"
                "• At least 24 hours since shipping\n"
                "• No active disputes\n\n"
                "This will send a release request to the buyer.",
                parse_mode=ParseMode.HTML
            )
            return

        transaction_id = sanitize_input(context.args[0])

        # Send processing message
        processing_msg = await update.message.reply_text(
            "⏳ <b>Processing Request...</b>",
            parse_mode=ParseMode.HTML
        )

        # Get transaction
        transaction = await get_transaction_by_id(transaction_id)

        if not transaction:
            await processing_msg.edit_text(
                f"❌ <b>Transaction Not Found</b>\n\n"
                f"Transaction ID: <code>{transaction_id}</code>\n\n"
                "Please verify the transaction ID and try again.",
                parse_mode=ParseMode.HTML
            )
            return

        # Verify seller owns this transaction
        if transaction['seller_id'] != seller['seller_id']:
            await processing_msg.edit_text(
                "🚫 <b>Access Denied</b>\n\n"
                "This transaction does not belong to you.",
                parse_mode=ParseMode.HTML
            )
            return

        # Verify transaction is in SHIPPED state
        if transaction['status'] != 'SHIPPED':
            await processing_msg.edit_text(
                f"⚠️ <b>Invalid Status</b>\n\n"
                f"Only shipped orders can request early release.\n\n"
                f"Current Status: {transaction['status']}\n\n"
                f"First mark the order as shipped:\n"
                f"/mark_shipped {transaction_id} [tracking_number]",
                parse_mode=ParseMode.HTML
            )
            return

        # Check if shipped for at least 24 hours
        shipped_at = transaction.get('shipped_at')
        if not shipped_at:
            await processing_msg.edit_text(
                "❌ <b>Error</b>\n\n"
                "Shipping timestamp not found. Please contact support.",
                parse_mode=ParseMode.HTML
            )
            return

        hours_since_shipped = (datetime.now() - shipped_at).total_seconds() / 3600

        if hours_since_shipped < EARLY_RELEASE_HOURS:
            remaining_hours = int(EARLY_RELEASE_HOURS - hours_since_shipped)
            await processing_msg.edit_text(
                f"⏱️ <b>Too Early</b>\n\n"
                f"Early release requests require at least {EARLY_RELEASE_HOURS} hours after shipping.\n\n"
                f"<b>Shipped:</b> {shipped_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"<b>Time elapsed:</b> {int(hours_since_shipped)} hours\n"
                f"<b>Time remaining:</b> {remaining_hours} hours\n\n"
                f"Please try again after {(shipped_at + timedelta(hours=EARLY_RELEASE_HOURS)).strftime('%Y-%m-%d %H:%M')}",
                parse_mode=ParseMode.HTML
            )
            return

        # Submit early release request
        release_request = await request_early_release(
            transaction_id=transaction_id,
            seller_id=seller['seller_id'],
            reason=f"Order shipped {int(hours_since_shipped)} hours ago"
        )

        # Notify buyer
        if transaction.get('buyer_user_id'):
            buyer_notification = (
                "🔔 <b>Early Release Request</b>\n\n"
                f"<b>Order ID:</b> <code>{transaction_id}</code>\n"
                f"<b>Seller:</b> {seller['business_name']}\n"
                f"<b>Amount:</b> KES {Decimal(str(transaction['amount'])):,}\n"
                f"<b>Tracking:</b> {transaction.get('tracking_number', 'N/A')}\n\n"
                f"The seller has requested early release of funds.\n\n"
                f"<b>Please review:</b>\n"
                f"• Have you received the order?\n"
                f"• Is everything as described?\n"
                f"• Are you satisfied with the purchase?\n\n"
                f"If yes, you can approve the release:\n"
                f"/approve_release {transaction_id}\n\n"
                f"If there's an issue, report it:\n"
                f"/dispute {transaction_id}\n\n"
                f"If you don't respond, funds will be auto-released on: "
                f"{transaction.get('auto_release_date', 'N/A')}"
            )

            try:
                await context.bot.send_message(
                    chat_id=transaction['buyer_user_id'],
                    text=buyer_notification,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Failed to notify buyer {transaction['buyer_user_id']}: {e}")

        # Success message
        await processing_msg.edit_text(
            "✅ <b>Release Request Sent!</b>\n\n"
            f"<b>Transaction ID:</b> <code>{transaction_id}</code>\n"
            f"<b>Amount:</b> KES {Decimal(str(transaction['amount'])):,}\n\n"
            f"Your early release request has been sent to the buyer.\n\n"
            f"<b>Next Steps:</b>\n"
            f"• Buyer will be notified to review the order\n"
            f"• They can approve release immediately\n"
            f"• Or funds auto-release on: {transaction.get('auto_release_date', 'N/A')}\n\n"
            f"You'll be notified when funds are released.",
            parse_mode=ParseMode.HTML
        )

        logger.info(
            f"Early release requested for transaction {transaction_id} "
            f"by seller {seller['seller_id']}"
        )

    except Exception as e:
        logger.error(f"Error in request_release: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>Error</b>\n\n"
            "Could not submit release request. Please try again.",
            parse_mode=ParseMode.HTML
        )


@seller_only
@rate_limit(3)
async def seller_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /seller_stats command - Display comprehensive seller dashboard.

    Shows total sales, amounts held/released, success rate, ratings,
    active disputes, and seller level/badge.
    """
    user = update.effective_user
    seller = context.user_data.get('seller')

    if not seller:
        await update.message.reply_text(
            "❌ Error: Seller information not found.",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        # Fetch seller statistics
        stats = await get_seller_statistics(seller['seller_id'])

        # Determine seller level/badge
        total_sales = stats['total_sales']
        seller_level = '🥉 Bronze'
        if total_sales >= 100:
            seller_level = '💎 Diamond'
        elif total_sales >= 50:
            seller_level = '🥇 Gold'
        elif total_sales >= 20:
            seller_level = '🥈 Silver'

        # Format statistics
        dashboard = (
            f"📊 <b>Seller Dashboard</b>\n"
            f"{'=' * 40}\n\n"
            f"<b>👤 Seller Information</b>\n"
            f"Business: {seller['business_name']}\n"
            f"Seller ID: <code>{seller['seller_id']}</code>\n"
            f"Level: {seller_level}\n"
            f"Rating: {'⭐' * int(stats.get('average_rating', 0))} "
            f"({stats.get('average_rating', 0):.1f}/5.0)\n"
            f"Member Since: {seller['created_at'].strftime('%Y-%m-%d')}\n\n"

            f"<b>💰 Financial Summary</b>\n"
            f"Total Earnings: KES {Decimal(str(stats['total_earnings'])):,}\n"
            f"  ├─ Held in Escrow: KES {Decimal(str(stats['amount_held'])):,}\n"
            f"  ├─ Released: KES {Decimal(str(stats['amount_released'])):,}\n"
            f"  └─ Available to Withdraw: KES {Decimal(str(stats['available_balance'])):,}\n\n"

            f"<b>📦 Sales Statistics</b>\n"
            f"Total Sales: {stats['total_sales']}\n"
            f"  ├─ Active Orders: {stats['active_orders']}\n"
            f"  ├─ Completed: {stats['completed_sales']}\n"
            f"  ├─ Disputed: {stats['disputed_transactions']}\n"
            f"  └─ Success Rate: {stats['success_rate']:.1f}%\n\n"

            f"<b>📈 Performance Metrics</b>\n"
            f"Average Order Value: KES {Decimal(str(stats['average_order_value'])):,}\n"
            f"Shipping Speed: {stats.get('avg_shipping_hours', 0):.1f} hours\n"
            f"Customer Satisfaction: {stats.get('satisfaction_rate', 0):.1f}%\n"
            f"Response Rate: {stats.get('response_rate', 0):.1f}%\n\n"
        )

        # Add warnings if any
        if stats['disputed_transactions'] > 0:
            dashboard += (
                f"⚠️ <b>Active Disputes: {stats['disputed_transactions']}</b>\n"
                f"Please resolve disputes promptly to maintain your rating.\n\n"
            )

        # Quick actions
        dashboard += (
            f"<b>🚀 Quick Actions</b>\n"
            f"• /my_sales - View all your sales\n"
            f"• /withdraw - Withdraw available funds\n"
            f"• /seller_help - Get help and tips\n"
        )

        # Add withdrawal button if balance available
        if stats['available_balance'] > 0:
            keyboard = [
                [InlineKeyboardButton(
                    f"💸 Withdraw KES {Decimal(str(stats['available_balance'])):,}",
                    callback_data=f"withdraw_confirm"
                )]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                dashboard,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                dashboard,
                parse_mode=ParseMode.HTML
            )

        logger.info(f"Seller stats viewed by seller {seller['seller_id']}")

    except Exception as e:
        logger.error(f"Error in seller_stats: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>Error</b>\n\n"
            "Could not retrieve seller statistics. Please try again.",
            parse_mode=ParseMode.HTML
        )


@seller_only
@rate_limit(5)
async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /withdraw command - Withdraw released funds via M-Pesa B2C.

    Shows available balance, initiates M-Pesa B2C payment to seller's
    registered M-Pesa number, and records the withdrawal.
    """
    user = update.effective_user
    seller = context.user_data.get('seller')

    if not seller:
        await update.message.reply_text(
            "❌ Error: Seller information not found.",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        # Get seller statistics to check available balance
        stats = await get_seller_statistics(seller['seller_id'])
        available_balance = Decimal(str(stats['available_balance']))

        if available_balance < MIN_WITHDRAWAL_AMOUNT:
            await update.message.reply_text(
                f"💰 <b>Insufficient Balance</b>\n\n"
                f"<b>Available Balance:</b> KES {available_balance:,}\n"
                f"<b>Minimum Withdrawal:</b> KES {MIN_WITHDRAWAL_AMOUNT:,}\n\n"
                f"You need at least KES {MIN_WITHDRAWAL_AMOUNT:,} to withdraw.\n\n"
                f"Continue making sales to increase your balance!",
                parse_mode=ParseMode.HTML
            )
            return

        # Create confirmation keyboard
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Confirm Withdrawal",
                    callback_data=f"withdraw_execute:{seller['seller_id']}"
                ),
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="withdraw_cancel"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Show withdrawal confirmation
        confirmation_msg = (
            f"💸 <b>Withdrawal Confirmation</b>\n\n"
            f"<b>Available Balance:</b> KES {available_balance:,}\n"
            f"<b>M-Pesa Number:</b> {seller['mpesa_number']}\n"
            f"<b>Business:</b> {seller['business_name']}\n\n"
            f"<b>Withdrawal Details:</b>\n"
            f"Amount: KES {available_balance:,}\n"
            f"Method: M-Pesa B2C\n"
            f"Processing Fee: KES 0 (Free!)\n"
            f"You will receive: KES {available_balance:,}\n\n"
            f"⚠️ Please confirm your M-Pesa number is correct.\n"
            f"Funds will be sent to: {seller['mpesa_number']}\n\n"
            f"Confirm to proceed with withdrawal."
        )

        await update.message.reply_text(
            confirmation_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

        logger.info(f"Withdrawal initiated by seller {seller['seller_id']}, amount: {available_balance}")

    except Exception as e:
        logger.error(f"Error in withdraw: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>Error</b>\n\n"
            "Could not process withdrawal request. Please try again.",
            parse_mode=ParseMode.HTML
        )


async def seller_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /seller_help command - Display seller-specific help information.

    Explains how escrow works, best practices, dispute prevention,
    and withdrawal process.
    """
    help_text = (
        "📚 <b>Seller Help Guide</b>\n"
        "=" * 40 + "\n\n"

        "<b>🔒 How Escrow Works</b>\n\n"
        "1. <b>Customer Pays:</b>\n"
        "   • Customer makes payment via M-Pesa\n"
        "   • Funds are held securely in escrow\n"
        "   • You are notified of the new order\n\n"

        "2. <b>You Ship the Order:</b>\n"
        "   • Process and ship the order\n"
        "   • Use: /mark_shipped [txn_id] [tracking]\n"
        "   • Customer receives tracking info\n\n"

        "3. <b>Funds Are Released:</b>\n"
        "   • Auto-release after 72 hours\n"
        "   • Or request early release after 24h\n"
        "   • Funds move to your available balance\n\n"

        "4. <b>You Withdraw:</b>\n"
        "   • Use /withdraw to get paid\n"
        "   • Sent directly to your M-Pesa\n"
        "   • Free withdrawals, no fees!\n\n"

        "<b>✅ Best Practices</b>\n\n"
        "• Ship orders within 24-48 hours\n"
        "• Provide accurate tracking numbers\n"
        "• Communicate with customers\n"
        "• Package items securely\n"
        "• Respond to messages promptly\n"
        "• Maintain high ratings\n\n"

        "<b>🛡️ Dispute Prevention</b>\n\n"
        "• Accurately describe products\n"
        "• Use quality photos\n"
        "• Ship to correct addresses\n"
        "• Confirm orders before shipping\n"
        "• Keep shipping receipts\n"
        "• Be professional and courteous\n\n"

        "<b>💸 Withdrawal Process</b>\n\n"
        f"• Minimum: KES {MIN_WITHDRAWAL_AMOUNT:,}\n"
        f"• Maximum: KES {MAX_WITHDRAWAL_AMOUNT:,}\n"
        "• Processing: Instant via M-Pesa B2C\n"
        "• Fees: None (100% free)\n"
        "• Withdrawals sent to your registered M-Pesa number\n\n"

        "<b>📊 Seller Commands</b>\n\n"
        "/register_seller - Register as seller\n"
        "/my_sales - View all sales\n"
        "/mark_shipped - Mark order shipped\n"
        "/request_release - Request early release\n"
        "/seller_stats - View dashboard\n"
        "/withdraw - Withdraw funds\n"
        "/seller_help - This help message\n\n"

        "<b>📞 Support</b>\n\n"
        "Need help? Contact our support team.\n"
        "We're here to help you succeed!\n\n"

        "🚀 <b>Ready to start selling?</b>\n"
        "Use /register_seller to get started!"
    )

    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)


# ============================================================================
# CALLBACK QUERY HANDLERS
# ============================================================================

async def seller_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle callback queries from seller inline keyboard buttons.

    Handles:
    - Withdrawal confirmation/cancellation
    - Bulk actions
    - Quick stats refresh
    """
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    data = query.data

    try:
        # Withdrawal execution
        if data.startswith("withdraw_execute:"):
            seller_id = data.split(":")[1]

            # Verify user is the seller
            seller = await get_seller_by_user_id(user.id)
            if not seller or seller['seller_id'] != seller_id:
                await query.edit_message_text(
                    "🚫 <b>Access Denied</b>\n\n"
                    "You are not authorized to perform this action.",
                    parse_mode=ParseMode.HTML
                )
                return

            # Update message to processing
            await query.edit_message_text(
                "⏳ <b>Processing Withdrawal...</b>\n\n"
                "Please wait while we transfer funds to your M-Pesa number.\n"
                "This may take a few moments.",
                parse_mode=ParseMode.HTML
            )

            # Get available balance
            stats = await get_seller_statistics(seller_id)
            amount = Decimal(str(stats['available_balance']))

            if amount < MIN_WITHDRAWAL_AMOUNT:
                await query.edit_message_text(
                    f"❌ <b>Insufficient Balance</b>\n\n"
                    f"Available: KES {amount:,}\n"
                    f"Minimum: KES {MIN_WITHDRAWAL_AMOUNT:,}",
                    parse_mode=ParseMode.HTML
                )
                return

            # Initiate B2C payment
            try:
                result = await initiate_seller_withdrawal(
                    seller_id=seller_id,
                    phone_number=seller['mpesa_number'],
                    amount=float(amount),
                    reference=f"WD-{seller_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                )

                # Record withdrawal
                withdrawal = await record_withdrawal(
                    seller_id=seller_id,
                    amount=amount,
                    mpesa_transaction_id=result.get('ConversationID'),
                    status='PENDING'
                )

                # Success message
                await query.edit_message_text(
                    "✅ <b>Withdrawal Initiated!</b>\n\n"
                    f"<b>Amount:</b> KES {amount:,}\n"
                    f"<b>M-Pesa Number:</b> {seller['mpesa_number']}\n"
                    f"<b>Reference:</b> <code>{withdrawal['withdrawal_id']}</code>\n\n"
                    "💸 Funds are being sent to your M-Pesa number.\n\n"
                    "You should receive the money within a few minutes.\n"
                    "Check your phone for the M-Pesa confirmation message.\n\n"
                    "Thank you for using our platform!",
                    parse_mode=ParseMode.HTML
                )

                logger.info(f"Withdrawal processed for seller {seller_id}, amount: {amount}")

            except Exception as e:
                logger.error(f"B2C withdrawal failed for seller {seller_id}: {e}", exc_info=True)
                await query.edit_message_text(
                    "❌ <b>Withdrawal Failed</b>\n\n"
                    f"Error: {str(e)}\n\n"
                    "Please try again or contact support if the problem persists.",
                    parse_mode=ParseMode.HTML
                )

        # Withdrawal cancellation
        elif data == "withdraw_cancel":
            await query.edit_message_text(
                "✅ <b>Withdrawal Cancelled</b>\n\n"
                "Your withdrawal has been cancelled.\n"
                "Funds remain in your account.\n\n"
                "Use /withdraw when you're ready to withdraw.",
                parse_mode=ParseMode.HTML
            )

        # Withdrawal confirmation (shows confirmation message)
        elif data == "withdraw_confirm":
            seller = await get_seller_by_user_id(user.id)
            if not seller:
                await query.answer("Error: Seller not found", show_alert=True)
                return

            stats = await get_seller_statistics(seller['seller_id'])
            available_balance = Decimal(str(stats['available_balance']))

            keyboard = [
                [
                    InlineKeyboardButton(
                        "✅ Confirm",
                        callback_data=f"withdraw_execute:{seller['seller_id']}"
                    ),
                    InlineKeyboardButton(
                        "❌ Cancel",
                        callback_data="withdraw_cancel"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.message.reply_text(
                f"💸 <b>Confirm Withdrawal</b>\n\n"
                f"Amount: KES {available_balance:,}\n"
                f"To: {seller['mpesa_number']}\n\n"
                f"Proceed?",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

    except Exception as e:
        logger.error(f"Error in seller_button_callback: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ <b>Error</b>\n\n"
            "An unexpected error occurred. Please try again.",
            parse_mode=ParseMode.HTML
        )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'register_seller',
    'my_sales',
    'mark_shipped',
    'request_release',
    'seller_stats',
    'withdraw',
    'seller_help',
    'seller_button_callback',
    'seller_only',
    'rate_limit'
]
