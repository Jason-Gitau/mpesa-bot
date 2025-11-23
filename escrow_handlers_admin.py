"""
Escrow Admin Command Handlers for M-Pesa Bot

This module contains admin-only command handlers for managing the escrow system:
- Seller verification
- Dispute resolution
- Transaction management
- System monitoring
- Fraud detection

Dependencies:
    - escrow_service.py: For escrow business logic
    - telegram: For bot interactions
    - database.py: For database operations
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from decimal import Decimal

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from escrow_service import get_escrow_service, EscrowError, EscrowService
from database import get_database
from utils import format_currency, sanitize_input, format_datetime
from config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load configuration
try:
    config = get_config()
    ADMIN_USER_IDS = [int(id.strip()) for id in config.admin_chat_id.split(',') if id.strip()]
except Exception:
    logger.warning("Admin user IDs not configured properly")
    ADMIN_USER_IDS = []


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


@admin_only
async def verify_seller(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /verify_seller command - Verify pending seller.

    Usage: /verify_seller <seller_id>

    Args:
        update: Telegram update object
        context: Callback context
    """
    user = update.effective_user

    try:
        if len(context.args) != 1:
            await update.message.reply_text(
                "❌ <b>Invalid Format</b>\n\n"
                "Usage: /verify_seller &lt;seller_id&gt;\n"
                "Example: /verify_seller 123",
                parse_mode=ParseMode.HTML
            )
            return

        seller_id = int(sanitize_input(context.args[0]))

        # Get escrow service
        db = await get_database()
        escrow_service = await get_escrow_service(db.pool)

        # Verify seller
        seller = await escrow_service.verify_seller(seller_id)

        await update.message.reply_text(
            "✅ <b>Seller Verified</b>\n\n"
            f"<b>Seller ID:</b> {seller['id']}\n"
            f"<b>User ID:</b> {seller['user_id']}\n"
            f"<b>Username:</b> {seller['username']}\n"
            f"<b>Business:</b> {seller.get('business_name', 'N/A')}\n"
            f"<b>Status:</b> ✅ Verified\n"
            f"<b>Verified At:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "The seller can now accept escrow payments.",
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Admin {user.id} verified seller {seller_id}")

    except ValueError:
        await update.message.reply_text(
            "❌ <b>Invalid Input</b>\n\nSeller ID must be a number.",
            parse_mode=ParseMode.HTML
        )
    except EscrowError as e:
        await update.message.reply_text(
            f"❌ <b>Error</b>\n\n{str(e)}",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error in verify_seller command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>System Error</b>\n\nFailed to verify seller. Please try again.",
            parse_mode=ParseMode.HTML
        )


@admin_only
async def suspend_seller(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /suspend_seller command - Suspend seller account.

    Usage: /suspend_seller <seller_id> <reason>

    Args:
        update: Telegram update object
        context: Callback context
    """
    user = update.effective_user

    try:
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ <b>Invalid Format</b>\n\n"
                "Usage: /suspend_seller &lt;seller_id&gt; &lt;reason&gt;\n"
                "Example: /suspend_seller 123 Multiple fraud reports",
                parse_mode=ParseMode.HTML
            )
            return

        seller_id = int(sanitize_input(context.args[0]))
        reason = ' '.join(context.args[1:])

        # Get escrow service
        db = await get_database()
        escrow_service = await get_escrow_service(db.pool)

        # Suspend seller
        seller = await escrow_service.suspend_seller(seller_id, reason)

        await update.message.reply_text(
            "🚫 <b>Seller Suspended</b>\n\n"
            f"<b>Seller ID:</b> {seller['id']}\n"
            f"<b>User ID:</b> {seller['user_id']}\n"
            f"<b>Username:</b> {seller['username']}\n"
            f"<b>Status:</b> 🚫 Suspended\n"
            f"<b>Reason:</b> {reason}\n"
            f"<b>Suspended At:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "The seller can no longer accept new escrow transactions.",
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Admin {user.id} suspended seller {seller_id}: {reason}")

    except ValueError:
        await update.message.reply_text(
            "❌ <b>Invalid Input</b>\n\nSeller ID must be a number.",
            parse_mode=ParseMode.HTML
        )
    except EscrowError as e:
        await update.message.reply_text(
            f"❌ <b>Error</b>\n\n{str(e)}",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error in suspend_seller command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>System Error</b>\n\nFailed to suspend seller. Please try again.",
            parse_mode=ParseMode.HTML
        )


@admin_only
async def resolve_dispute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /resolve_dispute command - Resolve escrow dispute.

    Usage: /resolve_dispute <transaction_id> <decision:buyer/seller/split> <notes>

    Args:
        update: Telegram update object
        context: Callback context
    """
    user = update.effective_user

    try:
        if len(context.args) < 3:
            await update.message.reply_text(
                "❌ <b>Invalid Format</b>\n\n"
                "Usage: /resolve_dispute &lt;transaction_id&gt; &lt;buyer/seller/split&gt; &lt;notes&gt;\n\n"
                "Examples:\n"
                "• /resolve_dispute TXN123 buyer Product never received\n"
                "• /resolve_dispute TXN456 seller Delivered with proof\n"
                "• /resolve_dispute TXN789 split Both parties agree to split",
                parse_mode=ParseMode.HTML
            )
            return

        transaction_id = sanitize_input(context.args[0])
        decision = sanitize_input(context.args[1]).lower()
        notes = ' '.join(context.args[2:])

        if decision not in ['buyer', 'seller', 'split']:
            await update.message.reply_text(
                "❌ <b>Invalid Decision</b>\n\n"
                "Decision must be one of: buyer, seller, split",
                parse_mode=ParseMode.HTML
            )
            return

        # Get escrow service
        db = await get_database()
        escrow_service = await get_escrow_service(db.pool)

        # Get dispute from transaction
        async with db.pool.acquire() as conn:
            dispute = await conn.fetchrow(
                """
                SELECT d.* FROM escrow_disputes d
                JOIN escrow_transactions t ON d.transaction_id = t.id
                WHERE t.transaction_id = $1 AND d.status IN ('open', 'under_review')
                ORDER BY d.created_at DESC
                LIMIT 1
                """,
                transaction_id
            )

            if not dispute:
                await update.message.reply_text(
                    f"❌ <b>Dispute Not Found</b>\n\n"
                    f"No active dispute found for transaction: {transaction_id}",
                    parse_mode=ParseMode.HTML
                )
                return

        # Resolve dispute
        resolved_dispute = await escrow_service.resolve_dispute(
            dispute['id'], decision, notes, user.id
        )

        decision_emoji = {
            'buyer': '👤',
            'seller': '🏪',
            'split': '⚖️'
        }

        await update.message.reply_text(
            "✅ <b>Dispute Resolved</b>\n\n"
            f"<b>Transaction ID:</b> <code>{transaction_id}</code>\n"
            f"<b>Dispute ID:</b> {resolved_dispute['id']}\n"
            f"<b>Decision:</b> {decision_emoji.get(decision, '•')} {decision.upper()}\n"
            f"<b>Resolution Notes:</b> {notes}\n"
            f"<b>Resolved By:</b> Admin {user.id}\n"
            f"<b>Resolved At:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"{'💰 Funds refunded to buyer' if decision == 'buyer' else ''}"
            f"{'💰 Funds released to seller' if decision == 'seller' else ''}"
            f"{'💰 Funds split between both parties' if decision == 'split' else ''}",
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Admin {user.id} resolved dispute {resolved_dispute['id']}: {decision}")

    except EscrowError as e:
        await update.message.reply_text(
            f"❌ <b>Error</b>\n\n{str(e)}",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error in resolve_dispute command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>System Error</b>\n\nFailed to resolve dispute. Please try again.",
            parse_mode=ParseMode.HTML
        )


@admin_only
async def escrow_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /escrow_dashboard command - Show system overview.

    Args:
        update: Telegram update object
        context: Callback context
    """
    try:
        # Get escrow service
        db = await get_database()
        escrow_service = await get_escrow_service(db.pool)

        # Get dashboard stats
        stats = await escrow_service.get_escrow_dashboard_stats()

        # Additional stats
        async with db.pool.acquire() as conn:
            seller_stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total_sellers,
                    COUNT(*) FILTER (WHERE status = 'verified') as verified_sellers,
                    COUNT(*) FILTER (WHERE status = 'pending') as pending_sellers,
                    COUNT(*) FILTER (WHERE status = 'suspended') as suspended_sellers
                FROM escrow_sellers
                """
            )

        dashboard_text = (
            "📊 <b>Escrow System Dashboard</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "<b>💰 Financial Overview (30 Days):</b>\n"
            f"• Total Held: KES {format_currency(stats['total_held'])}\n"
            f"• Total Released: KES {format_currency(stats['total_released'])}\n"
            f"• Total Refunded: KES {format_currency(stats['total_refunded'])}\n\n"

            "<b>📦 Transactions:</b>\n"
            f"• Total: {stats['total_transactions']}\n"
            f"• In Escrow: {stats['held_count']}\n"
            f"• Completed: {stats['completed_count']}\n"
            f"• Disputed: {stats['disputed_count']}\n\n"

            "<b>🏪 Sellers:</b>\n"
            f"• Total: {seller_stats['total_sellers']}\n"
            f"• Verified: {seller_stats['verified_sellers']}\n"
            f"• Pending: {seller_stats['pending_sellers']}\n"
            f"• Suspended: {seller_stats['suspended_sellers']}\n\n"

            f"<b>Last Updated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

            "<b>Quick Actions:</b>\n"
            "• /disputed_transactions - View disputes\n"
            "• /suspicious_users - Check fraud flags\n"
            "• /system_health - System health check"
        )

        await update.message.reply_text(
            dashboard_text,
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Admin {update.effective_user.id} viewed escrow dashboard")

    except Exception as e:
        logger.error(f"Error in escrow_dashboard command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>System Error</b>\n\nFailed to load dashboard. Please try again.",
            parse_mode=ParseMode.HTML
        )


@admin_only
async def disputed_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /disputed_transactions command - View all disputes.

    Args:
        update: Telegram update object
        context: Callback context
    """
    try:
        # Get escrow service
        db = await get_database()
        escrow_service = await get_escrow_service(db.pool)

        # Get disputed transactions
        disputes = await escrow_service.get_disputed_transactions(limit=20)

        if not disputes:
            await update.message.reply_text(
                "✅ <b>No Active Disputes</b>\n\n"
                "There are currently no open disputes in the system.",
                parse_mode=ParseMode.HTML
            )
            return

        disputes_text = (
            f"⚠️ <b>Active Disputes ({len(disputes)})</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        for i, dispute in enumerate(disputes[:10], 1):
            status_emoji = {'open': '🔴', 'under_review': '🟡'}.get(dispute['status'], '⚪')

            disputes_text += (
                f"<b>{i}. {status_emoji} Dispute #{dispute['id']}</b>\n"
                f"   Transaction: <code>{dispute['transaction_id']}</code>\n"
                f"   Amount: KES {format_currency(float(dispute['amount']))}\n"
                f"   Raised by: {dispute['raised_by'].upper()}\n"
                f"   Reason: {dispute['reason']}\n"
                f"   Created: {dispute['created_at'].strftime('%Y-%m-%d %H:%M')}\n\n"
            )

        disputes_text += (
            "\n<b>To resolve a dispute:</b>\n"
            "/resolve_dispute &lt;txn_id&gt; &lt;buyer/seller/split&gt; &lt;notes&gt;"
        )

        await update.message.reply_text(
            disputes_text,
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Admin {update.effective_user.id} viewed disputed transactions")

    except Exception as e:
        logger.error(f"Error in disputed_transactions command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>System Error</b>\n\nFailed to load disputes. Please try again.",
            parse_mode=ParseMode.HTML
        )


@admin_only
async def suspicious_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /suspicious_users command - View flagged users.

    Args:
        update: Telegram update object
        context: Callback context
    """
    try:
        # Get escrow service
        db = await get_database()
        escrow_service = await get_escrow_service(db.pool)

        # Get suspicious users
        flags = await escrow_service.get_suspicious_users()

        if not flags:
            await update.message.reply_text(
                "✅ <b>No Suspicious Activity</b>\n\n"
                "No unreviewed fraud flags in the system.",
                parse_mode=ParseMode.HTML
            )
            return

        flags_text = (
            f"🚨 <b>Suspicious Users ({len(flags)})</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        for i, flag in enumerate(flags[:15], 1):
            severity_emoji = {
                'low': '🟢',
                'medium': '🟡',
                'high': '🟠',
                'critical': '🔴'
            }.get(flag['severity'], '⚪')

            flags_text += (
                f"<b>{i}. {severity_emoji} {flag['severity'].upper()}</b>\n"
                f"   User ID: {flag['user_id']} ({flag['user_type']})\n"
                f"   Flag: {flag['flag_type']}\n"
                f"   Details: {flag['description'][:100]}...\n"
                f"   Flagged: {flag['created_at'].strftime('%Y-%m-%d %H:%M')}\n\n"
            )

        await update.message.reply_text(
            flags_text,
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Admin {update.effective_user.id} viewed suspicious users")

    except Exception as e:
        logger.error(f"Error in suspicious_users command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>System Error</b>\n\nFailed to load fraud flags. Please try again.",
            parse_mode=ParseMode.HTML
        )


@admin_only
async def freeze_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /freeze_transaction command - Manually freeze transaction.

    Usage: /freeze_transaction <transaction_id>

    Args:
        update: Telegram update object
        context: Callback context
    """
    user = update.effective_user

    try:
        if len(context.args) != 1:
            await update.message.reply_text(
                "❌ <b>Invalid Format</b>\n\n"
                "Usage: /freeze_transaction &lt;transaction_id&gt;\n"
                "Example: /freeze_transaction TXN123456",
                parse_mode=ParseMode.HTML
            )
            return

        transaction_id = sanitize_input(context.args[0])

        # Get escrow service
        db = await get_database()
        escrow_service = await get_escrow_service(db.pool)

        # Freeze transaction
        txn = await escrow_service.freeze_transaction(transaction_id)

        await update.message.reply_text(
            "❄️ <b>Transaction Frozen</b>\n\n"
            f"<b>Transaction ID:</b> <code>{txn['transaction_id']}</code>\n"
            f"<b>Amount:</b> KES {format_currency(float(txn['amount']))}\n"
            f"<b>Status:</b> ❄️ FROZEN\n"
            f"<b>Frozen By:</b> Admin {user.id}\n"
            f"<b>Frozen At:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "⚠️ No automated actions will be performed on this transaction.\n"
            "Manual intervention required to unfreeze.",
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Admin {user.id} froze transaction {transaction_id}")

    except EscrowError as e:
        await update.message.reply_text(
            f"❌ <b>Error</b>\n\n{str(e)}",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error in freeze_transaction command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>System Error</b>\n\nFailed to freeze transaction. Please try again.",
            parse_mode=ParseMode.HTML
        )


@admin_only
async def manual_refund(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /manual_refund command - Force refund to buyer.

    Usage: /manual_refund <transaction_id>

    Args:
        update: Telegram update object
        context: Callback context
    """
    user = update.effective_user

    try:
        if len(context.args) < 1:
            await update.message.reply_text(
                "❌ <b>Invalid Format</b>\n\n"
                "Usage: /manual_refund &lt;transaction_id&gt; [reason]\n"
                "Example: /manual_refund TXN123456 Admin override",
                parse_mode=ParseMode.HTML
            )
            return

        transaction_id = sanitize_input(context.args[0])
        reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "Manual admin refund"

        # Get escrow service
        db = await get_database()
        escrow_service = await get_escrow_service(db.pool)

        # Refund buyer
        txn = await escrow_service.refund_buyer(transaction_id, reason)

        await update.message.reply_text(
            "💸 <b>Manual Refund Processed</b>\n\n"
            f"<b>Transaction ID:</b> <code>{txn['transaction_id']}</code>\n"
            f"<b>Refund Amount:</b> KES {format_currency(float(txn['refund_amount']))}\n"
            f"<b>Reason:</b> {reason}\n"
            f"<b>Processed By:</b> Admin {user.id}\n"
            f"<b>Processed At:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "✅ Buyer has been refunded successfully.",
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Admin {user.id} manually refunded transaction {transaction_id}")

    except EscrowError as e:
        await update.message.reply_text(
            f"❌ <b>Error</b>\n\n{str(e)}",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error in manual_refund command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>System Error</b>\n\nFailed to process refund. Please try again.",
            parse_mode=ParseMode.HTML
        )


@admin_only
async def manual_release(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /manual_release command - Force release to seller.

    Usage: /manual_release <transaction_id>

    Args:
        update: Telegram update object
        context: Callback context
    """
    user = update.effective_user

    try:
        if len(context.args) != 1:
            await update.message.reply_text(
                "❌ <b>Invalid Format</b>\n\n"
                "Usage: /manual_release &lt;transaction_id&gt;\n"
                "Example: /manual_release TXN123456",
                parse_mode=ParseMode.HTML
            )
            return

        transaction_id = sanitize_input(context.args[0])

        # Get escrow service
        db = await get_database()
        escrow_service = await get_escrow_service(db.pool)

        # Release payment
        txn = await escrow_service.release_payment(transaction_id)

        await update.message.reply_text(
            "💰 <b>Manual Release Processed</b>\n\n"
            f"<b>Transaction ID:</b> <code>{txn['transaction_id']}</code>\n"
            f"<b>Release Amount:</b> KES {format_currency(float(txn['release_amount']))}\n"
            f"<b>Released By:</b> Admin {user.id}\n"
            f"<b>Released At:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "✅ Payment released to seller successfully.",
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Admin {user.id} manually released transaction {transaction_id}")

    except EscrowError as e:
        await update.message.reply_text(
            f"❌ <b>Error</b>\n\n{str(e)}",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error in manual_release command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>System Error</b>\n\nFailed to release payment. Please try again.",
            parse_mode=ParseMode.HTML
        )


@admin_only
async def system_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /system_health command - Escrow system health check.

    Args:
        update: Telegram update object
        context: Callback context
    """
    try:
        # Get database
        db = await get_database()
        escrow_service = await get_escrow_service(db.pool)

        # Check database connection
        db_status = "✅"
        try:
            async with db.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
        except Exception:
            db_status = "❌"

        # Get system stats
        async with db.pool.acquire() as conn:
            # Check for stuck transactions
            stuck_txns = await conn.fetchval(
                """
                SELECT COUNT(*) FROM escrow_transactions
                WHERE status = 'held'
                AND created_at < CURRENT_TIMESTAMP - INTERVAL '7 days'
                """
            )

            # Check for old unresolved disputes
            old_disputes = await conn.fetchval(
                """
                SELECT COUNT(*) FROM escrow_disputes
                WHERE status IN ('open', 'under_review')
                AND created_at < CURRENT_TIMESTAMP - INTERVAL '14 days'
                """
            )

            # Check for high-severity fraud flags
            critical_flags = await conn.fetchval(
                """
                SELECT COUNT(*) FROM fraud_flags
                WHERE severity = 'critical' AND reviewed = FALSE
                """
            )

        # Determine overall health
        issues = []
        if stuck_txns > 0:
            issues.append(f"⚠️ {stuck_txns} stuck transactions (>7 days)")
        if old_disputes > 0:
            issues.append(f"⚠️ {old_disputes} old disputes (>14 days)")
        if critical_flags > 0:
            issues.append(f"🚨 {critical_flags} critical fraud flags")

        overall_status = "✅ HEALTHY" if not issues else "⚠️ NEEDS ATTENTION"

        health_text = (
            "🏥 <b>Escrow System Health Check</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            f"<b>Overall Status:</b> {overall_status}\n\n"

            "<b>Component Status:</b>\n"
            f"• Database: {db_status}\n"
            f"• Escrow Service: ✅\n\n"

            "<b>System Metrics:</b>\n"
            f"• Stuck Transactions: {stuck_txns}\n"
            f"• Old Disputes: {old_disputes}\n"
            f"• Critical Flags: {critical_flags}\n\n"
        )

        if issues:
            health_text += "<b>⚠️ Issues Detected:</b>\n"
            for issue in issues:
                health_text += f"{issue}\n"
        else:
            health_text += "✅ <b>No issues detected</b>\n"

        health_text += f"\n<b>Last Checked:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        await update.message.reply_text(
            health_text,
            parse_mode=ParseMode.HTML
        )

        logger.info(f"Admin {update.effective_user.id} checked system health")

    except Exception as e:
        logger.error(f"Error in system_health command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ <b>Health Check Failed</b>\n\n"
            "Unable to perform system health check. This may indicate a serious issue.\n"
            "Please check system logs.",
            parse_mode=ParseMode.HTML
        )


# Export all handlers
__all__ = [
    'verify_seller',
    'suspend_seller',
    'resolve_dispute',
    'escrow_dashboard',
    'disputed_transactions',
    'suspicious_users',
    'freeze_transaction',
    'manual_refund',
    'manual_release',
    'system_health'
]
