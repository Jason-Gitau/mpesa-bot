"""
Escrow Automation Module for M-Pesa Bot

This module handles background automation tasks for the escrow system:
- Auto-release payments after 7 days
- Auto-refund for unshipped orders
- Reminder notifications
- Seller rating calculations
- Fraud pattern detection
- Transaction cleanup

Dependencies:
    - APScheduler: For background job scheduling
    - escrow_service.py: For escrow operations
    - telegram: For sending notifications
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from decimal import Decimal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from telegram import Bot
from telegram.constants import ParseMode

from escrow_service import get_escrow_service, EscrowError
from database import get_database
from utils import format_currency
from config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EscrowAutomation:
    """
    Automation service for escrow system.

    Handles all scheduled background tasks including:
    - Payment releases
    - Refunds
    - Notifications
    - Fraud detection
    - Data cleanup
    """

    def __init__(self, bot: Bot):
        """
        Initialize escrow automation service.

        Args:
            bot: Telegram bot instance for sending notifications
        """
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.config = get_config()
        self.is_running = False

        # Statistics
        self.stats = {
            'auto_releases': 0,
            'auto_refunds': 0,
            'reminders_sent': 0,
            'fraud_flags': 0,
            'last_run': {}
        }

    async def start(self) -> None:
        """Start the automation scheduler."""
        if self.is_running:
            logger.warning("Automation scheduler already running")
            return

        try:
            # Initialize database and escrow service
            db = await get_database()
            escrow_service = await get_escrow_service(db.pool)

            # Schedule tasks
            self._schedule_tasks()

            # Start scheduler
            self.scheduler.start()
            self.is_running = True

            logger.info("Escrow automation started successfully")
            logger.info(f"Scheduled jobs: {len(self.scheduler.get_jobs())}")

        except Exception as e:
            logger.error(f"Failed to start automation: {e}", exc_info=True)
            raise

    async def stop(self) -> None:
        """Stop the automation scheduler."""
        if not self.is_running:
            return

        self.scheduler.shutdown()
        self.is_running = False
        logger.info("Escrow automation stopped")

    def _schedule_tasks(self) -> None:
        """Schedule all automation tasks."""

        # Auto-release payments - Every 1 hour
        self.scheduler.add_job(
            self.auto_release_payments,
            trigger=IntervalTrigger(hours=1),
            id='auto_release_payments',
            name='Auto Release Payments',
            max_instances=1,
            misfire_grace_time=300
        )

        # Auto-refund unshipped - Every 6 hours
        self.scheduler.add_job(
            self.auto_refund_unshipped,
            trigger=IntervalTrigger(hours=6),
            id='auto_refund_unshipped',
            name='Auto Refund Unshipped',
            max_instances=1,
            misfire_grace_time=300
        )

        # Send reminder notifications - Every 12 hours at 9 AM and 9 PM
        self.scheduler.add_job(
            self.send_reminder_notifications,
            trigger=CronTrigger(hour='9,21', minute=0),
            id='send_reminders',
            name='Send Reminder Notifications',
            max_instances=1
        )

        # Calculate seller ratings - Daily at midnight
        self.scheduler.add_job(
            self.calculate_seller_ratings,
            trigger=CronTrigger(hour=0, minute=0),
            id='calculate_ratings',
            name='Calculate Seller Ratings',
            max_instances=1
        )

        # Detect fraud patterns - Daily at 2 AM
        self.scheduler.add_job(
            self.detect_fraud_patterns,
            trigger=CronTrigger(hour=2, minute=0),
            id='detect_fraud',
            name='Detect Fraud Patterns',
            max_instances=1
        )

        # Cleanup expired transactions - Weekly on Sunday at 3 AM
        self.scheduler.add_job(
            self.cleanup_expired_transactions,
            trigger=CronTrigger(day_of_week='sun', hour=3, minute=0),
            id='cleanup_transactions',
            name='Cleanup Expired Transactions',
            max_instances=1
        )

        logger.info("All automation tasks scheduled")

    async def auto_release_payments(self) -> None:
        """
        Auto-release payments after 7 days if no dispute.

        Process:
        1. Find transactions in SHIPPED state for 7+ days
        2. Check no active disputes
        3. Automatically release to seller
        4. Notify both parties
        5. Update transaction timeline
        """
        logger.info("Starting auto-release payments task")
        start_time = datetime.now()

        try:
            db = await get_database()
            escrow_service = await get_escrow_service(db.pool)

            # Get eligible transactions
            candidates = await escrow_service.get_auto_release_candidates()

            logger.info(f"Found {len(candidates)} transactions eligible for auto-release")

            released_count = 0
            failed_count = 0

            for txn in candidates:
                try:
                    # Release payment
                    await escrow_service.release_payment(txn['transaction_id'])

                    # Notify buyer
                    buyer_message = (
                        "✅ <b>Payment Auto-Released</b>\n\n"
                        f"<b>Transaction ID:</b> <code>{txn['transaction_id']}</code>\n"
                        f"<b>Amount:</b> KES {format_currency(float(txn['amount']))}\n\n"
                        "The 7-day dispute period has passed.\n"
                        "Payment has been automatically released to the seller.\n\n"
                        "Thank you for using our escrow service!"
                    )

                    await self.bot.send_message(
                        chat_id=txn['buyer_id'],
                        text=buyer_message,
                        parse_mode=ParseMode.HTML
                    )

                    # Notify seller
                    seller_message = (
                        "💰 <b>Payment Received</b>\n\n"
                        f"<b>Transaction ID:</b> <code>{txn['transaction_id']}</code>\n"
                        f"<b>Amount:</b> KES {format_currency(float(txn['amount']))}\n\n"
                        "Funds have been automatically released from escrow.\n"
                        "The transaction is now complete.\n\n"
                        "Thank you for your business!"
                    )

                    # Get seller info
                    async with db.pool.acquire() as conn:
                        seller = await conn.fetchrow(
                            "SELECT user_id FROM escrow_sellers WHERE id = $1",
                            txn['seller_id']
                        )

                    if seller:
                        await self.bot.send_message(
                            chat_id=seller['user_id'],
                            text=seller_message,
                            parse_mode=ParseMode.HTML
                        )

                    released_count += 1
                    logger.info(f"Auto-released payment: {txn['transaction_id']}")

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to auto-release {txn['transaction_id']}: {e}")

            # Update statistics
            self.stats['auto_releases'] += released_count
            self.stats['last_run']['auto_release'] = datetime.now()

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"Auto-release task completed: {released_count} released, "
                f"{failed_count} failed in {duration:.2f}s"
            )

        except Exception as e:
            logger.error(f"Auto-release payments task failed: {e}", exc_info=True)

    async def auto_refund_unshipped(self) -> None:
        """
        Auto-refund if seller doesn't ship in 3 days.

        Process:
        1. Check transactions in HELD state for 3+ days
        2. No shipping confirmation
        3. Auto-refund to buyer
        4. Notify both parties
        5. Flag seller for review
        """
        logger.info("Starting auto-refund unshipped task")
        start_time = datetime.now()

        try:
            db = await get_database()
            escrow_service = await get_escrow_service(db.pool)

            # Get unshipped transactions (3+ days old)
            unshipped = await escrow_service.get_unshipped_transactions(days=3)

            logger.info(f"Found {len(unshipped)} unshipped transactions")

            refunded_count = 0
            failed_count = 0

            for txn in unshipped:
                try:
                    # Refund buyer
                    reason = "Seller failed to ship within 3 days - Auto-refunded"
                    await escrow_service.refund_buyer(
                        txn['transaction_id'],
                        reason
                    )

                    # Notify buyer
                    buyer_message = (
                        "💸 <b>Automatic Refund Issued</b>\n\n"
                        f"<b>Transaction ID:</b> <code>{txn['transaction_id']}</code>\n"
                        f"<b>Refund Amount:</b> KES {format_currency(float(txn['amount']))}\n\n"
                        "The seller did not ship your order within 3 days.\n"
                        "Your payment has been automatically refunded.\n\n"
                        "You can place a new order with a different seller."
                    )

                    await self.bot.send_message(
                        chat_id=txn['buyer_id'],
                        text=buyer_message,
                        parse_mode=ParseMode.HTML
                    )

                    # Notify seller and flag for review
                    seller_message = (
                        "⚠️ <b>Transaction Auto-Refunded</b>\n\n"
                        f"<b>Transaction ID:</b> <code>{txn['transaction_id']}</code>\n"
                        f"<b>Amount:</b> KES {format_currency(float(txn['amount']))}\n\n"
                        "This order was not shipped within 3 days.\n"
                        "The buyer has been automatically refunded.\n\n"
                        "⚠️ Your account has been flagged for review.\n"
                        "Multiple violations may result in suspension."
                    )

                    # Get seller info and send notification
                    async with db.pool.acquire() as conn:
                        seller = await conn.fetchrow(
                            "SELECT * FROM escrow_sellers WHERE id = $1",
                            txn['seller_id']
                        )

                    if seller:
                        await self.bot.send_message(
                            chat_id=seller['user_id'],
                            text=seller_message,
                            parse_mode=ParseMode.HTML
                        )

                        # Flag seller
                        await escrow_service.flag_suspicious_activity(
                            user_id=seller['user_id'],
                            user_type='seller',
                            flag_type='unshipped_order',
                            description=f"Failed to ship order {txn['transaction_id']} within 3 days",
                            severity='medium'
                        )

                    refunded_count += 1
                    logger.info(f"Auto-refunded unshipped order: {txn['transaction_id']}")

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to auto-refund {txn['transaction_id']}: {e}")

            # Update statistics
            self.stats['auto_refunds'] += refunded_count
            self.stats['last_run']['auto_refund'] = datetime.now()

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"Auto-refund task completed: {refunded_count} refunded, "
                f"{failed_count} failed in {duration:.2f}s"
            )

        except Exception as e:
            logger.error(f"Auto-refund unshipped task failed: {e}", exc_info=True)

    async def send_reminder_notifications(self) -> None:
        """
        Send reminder notifications to users.

        Reminders:
        - Buyers: "Confirm delivery" (day 5, 6)
        - Sellers: "Ship your order" (day 1, 2)
        - Auto-release warnings (day 6)
        """
        logger.info("Starting reminder notifications task")
        start_time = datetime.now()

        try:
            db = await get_database()

            reminders_sent = 0

            async with db.pool.acquire() as conn:
                # Buyer reminders: Confirm delivery (days 5-6 in SHIPPED status)
                buyer_reminders = await conn.fetch(
                    """
                    SELECT *
                    FROM escrow_transactions
                    WHERE status = 'shipped'
                    AND updated_at BETWEEN
                        CURRENT_TIMESTAMP - INTERVAL '6 days' AND
                        CURRENT_TIMESTAMP - INTERVAL '5 days'
                    """
                )

                for txn in buyer_reminders:
                    try:
                        days_left = 7 - (datetime.now() - txn['updated_at']).days

                        message = (
                            "📦 <b>Delivery Confirmation Reminder</b>\n\n"
                            f"<b>Transaction ID:</b> <code>{txn['transaction_id']}</code>\n"
                            f"<b>Amount:</b> KES {format_currency(float(txn['amount']))}\n\n"
                            "Your order was marked as shipped.\n"
                            f"⏰ Payment will auto-release in {days_left} day(s)\n\n"
                            "If you haven't received your order or there's an issue:\n"
                            "• Raise a dispute immediately\n"
                            "• Contact the seller\n\n"
                            "Otherwise, payment will automatically release to the seller."
                        )

                        await self.bot.send_message(
                            chat_id=txn['buyer_id'],
                            text=message,
                            parse_mode=ParseMode.HTML
                        )

                        reminders_sent += 1

                    except Exception as e:
                        logger.error(f"Failed to send buyer reminder: {e}")

                # Seller reminders: Ship order (days 1-2 in HELD status)
                seller_reminders = await conn.fetch(
                    """
                    SELECT t.*, s.user_id as seller_user_id
                    FROM escrow_transactions t
                    JOIN escrow_sellers s ON t.seller_id = s.id
                    WHERE t.status = 'held'
                    AND t.created_at BETWEEN
                        CURRENT_TIMESTAMP - INTERVAL '2 days' AND
                        CURRENT_TIMESTAMP - INTERVAL '1 day'
                    """
                )

                for txn in seller_reminders:
                    try:
                        days_left = 3 - (datetime.now() - txn['created_at']).days

                        message = (
                            "📦 <b>Shipping Reminder</b>\n\n"
                            f"<b>Transaction ID:</b> <code>{txn['transaction_id']}</code>\n"
                            f"<b>Amount:</b> KES {format_currency(float(txn['amount']))}\n\n"
                            "⚠️ Please ship this order!\n"
                            f"⏰ Auto-refund in {days_left} day(s) if not shipped\n\n"
                            "To avoid automatic refund:\n"
                            "1. Ship the order\n"
                            "2. Update the tracking information\n"
                            "3. Mark as shipped in the system\n\n"
                            "Use: /mark_shipped <transaction_id> <tracking>"
                        )

                        await self.bot.send_message(
                            chat_id=txn['seller_user_id'],
                            text=message,
                            parse_mode=ParseMode.HTML
                        )

                        reminders_sent += 1

                    except Exception as e:
                        logger.error(f"Failed to send seller reminder: {e}")

            # Update statistics
            self.stats['reminders_sent'] += reminders_sent
            self.stats['last_run']['reminders'] = datetime.now()

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"Reminder notifications completed: {reminders_sent} sent in {duration:.2f}s"
            )

        except Exception as e:
            logger.error(f"Reminder notifications task failed: {e}", exc_info=True)

    async def calculate_seller_ratings(self) -> None:
        """
        Update seller ratings.

        Process:
        - Calculate average buyer ratings
        - Update seller level/badges
        - Factor in dispute rate
        - Update success rate
        """
        logger.info("Starting seller ratings calculation task")
        start_time = datetime.now()

        try:
            db = await get_database()
            escrow_service = await get_escrow_service(db.pool)

            async with db.pool.acquire() as conn:
                # Get all sellers
                sellers = await conn.fetch("SELECT * FROM escrow_sellers")

                updated_count = 0

                for seller in sellers:
                    try:
                        # Update ratings
                        await escrow_service.update_seller_ratings(seller['id'])

                        # Calculate success rate
                        stats = await conn.fetchrow(
                            """
                            SELECT
                                COUNT(*) as total,
                                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                                COUNT(*) FILTER (WHERE status = 'disputed') as disputed
                            FROM escrow_transactions
                            WHERE seller_id = $1
                            """,
                            seller['id']
                        )

                        if stats['total'] > 0:
                            success_rate = (stats['completed'] / stats['total']) * 100

                            await conn.execute(
                                """
                                UPDATE escrow_sellers
                                SET success_rate = $2,
                                    total_sales = $3,
                                    total_disputes = $4,
                                    updated_at = CURRENT_TIMESTAMP
                                WHERE id = $1
                                """,
                                seller['id'],
                                success_rate,
                                stats['total'],
                                stats['disputed']
                            )

                        updated_count += 1

                    except Exception as e:
                        logger.error(f"Failed to update seller {seller['id']}: {e}")

            # Update statistics
            self.stats['last_run']['ratings'] = datetime.now()

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"Seller ratings calculation completed: {updated_count} sellers updated "
                f"in {duration:.2f}s"
            )

        except Exception as e:
            logger.error(f"Seller ratings calculation task failed: {e}", exc_info=True)

    async def detect_fraud_patterns(self) -> None:
        """
        Detect fraud patterns.

        Patterns:
        - Multiple disputes from same buyer
        - Seller with high dispute rate (>30%)
        - Unusual transaction patterns
        - Repeated refunds
        """
        logger.info("Starting fraud detection task")
        start_time = datetime.now()

        try:
            db = await get_database()
            escrow_service = await get_escrow_service(db.pool)

            flags_created = 0

            async with db.pool.acquire() as conn:
                # Pattern 1: Buyers with multiple disputes (3+ in 30 days)
                repeat_disputers = await conn.fetch(
                    """
                    SELECT buyer_id, COUNT(*) as dispute_count
                    FROM escrow_transactions
                    WHERE status = 'disputed'
                    AND created_at > CURRENT_TIMESTAMP - INTERVAL '30 days'
                    GROUP BY buyer_id
                    HAVING COUNT(*) >= 3
                    """
                )

                for buyer in repeat_disputers:
                    try:
                        await escrow_service.flag_suspicious_activity(
                            user_id=buyer['buyer_id'],
                            user_type='buyer',
                            flag_type='multiple_disputes',
                            description=f"Raised {buyer['dispute_count']} disputes in 30 days",
                            severity='high'
                        )
                        flags_created += 1
                    except Exception as e:
                        logger.error(f"Failed to flag buyer {buyer['buyer_id']}: {e}")

                # Pattern 2: Sellers with high dispute rate (>30%)
                high_dispute_sellers = await conn.fetch(
                    """
                    SELECT
                        seller_id,
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE status = 'disputed') as disputes,
                        CAST(COUNT(*) FILTER (WHERE status = 'disputed') AS FLOAT) /
                        COUNT(*) * 100 as dispute_rate
                    FROM escrow_transactions
                    WHERE seller_id IS NOT NULL
                    AND created_at > CURRENT_TIMESTAMP - INTERVAL '60 days'
                    GROUP BY seller_id
                    HAVING COUNT(*) >= 5
                    AND CAST(COUNT(*) FILTER (WHERE status = 'disputed') AS FLOAT) /
                        COUNT(*) > 0.3
                    """
                )

                for seller in high_dispute_sellers:
                    try:
                        seller_info = await conn.fetchrow(
                            "SELECT user_id FROM escrow_sellers WHERE id = $1",
                            seller['seller_id']
                        )

                        if seller_info:
                            await escrow_service.flag_suspicious_activity(
                                user_id=seller_info['user_id'],
                                user_type='seller',
                                flag_type='high_dispute_rate',
                                description=f"Dispute rate: {seller['dispute_rate']:.1f}% "
                                          f"({seller['disputes']}/{seller['total']} transactions)",
                                severity='critical'
                            )
                            flags_created += 1
                    except Exception as e:
                        logger.error(f"Failed to flag seller {seller['seller_id']}: {e}")

                # Pattern 3: Unusual refund patterns (multiple refunds in short time)
                repeat_refunds = await conn.fetch(
                    """
                    SELECT buyer_id, COUNT(*) as refund_count
                    FROM escrow_transactions
                    WHERE status = 'refunded'
                    AND created_at > CURRENT_TIMESTAMP - INTERVAL '14 days'
                    GROUP BY buyer_id
                    HAVING COUNT(*) >= 3
                    """
                )

                for buyer in repeat_refunds:
                    try:
                        await escrow_service.flag_suspicious_activity(
                            user_id=buyer['buyer_id'],
                            user_type='buyer',
                            flag_type='multiple_refunds',
                            description=f"{buyer['refund_count']} refunds in 14 days",
                            severity='medium'
                        )
                        flags_created += 1
                    except Exception as e:
                        logger.error(f"Failed to flag buyer {buyer['buyer_id']}: {e}")

            # Update statistics
            self.stats['fraud_flags'] += flags_created
            self.stats['last_run']['fraud_detection'] = datetime.now()

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"Fraud detection completed: {flags_created} new flags in {duration:.2f}s"
            )

        except Exception as e:
            logger.error(f"Fraud detection task failed: {e}", exc_info=True)

    async def cleanup_expired_transactions(self) -> None:
        """
        Clean old data and generate reports.

        Process:
        - Archive transactions older than 90 days
        - Generate monthly reports
        - Clean up old fraud flags
        - Optimize database
        """
        logger.info("Starting transaction cleanup task")
        start_time = datetime.now()

        try:
            db = await get_database()

            async with db.pool.acquire() as conn:
                # Archive old completed transactions (90+ days)
                archive_date = datetime.now() - timedelta(days=90)

                archived = await conn.fetchval(
                    """
                    WITH archived AS (
                        DELETE FROM escrow_transactions
                        WHERE status IN ('completed', 'refunded', 'cancelled')
                        AND completed_at < $1
                        RETURNING id
                    )
                    SELECT COUNT(*) FROM archived
                    """,
                    archive_date
                )

                # Clean up resolved fraud flags (30+ days old)
                cleaned_flags = await conn.fetchval(
                    """
                    DELETE FROM fraud_flags
                    WHERE reviewed = TRUE
                    AND created_at < CURRENT_TIMESTAMP - INTERVAL '30 days'
                    RETURNING id
                    """
                )

                # Generate monthly report
                report = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) as total_transactions,
                        SUM(amount) FILTER (WHERE status = 'completed') as total_volume,
                        COUNT(*) FILTER (WHERE status = 'disputed') as disputes,
                        COUNT(DISTINCT buyer_id) as unique_buyers,
                        COUNT(DISTINCT seller_id) as unique_sellers
                    FROM escrow_transactions
                    WHERE created_at >= date_trunc('month', CURRENT_TIMESTAMP - INTERVAL '1 month')
                    AND created_at < date_trunc('month', CURRENT_TIMESTAMP)
                    """
                )

                # Log monthly report
                logger.info(
                    f"Monthly Report - Transactions: {report['total_transactions']}, "
                    f"Volume: KES {float(report['total_volume'] or 0):,.2f}, "
                    f"Disputes: {report['disputes']}, "
                    f"Buyers: {report['unique_buyers']}, "
                    f"Sellers: {report['unique_sellers']}"
                )

            # Update statistics
            self.stats['last_run']['cleanup'] = datetime.now()

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"Cleanup completed: {archived} transactions archived, "
                f"{cleaned_flags} flags cleaned in {duration:.2f}s"
            )

        except Exception as e:
            logger.error(f"Cleanup task failed: {e}", exc_info=True)

    def get_stats(self) -> Dict[str, Any]:
        """Get automation statistics."""
        return {
            'is_running': self.is_running,
            'scheduled_jobs': len(self.scheduler.get_jobs()) if self.is_running else 0,
            'stats': self.stats,
            'uptime': (datetime.now() - self.stats.get('start_time', datetime.now())).total_seconds()
        }


# Singleton instance
_automation_instance: Optional[EscrowAutomation] = None


async def get_escrow_automation(bot: Bot) -> EscrowAutomation:
    """Get or create escrow automation instance."""
    global _automation_instance

    if _automation_instance is None:
        _automation_instance = EscrowAutomation(bot)
        _automation_instance.stats['start_time'] = datetime.now()

    return _automation_instance


async def start_automation(bot: Bot) -> None:
    """Start escrow automation service."""
    automation = await get_escrow_automation(bot)
    await automation.start()


async def stop_automation() -> None:
    """Stop escrow automation service."""
    global _automation_instance

    if _automation_instance:
        await _automation_instance.stop()


# Example usage
if __name__ == '__main__':
    """
    Example of how to integrate escrow automation with your bot.

    Add this to your main.py:

    from escrow_automation import start_automation, stop_automation
    from telegram.ext import Application

    async def post_init(application: Application) -> None:
        # Start escrow automation
        await start_automation(application.bot)

    async def post_shutdown(application: Application) -> None:
        # Stop escrow automation
        await stop_automation()

    # Build application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    """

    print("Escrow Automation Module")
    print("========================")
    print("\nThis module provides background automation for the escrow system.")
    print("\nScheduled Tasks:")
    print("• Auto-release payments - Every 1 hour")
    print("• Auto-refund unshipped - Every 6 hours")
    print("• Send reminders - Every 12 hours (9 AM, 9 PM)")
    print("• Calculate ratings - Daily at midnight")
    print("• Detect fraud - Daily at 2 AM")
    print("• Cleanup transactions - Weekly on Sunday at 3 AM")
    print("\nSee module docstring for integration instructions.")
