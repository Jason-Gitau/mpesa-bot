"""
Enhanced database module for M-Pesa Escrow System
Provides comprehensive escrow transaction management with buyer/seller protection
"""

import asyncpg
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from decimal import Decimal
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EscrowDatabase:
    """Database handler for escrow system with PostgreSQL"""

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database connection

        Args:
            database_url: PostgreSQL connection URL (defaults to env var)
        """
        self.database_url = database_url or os.getenv('DATABASE_URL')
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Establish database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            logger.info("Database connection pool established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    async def disconnect(self) -> None:
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")

    async def initialize_tables(self) -> None:
        """Create all required database tables with indexes and constraints"""
        if not self.pool:
            raise RuntimeError("Database not connected. Call connect() first.")

        async with self.pool.acquire() as conn:
            # Create sellers table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sellers (
                    id SERIAL PRIMARY KEY,
                    user_chat_id BIGINT UNIQUE NOT NULL,
                    business_name VARCHAR(255) NOT NULL,
                    phone_number VARCHAR(20) NOT NULL,
                    mpesa_number VARCHAR(20) NOT NULL,
                    verification_status VARCHAR(20) DEFAULT 'pending'
                        CHECK (verification_status IN ('pending', 'verified', 'suspended')),
                    rating DECIMAL(3, 2) DEFAULT 0.00 CHECK (rating >= 0 AND rating <= 5),
                    total_sales INTEGER DEFAULT 0,
                    total_amount DECIMAL(15, 2) DEFAULT 0.00,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    verified_at TIMESTAMP,
                    CONSTRAINT valid_phone CHECK (phone_number ~ '^[0-9+]+$'),
                    CONSTRAINT valid_mpesa CHECK (mpesa_number ~ '^254[0-9]{9}$')
                )
            """)

            # Create escrow_transactions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS escrow_transactions (
                    id SERIAL PRIMARY KEY,
                    transaction_id VARCHAR(50) UNIQUE NOT NULL,
                    checkout_request_id VARCHAR(100),
                    mpesa_receipt_number VARCHAR(50),
                    buyer_chat_id BIGINT NOT NULL,
                    seller_id INTEGER NOT NULL REFERENCES sellers(id) ON DELETE RESTRICT,
                    amount DECIMAL(15, 2) NOT NULL CHECK (amount > 0),
                    description TEXT,
                    status VARCHAR(30) DEFAULT 'pending_payment'
                        CHECK (status IN ('pending_payment', 'held', 'shipped',
                                         'completed', 'refunded', 'disputed', 'expired')),
                    payment_received_at TIMESTAMP,
                    shipped_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    disputed_at TIMESTAMP,
                    resolved_at TIMESTAMP,
                    tracking_number VARCHAR(100),
                    buyer_confirmation BOOLEAN DEFAULT FALSE,
                    seller_confirmation BOOLEAN DEFAULT FALSE,
                    auto_release_date TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT valid_transaction_id CHECK (LENGTH(transaction_id) >= 10)
                )
            """)

            # Create disputes table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS disputes (
                    id SERIAL PRIMARY KEY,
                    transaction_id VARCHAR(50) NOT NULL REFERENCES escrow_transactions(transaction_id)
                        ON DELETE CASCADE,
                    raised_by VARCHAR(10) NOT NULL CHECK (raised_by IN ('buyer', 'seller')),
                    reason VARCHAR(100) NOT NULL,
                    description TEXT NOT NULL,
                    status VARCHAR(20) DEFAULT 'open'
                        CHECK (status IN ('open', 'investigating', 'resolved')),
                    resolution TEXT,
                    resolved_by_admin_id BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP
                )
            """)

            # Create transaction_timeline table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS transaction_timeline (
                    id SERIAL PRIMARY KEY,
                    transaction_id VARCHAR(50) NOT NULL REFERENCES escrow_transactions(transaction_id)
                        ON DELETE CASCADE,
                    event_type VARCHAR(30) NOT NULL
                        CHECK (event_type IN ('payment_initiated', 'payment_held', 'shipped',
                                              'delivered', 'disputed', 'refunded', 'released',
                                              'expired', 'confirmed')),
                    description TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create notifications table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id SERIAL PRIMARY KEY,
                    user_chat_id BIGINT NOT NULL,
                    transaction_id VARCHAR(50) REFERENCES escrow_transactions(transaction_id)
                        ON DELETE CASCADE,
                    message TEXT NOT NULL,
                    notification_type VARCHAR(30) NOT NULL,
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for performance
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sellers_chat_id ON sellers(user_chat_id);
                CREATE INDEX IF NOT EXISTS idx_sellers_verification ON sellers(verification_status);
                CREATE INDEX IF NOT EXISTS idx_escrow_buyer ON escrow_transactions(buyer_chat_id);
                CREATE INDEX IF NOT EXISTS idx_escrow_seller ON escrow_transactions(seller_id);
                CREATE INDEX IF NOT EXISTS idx_escrow_status ON escrow_transactions(status);
                CREATE INDEX IF NOT EXISTS idx_escrow_auto_release ON escrow_transactions(auto_release_date);
                CREATE INDEX IF NOT EXISTS idx_disputes_transaction ON disputes(transaction_id);
                CREATE INDEX IF NOT EXISTS idx_disputes_status ON disputes(status);
                CREATE INDEX IF NOT EXISTS idx_timeline_transaction ON transaction_timeline(transaction_id);
                CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_chat_id);
                CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notifications(is_read);
            """)

            logger.info("All database tables and indexes created successfully")

    # ==================== SELLER MANAGEMENT ====================

    async def register_seller(
        self,
        user_chat_id: int,
        business_name: str,
        phone_number: str,
        mpesa_number: str
    ) -> Optional[Dict[str, Any]]:
        """
        Register a new seller in the escrow system

        Args:
            user_chat_id: Telegram chat ID of the seller
            business_name: Name of the business
            phone_number: Contact phone number
            mpesa_number: M-Pesa number for receiving payments (format: 254XXXXXXXXX)

        Returns:
            Dict with seller details or None if registration fails
        """
        try:
            async with self.pool.acquire() as conn:
                seller = await conn.fetchrow("""
                    INSERT INTO sellers (user_chat_id, business_name, phone_number, mpesa_number)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id, user_chat_id, business_name, phone_number, mpesa_number,
                              verification_status, rating, total_sales, total_amount, created_at
                """, user_chat_id, business_name, phone_number, mpesa_number)

                logger.info(f"Seller registered: {business_name} (ID: {seller['id']})")
                return dict(seller)
        except asyncpg.UniqueViolationError:
            logger.warning(f"Seller with chat_id {user_chat_id} already exists")
            return None
        except asyncpg.CheckViolationError as e:
            logger.error(f"Invalid seller data: {e}")
            return None
        except Exception as e:
            logger.error(f"Error registering seller: {e}")
            return None

    async def verify_seller(
        self,
        seller_id: int,
        verification_status: str = 'verified'
    ) -> bool:
        """
        Admin verifies or suspends a seller

        Args:
            seller_id: Seller's database ID
            verification_status: Status to set ('verified' or 'suspended')

        Returns:
            True if verification updated successfully
        """
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute("""
                    UPDATE sellers
                    SET verification_status = $1,
                        verified_at = CASE WHEN $1 = 'verified' THEN CURRENT_TIMESTAMP ELSE verified_at END
                    WHERE id = $2
                """, verification_status, seller_id)

                if result == "UPDATE 1":
                    logger.info(f"Seller {seller_id} verification status: {verification_status}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Error verifying seller: {e}")
            return False

    async def get_seller_by_chat_id(self, user_chat_id: int) -> Optional[Dict[str, Any]]:
        """
        Get seller information by Telegram chat ID

        Args:
            user_chat_id: Telegram chat ID

        Returns:
            Dict with seller details or None if not found
        """
        try:
            async with self.pool.acquire() as conn:
                seller = await conn.fetchrow("""
                    SELECT id, user_chat_id, business_name, phone_number, mpesa_number,
                           verification_status, rating, total_sales, total_amount,
                           created_at, verified_at
                    FROM sellers
                    WHERE user_chat_id = $1
                """, user_chat_id)

                return dict(seller) if seller else None
        except Exception as e:
            logger.error(f"Error fetching seller: {e}")
            return None

    async def get_seller_by_id(self, seller_id: int) -> Optional[Dict[str, Any]]:
        """
        Get seller information by database ID

        Args:
            seller_id: Seller's database ID

        Returns:
            Dict with seller details or None if not found
        """
        try:
            async with self.pool.acquire() as conn:
                seller = await conn.fetchrow("""
                    SELECT id, user_chat_id, business_name, phone_number, mpesa_number,
                           verification_status, rating, total_sales, total_amount,
                           created_at, verified_at
                    FROM sellers
                    WHERE id = $1
                """, seller_id)

                return dict(seller) if seller else None
        except Exception as e:
            logger.error(f"Error fetching seller: {e}")
            return None

    # ==================== ESCROW TRANSACTION MANAGEMENT ====================

    async def create_escrow_transaction(
        self,
        transaction_id: str,
        buyer_chat_id: int,
        seller_id: int,
        amount: Decimal,
        description: str,
        checkout_request_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new escrow transaction

        Args:
            transaction_id: Unique transaction identifier
            buyer_chat_id: Telegram chat ID of the buyer
            seller_id: Database ID of the seller
            amount: Transaction amount
            description: Description of the purchase
            checkout_request_id: M-Pesa STK push request ID

        Returns:
            Dict with transaction details or None if creation fails
        """
        try:
            async with self.pool.acquire() as conn:
                transaction = await conn.fetchrow("""
                    INSERT INTO escrow_transactions
                    (transaction_id, buyer_chat_id, seller_id, amount, description,
                     checkout_request_id, status)
                    VALUES ($1, $2, $3, $4, $5, $6, 'pending_payment')
                    RETURNING id, transaction_id, buyer_chat_id, seller_id, amount,
                              description, status, created_at
                """, transaction_id, buyer_chat_id, seller_id, amount, description,
                checkout_request_id)

                # Add timeline event
                await self.add_timeline_event(
                    transaction_id,
                    'payment_initiated',
                    f'Escrow transaction created for KES {amount}'
                )

                logger.info(f"Escrow transaction created: {transaction_id}")
                return dict(transaction)
        except asyncpg.UniqueViolationError:
            logger.warning(f"Transaction {transaction_id} already exists")
            return None
        except asyncpg.ForeignKeyViolationError:
            logger.error(f"Invalid seller_id: {seller_id}")
            return None
        except Exception as e:
            logger.error(f"Error creating escrow transaction: {e}")
            return None

    async def update_transaction_status(
        self,
        transaction_id: str,
        status: str,
        mpesa_receipt_number: Optional[str] = None,
        auto_release_days: int = 7
    ) -> bool:
        """
        Update escrow transaction status

        Args:
            transaction_id: Transaction identifier
            status: New status
            mpesa_receipt_number: M-Pesa receipt number (for payment confirmation)
            auto_release_days: Days until automatic payment release (default 7)

        Returns:
            True if update successful
        """
        try:
            async with self.pool.acquire() as conn:
                # Prepare update based on status
                if status == 'held':
                    auto_release_date = datetime.now() + timedelta(days=auto_release_days)
                    result = await conn.execute("""
                        UPDATE escrow_transactions
                        SET status = $1,
                            mpesa_receipt_number = $2,
                            payment_received_at = CURRENT_TIMESTAMP,
                            auto_release_date = $3
                        WHERE transaction_id = $4
                    """, status, mpesa_receipt_number, auto_release_date, transaction_id)

                    await self.add_timeline_event(
                        transaction_id,
                        'payment_held',
                        f'Payment received and held in escrow. Receipt: {mpesa_receipt_number}'
                    )

                elif status == 'shipped':
                    result = await conn.execute("""
                        UPDATE escrow_transactions
                        SET status = $1, shipped_at = CURRENT_TIMESTAMP
                        WHERE transaction_id = $2
                    """, status, transaction_id)

                elif status == 'completed':
                    result = await conn.execute("""
                        UPDATE escrow_transactions
                        SET status = $1, completed_at = CURRENT_TIMESTAMP
                        WHERE transaction_id = $2
                    """, status, transaction_id)

                    # Update seller stats
                    await conn.execute("""
                        UPDATE sellers
                        SET total_sales = total_sales + 1,
                            total_amount = total_amount + (
                                SELECT amount FROM escrow_transactions WHERE transaction_id = $1
                            )
                        WHERE id = (SELECT seller_id FROM escrow_transactions WHERE transaction_id = $1)
                    """, transaction_id)

                elif status == 'refunded':
                    result = await conn.execute("""
                        UPDATE escrow_transactions
                        SET status = $1, resolved_at = CURRENT_TIMESTAMP
                        WHERE transaction_id = $2
                    """, status, transaction_id)

                elif status == 'disputed':
                    result = await conn.execute("""
                        UPDATE escrow_transactions
                        SET status = $1, disputed_at = CURRENT_TIMESTAMP
                        WHERE transaction_id = $2
                    """, status, transaction_id)

                elif status == 'expired':
                    result = await conn.execute("""
                        UPDATE escrow_transactions
                        SET status = $1, resolved_at = CURRENT_TIMESTAMP
                        WHERE transaction_id = $2
                    """, status, transaction_id)

                else:
                    result = await conn.execute("""
                        UPDATE escrow_transactions
                        SET status = $1
                        WHERE transaction_id = $2
                    """, status, transaction_id)

                if result == "UPDATE 1":
                    logger.info(f"Transaction {transaction_id} status updated to {status}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Error updating transaction status: {e}")
            return False

    async def mark_as_shipped(
        self,
        transaction_id: str,
        tracking_number: Optional[str] = None
    ) -> bool:
        """
        Seller marks order as shipped

        Args:
            transaction_id: Transaction identifier
            tracking_number: Shipping tracking number (optional)

        Returns:
            True if update successful
        """
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute("""
                    UPDATE escrow_transactions
                    SET status = 'shipped',
                        shipped_at = CURRENT_TIMESTAMP,
                        tracking_number = $1,
                        seller_confirmation = TRUE
                    WHERE transaction_id = $2 AND status = 'held'
                """, tracking_number, transaction_id)

                if result == "UPDATE 1":
                    tracking_info = f" Tracking: {tracking_number}" if tracking_number else ""
                    await self.add_timeline_event(
                        transaction_id,
                        'shipped',
                        f'Order marked as shipped by seller.{tracking_info}'
                    )

                    logger.info(f"Transaction {transaction_id} marked as shipped")
                    return True
                return False
        except Exception as e:
            logger.error(f"Error marking as shipped: {e}")
            return False

    async def confirm_delivery(
        self,
        transaction_id: str,
        buyer_chat_id: int
    ) -> bool:
        """
        Buyer confirms delivery of goods

        Args:
            transaction_id: Transaction identifier
            buyer_chat_id: Buyer's chat ID for verification

        Returns:
            True if confirmation successful
        """
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute("""
                    UPDATE escrow_transactions
                    SET buyer_confirmation = TRUE,
                        status = 'completed',
                        completed_at = CURRENT_TIMESTAMP
                    WHERE transaction_id = $1
                      AND buyer_chat_id = $2
                      AND status IN ('shipped', 'held')
                """, transaction_id, buyer_chat_id)

                if result == "UPDATE 1":
                    await self.add_timeline_event(
                        transaction_id,
                        'delivered',
                        'Buyer confirmed delivery. Payment will be released to seller.'
                    )

                    # Update seller stats
                    await conn.execute("""
                        UPDATE sellers
                        SET total_sales = total_sales + 1,
                            total_amount = total_amount + (
                                SELECT amount FROM escrow_transactions WHERE transaction_id = $1
                            )
                        WHERE id = (SELECT seller_id FROM escrow_transactions WHERE transaction_id = $1)
                    """, transaction_id)

                    logger.info(f"Delivery confirmed for transaction {transaction_id}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Error confirming delivery: {e}")
            return False

    async def release_payment(
        self,
        transaction_id: str,
        is_auto_release: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Release payment from escrow to seller

        Args:
            transaction_id: Transaction identifier
            is_auto_release: Whether this is an automatic release

        Returns:
            Dict with transaction and seller details for payment processing
        """
        try:
            async with self.pool.acquire() as conn:
                # Get transaction and seller details
                transaction = await conn.fetchrow("""
                    SELECT et.*, s.mpesa_number, s.business_name
                    FROM escrow_transactions et
                    JOIN sellers s ON et.seller_id = s.id
                    WHERE et.transaction_id = $1
                      AND et.status IN ('completed', 'shipped', 'held')
                """, transaction_id)

                if not transaction:
                    logger.warning(f"Transaction {transaction_id} not found or not eligible for release")
                    return None

                # Mark as completed
                await conn.execute("""
                    UPDATE escrow_transactions
                    SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                    WHERE transaction_id = $1
                """, transaction_id)

                release_type = "automatic" if is_auto_release else "manual"
                await self.add_timeline_event(
                    transaction_id,
                    'released',
                    f'Payment released to seller ({release_type} release)'
                )

                logger.info(f"Payment released for transaction {transaction_id}")
                return dict(transaction)
        except Exception as e:
            logger.error(f"Error releasing payment: {e}")
            return None

    async def refund_payment(
        self,
        transaction_id: str,
        reason: str
    ) -> Optional[Dict[str, Any]]:
        """
        Refund payment from escrow to buyer

        Args:
            transaction_id: Transaction identifier
            reason: Reason for refund

        Returns:
            Dict with transaction details for refund processing
        """
        try:
            async with self.pool.acquire() as conn:
                # Get transaction details
                transaction = await conn.fetchrow("""
                    SELECT * FROM escrow_transactions
                    WHERE transaction_id = $1
                      AND status IN ('held', 'disputed', 'shipped')
                """, transaction_id)

                if not transaction:
                    logger.warning(f"Transaction {transaction_id} not found or not eligible for refund")
                    return None

                # Mark as refunded
                await conn.execute("""
                    UPDATE escrow_transactions
                    SET status = 'refunded', resolved_at = CURRENT_TIMESTAMP
                    WHERE transaction_id = $1
                """, transaction_id)

                await self.add_timeline_event(
                    transaction_id,
                    'refunded',
                    f'Payment refunded to buyer. Reason: {reason}'
                )

                logger.info(f"Payment refunded for transaction {transaction_id}")
                return dict(transaction)
        except Exception as e:
            logger.error(f"Error refunding payment: {e}")
            return None

    # ==================== DISPUTE MANAGEMENT ====================

    async def create_dispute(
        self,
        transaction_id: str,
        raised_by: str,
        reason: str,
        description: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create a dispute for an escrow transaction

        Args:
            transaction_id: Transaction identifier
            raised_by: Who raised the dispute ('buyer' or 'seller')
            reason: Brief reason for dispute
            description: Detailed description

        Returns:
            Dict with dispute details or None if creation fails
        """
        try:
            async with self.pool.acquire() as conn:
                # Update transaction status to disputed
                await conn.execute("""
                    UPDATE escrow_transactions
                    SET status = 'disputed', disputed_at = CURRENT_TIMESTAMP
                    WHERE transaction_id = $1
                """, transaction_id)

                # Create dispute record
                dispute = await conn.fetchrow("""
                    INSERT INTO disputes (transaction_id, raised_by, reason, description)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id, transaction_id, raised_by, reason, description,
                              status, created_at
                """, transaction_id, raised_by, reason, description)

                await self.add_timeline_event(
                    transaction_id,
                    'disputed',
                    f'Dispute raised by {raised_by}. Reason: {reason}'
                )

                logger.info(f"Dispute created for transaction {transaction_id}")
                return dict(dispute)
        except Exception as e:
            logger.error(f"Error creating dispute: {e}")
            return None

    async def resolve_dispute(
        self,
        dispute_id: int,
        resolution: str,
        resolved_by_admin_id: int,
        action: str  # 'refund' or 'release'
    ) -> bool:
        """
        Admin resolves a dispute

        Args:
            dispute_id: Dispute database ID
            resolution: Resolution description
            resolved_by_admin_id: Admin's chat ID
            action: Action to take ('refund' to buyer or 'release' to seller)

        Returns:
            True if resolution successful
        """
        try:
            async with self.pool.acquire() as conn:
                # Get dispute details
                dispute = await conn.fetchrow("""
                    SELECT * FROM disputes WHERE id = $1
                """, dispute_id)

                if not dispute:
                    return False

                # Update dispute status
                await conn.execute("""
                    UPDATE disputes
                    SET status = 'resolved',
                        resolution = $1,
                        resolved_by_admin_id = $2,
                        resolved_at = CURRENT_TIMESTAMP
                    WHERE id = $3
                """, resolution, resolved_by_admin_id, dispute_id)

                # Take action based on resolution
                if action == 'refund':
                    await self.refund_payment(
                        dispute['transaction_id'],
                        f"Dispute resolved: {resolution}"
                    )
                elif action == 'release':
                    await self.release_payment(dispute['transaction_id'])

                logger.info(f"Dispute {dispute_id} resolved with action: {action}")
                return True
        except Exception as e:
            logger.error(f"Error resolving dispute: {e}")
            return False

    async def get_dispute_transactions(
        self,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all disputed transactions

        Args:
            status: Filter by dispute status ('open', 'investigating', 'resolved')

        Returns:
            List of disputed transactions with dispute details
        """
        try:
            async with self.pool.acquire() as conn:
                if status:
                    disputes = await conn.fetch("""
                        SELECT d.*, et.amount, et.description, et.buyer_chat_id,
                               s.business_name, s.user_chat_id as seller_chat_id
                        FROM disputes d
                        JOIN escrow_transactions et ON d.transaction_id = et.transaction_id
                        JOIN sellers s ON et.seller_id = s.id
                        WHERE d.status = $1
                        ORDER BY d.created_at DESC
                    """, status)
                else:
                    disputes = await conn.fetch("""
                        SELECT d.*, et.amount, et.description, et.buyer_chat_id,
                               s.business_name, s.user_chat_id as seller_chat_id
                        FROM disputes d
                        JOIN escrow_transactions et ON d.transaction_id = et.transaction_id
                        JOIN sellers s ON et.seller_id = s.id
                        ORDER BY d.created_at DESC
                    """)

                return [dict(d) for d in disputes]
        except Exception as e:
            logger.error(f"Error fetching disputes: {e}")
            return []

    # ==================== TIMELINE & NOTIFICATIONS ====================

    async def add_timeline_event(
        self,
        transaction_id: str,
        event_type: str,
        description: str
    ) -> bool:
        """
        Add an event to transaction timeline

        Args:
            transaction_id: Transaction identifier
            event_type: Type of event
            description: Event description

        Returns:
            True if event added successfully
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO transaction_timeline (transaction_id, event_type, description)
                    VALUES ($1, $2, $3)
                """, transaction_id, event_type, description)

                return True
        except Exception as e:
            logger.error(f"Error adding timeline event: {e}")
            return False

    async def get_transaction_timeline(
        self,
        transaction_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get complete timeline for a transaction

        Args:
            transaction_id: Transaction identifier

        Returns:
            List of timeline events
        """
        try:
            async with self.pool.acquire() as conn:
                timeline = await conn.fetch("""
                    SELECT event_type, description, created_at
                    FROM transaction_timeline
                    WHERE transaction_id = $1
                    ORDER BY created_at ASC
                """, transaction_id)

                return [dict(event) for event in timeline]
        except Exception as e:
            logger.error(f"Error fetching timeline: {e}")
            return []

    async def create_notification(
        self,
        user_chat_id: int,
        message: str,
        notification_type: str,
        transaction_id: Optional[str] = None
    ) -> bool:
        """
        Create a notification for a user

        Args:
            user_chat_id: User's Telegram chat ID
            message: Notification message
            notification_type: Type of notification
            transaction_id: Related transaction ID (optional)

        Returns:
            True if notification created
        """
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO notifications
                    (user_chat_id, transaction_id, message, notification_type)
                    VALUES ($1, $2, $3, $4)
                """, user_chat_id, transaction_id, message, notification_type)

                return True
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            return False

    async def get_unread_notifications(
        self,
        user_chat_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get unread notifications for a user

        Args:
            user_chat_id: User's Telegram chat ID

        Returns:
            List of unread notifications
        """
        try:
            async with self.pool.acquire() as conn:
                notifications = await conn.fetch("""
                    SELECT id, transaction_id, message, notification_type, created_at
                    FROM notifications
                    WHERE user_chat_id = $1 AND is_read = FALSE
                    ORDER BY created_at DESC
                """, user_chat_id)

                return [dict(n) for n in notifications]
        except Exception as e:
            logger.error(f"Error fetching notifications: {e}")
            return []

    async def mark_notifications_read(
        self,
        user_chat_id: int,
        notification_ids: Optional[List[int]] = None
    ) -> bool:
        """
        Mark notifications as read

        Args:
            user_chat_id: User's Telegram chat ID
            notification_ids: Specific notification IDs (or all if None)

        Returns:
            True if marked successfully
        """
        try:
            async with self.pool.acquire() as conn:
                if notification_ids:
                    await conn.execute("""
                        UPDATE notifications
                        SET is_read = TRUE
                        WHERE user_chat_id = $1 AND id = ANY($2)
                    """, user_chat_id, notification_ids)
                else:
                    await conn.execute("""
                        UPDATE notifications
                        SET is_read = TRUE
                        WHERE user_chat_id = $1
                    """, user_chat_id)

                return True
        except Exception as e:
            logger.error(f"Error marking notifications read: {e}")
            return False

    # ==================== QUERY & STATS FUNCTIONS ====================

    async def get_pending_auto_releases(self) -> List[Dict[str, Any]]:
        """
        Get transactions ready for automatic payment release

        Returns:
            List of transactions eligible for auto-release
        """
        try:
            async with self.pool.acquire() as conn:
                transactions = await conn.fetch("""
                    SELECT et.*, s.mpesa_number, s.business_name
                    FROM escrow_transactions et
                    JOIN sellers s ON et.seller_id = s.id
                    WHERE et.status IN ('held', 'shipped')
                      AND et.auto_release_date <= CURRENT_TIMESTAMP
                      AND et.buyer_confirmation = FALSE
                    ORDER BY et.auto_release_date ASC
                """)

                return [dict(t) for t in transactions]
        except Exception as e:
            logger.error(f"Error fetching pending auto-releases: {e}")
            return []

    async def get_seller_stats(self, seller_id: int) -> Optional[Dict[str, Any]]:
        """
        Get seller dashboard statistics

        Args:
            seller_id: Seller's database ID

        Returns:
            Dict with seller statistics
        """
        try:
            async with self.pool.acquire() as conn:
                # Get basic seller info
                seller = await conn.fetchrow("""
                    SELECT * FROM sellers WHERE id = $1
                """, seller_id)

                if not seller:
                    return None

                # Get transaction stats
                stats = await conn.fetchrow("""
                    SELECT
                        COUNT(*) as total_transactions,
                        COUNT(CASE WHEN status = 'held' THEN 1 END) as pending_shipments,
                        COUNT(CASE WHEN status = 'shipped' THEN 1 END) as in_transit,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                        COUNT(CASE WHEN status = 'disputed' THEN 1 END) as disputed,
                        COALESCE(SUM(CASE WHEN status = 'held' THEN amount ELSE 0 END), 0) as pending_amount,
                        COALESCE(SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END), 0) as completed_amount
                    FROM escrow_transactions
                    WHERE seller_id = $1
                """, seller_id)

                return {
                    'seller': dict(seller),
                    'stats': dict(stats)
                }
        except Exception as e:
            logger.error(f"Error fetching seller stats: {e}")
            return None

    async def get_buyer_transactions(
        self,
        buyer_chat_id: int,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get buyer's purchase history

        Args:
            buyer_chat_id: Buyer's Telegram chat ID
            status: Filter by status (optional)
            limit: Maximum number of results

        Returns:
            List of buyer's transactions
        """
        try:
            async with self.pool.acquire() as conn:
                if status:
                    transactions = await conn.fetch("""
                        SELECT et.*, s.business_name, s.phone_number
                        FROM escrow_transactions et
                        JOIN sellers s ON et.seller_id = s.id
                        WHERE et.buyer_chat_id = $1 AND et.status = $2
                        ORDER BY et.created_at DESC
                        LIMIT $3
                    """, buyer_chat_id, status, limit)
                else:
                    transactions = await conn.fetch("""
                        SELECT et.*, s.business_name, s.phone_number
                        FROM escrow_transactions et
                        JOIN sellers s ON et.seller_id = s.id
                        WHERE et.buyer_chat_id = $1
                        ORDER BY et.created_at DESC
                        LIMIT $2
                    """, buyer_chat_id, limit)

                return [dict(t) for t in transactions]
        except Exception as e:
            logger.error(f"Error fetching buyer transactions: {e}")
            return []

    async def get_seller_transactions(
        self,
        seller_id: int,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get seller's sales history

        Args:
            seller_id: Seller's database ID
            status: Filter by status (optional)
            limit: Maximum number of results

        Returns:
            List of seller's transactions
        """
        try:
            async with self.pool.acquire() as conn:
                if status:
                    transactions = await conn.fetch("""
                        SELECT * FROM escrow_transactions
                        WHERE seller_id = $1 AND status = $2
                        ORDER BY created_at DESC
                        LIMIT $3
                    """, seller_id, status, limit)
                else:
                    transactions = await conn.fetch("""
                        SELECT * FROM escrow_transactions
                        WHERE seller_id = $1
                        ORDER BY created_at DESC
                        LIMIT $2
                    """, seller_id, limit)

                return [dict(t) for t in transactions]
        except Exception as e:
            logger.error(f"Error fetching seller transactions: {e}")
            return []

    async def get_transaction_by_id(
        self,
        transaction_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed transaction information

        Args:
            transaction_id: Transaction identifier

        Returns:
            Dict with complete transaction details including seller info
        """
        try:
            async with self.pool.acquire() as conn:
                transaction = await conn.fetchrow("""
                    SELECT et.*, s.business_name, s.phone_number, s.mpesa_number,
                           s.verification_status, s.rating
                    FROM escrow_transactions et
                    JOIN sellers s ON et.seller_id = s.id
                    WHERE et.transaction_id = $1
                """, transaction_id)

                return dict(transaction) if transaction else None
        except Exception as e:
            logger.error(f"Error fetching transaction: {e}")
            return None

    async def update_seller_rating(
        self,
        seller_id: int,
        new_rating: float
    ) -> bool:
        """
        Update seller's rating

        Args:
            seller_id: Seller's database ID
            new_rating: New rating value (0-5)

        Returns:
            True if update successful
        """
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute("""
                    UPDATE sellers
                    SET rating = $1
                    WHERE id = $2
                """, new_rating, seller_id)

                return result == "UPDATE 1"
        except Exception as e:
            logger.error(f"Error updating seller rating: {e}")
            return False

    async def get_expired_transactions(self) -> List[Dict[str, Any]]:
        """
        Get transactions that have expired (payment not received)

        Returns:
            List of expired transactions
        """
        try:
            async with self.pool.acquire() as conn:
                # Transactions older than 24 hours with pending_payment status
                transactions = await conn.fetch("""
                    SELECT * FROM escrow_transactions
                    WHERE status = 'pending_payment'
                      AND created_at < CURRENT_TIMESTAMP - INTERVAL '24 hours'
                    ORDER BY created_at ASC
                """)

                return [dict(t) for t in transactions]
        except Exception as e:
            logger.error(f"Error fetching expired transactions: {e}")
            return []


# Convenience function for easy initialization
async def create_escrow_db(database_url: Optional[str] = None) -> EscrowDatabase:
    """
    Create and initialize escrow database

    Args:
        database_url: PostgreSQL connection URL

    Returns:
        Connected EscrowDatabase instance
    """
    db = EscrowDatabase(database_url)
    await db.connect()
    await db.initialize_tables()
    return db
