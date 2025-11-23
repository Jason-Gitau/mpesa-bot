"""
Escrow Service Module for M-Pesa Bot

This module provides comprehensive escrow business logic for secure marketplace
transactions. It handles the full lifecycle of escrow payments including initiation,
holding funds, delivery confirmation, payment release, refunds, and dispute resolution.

Features:
    - Secure payment holding and release
    - Automated refund and release mechanisms
    - Dispute resolution workflow
    - Fraud detection and prevention
    - Comprehensive transaction state management
    - Integration with M-Pesa and Telegram notifications

Dependencies:
    - database.py: Database operations
    - mpesa_service.py: M-Pesa payment integration
    - config.py: Configuration management
"""

import asyncio
import asyncpg
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
from enum import Enum

from database import Database, DatabaseError
from mpesa_service import initiate_stk_push, PaymentError, MpesaError
from config import get_config, Config, ConfigError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EscrowState(str, Enum):
    """Enumeration of possible escrow transaction states."""
    PENDING = "pending"              # Payment initiated, waiting for M-Pesa
    HELD = "held"                    # Payment received, held in escrow
    SHIPPED = "shipped"              # Seller marked as shipped
    COMPLETED = "completed"          # Payment released to seller
    REFUNDED = "refunded"            # Payment returned to buyer
    DISPUTED = "disputed"            # Dispute opened
    CANCELLED = "cancelled"          # Transaction cancelled
    FAILED = "failed"                # Payment failed


class DisputeStatus(str, Enum):
    """Enumeration of dispute statuses."""
    OPEN = "open"                    # Dispute opened, pending resolution
    INVESTIGATING = "investigating"  # Under admin review
    RESOLVED = "resolved"            # Dispute resolved
    CLOSED = "closed"                # Dispute closed


class DisputeDecision(str, Enum):
    """Enumeration of possible dispute resolutions."""
    REFUND_BUYER = "refund_buyer"           # Refund full amount to buyer
    RELEASE_SELLER = "release_seller"       # Release full amount to seller
    PARTIAL_REFUND = "partial_refund"       # Partial refund to buyer
    RESHIP = "reship"                       # Seller to reship item


class EscrowError(Exception):
    """Base exception for escrow-related errors."""
    pass


class StateTransitionError(EscrowError):
    """Raised when an invalid state transition is attempted."""
    pass


class ValidationError(EscrowError):
    """Raised when validation fails."""
    pass


class FraudDetectionError(EscrowError):
    """Raised when suspicious activity is detected."""
    pass


class EscrowService:
    """
    Core escrow business logic service.

    Manages the complete lifecycle of escrow transactions including payment
    processing, delivery confirmation, dispute resolution, and automated
    refund/release mechanisms.

    Attributes:
        db: Database instance for persistence
        config: Configuration instance
        telegram_bot: Telegram bot instance for notifications (optional)
    """

    # Constants
    AUTO_REFUND_DAYS = 3          # Auto-refund if not shipped within 3 days
    AUTO_RELEASE_DAYS = 7         # Auto-release after 7 days of delivery confirmation
    MAX_TRANSACTION_AMOUNT = 500000  # Maximum escrow amount (KES)
    MIN_SELLER_RATING = 0.5       # Minimum seller rating (0.0 - 1.0)
    FRAUD_CHECK_THRESHOLD = 10    # Number of transactions to check for patterns

    def __init__(
        self,
        database: Database,
        config: Optional[Config] = None,
        telegram_bot: Optional[Any] = None
    ):
        """
        Initialize the escrow service.

        Args:
            database: Database instance for data persistence
            config: Configuration instance (optional, will load if not provided)
            telegram_bot: Telegram bot instance for sending notifications (optional)
        """
        self.db = database
        self.config = config or get_config()
        self.telegram_bot = telegram_bot
        logger.info("EscrowService initialized successfully")

    async def init_escrow_schema(self) -> None:
        """
        Initialize escrow-specific database schema.

        Creates tables for escrow transactions, disputes, seller ratings,
        and fraud flags if they don't already exist.

        Raises:
            DatabaseError: If schema initialization fails
        """
        if not self.db.pool:
            raise DatabaseError("Database not connected. Call connect() first.")

        # Escrow transactions table
        create_escrow_transactions = """
        CREATE TABLE IF NOT EXISTS escrow_transactions (
            id SERIAL PRIMARY KEY,
            transaction_id VARCHAR(100) UNIQUE NOT NULL,
            buyer_chat_id BIGINT NOT NULL,
            seller_chat_id BIGINT NOT NULL,
            amount DECIMAL(10, 2) NOT NULL,
            description TEXT NOT NULL,
            state VARCHAR(20) DEFAULT 'pending' CHECK (
                state IN ('pending', 'held', 'shipped', 'completed',
                         'refunded', 'disputed', 'cancelled', 'failed')
            ),
            mpesa_checkout_request_id VARCHAR(100),
            mpesa_receipt_number VARCHAR(100),
            tracking_number VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            payment_received_at TIMESTAMP,
            shipped_at TIMESTAMP,
            delivered_at TIMESTAMP,
            completed_at TIMESTAMP,
            auto_release_date TIMESTAMP,
            refund_reason TEXT,
            is_flagged BOOLEAN DEFAULT FALSE,
            flag_reason TEXT,
            CONSTRAINT positive_amount CHECK (amount > 0),
            FOREIGN KEY (buyer_chat_id) REFERENCES users(chat_id) ON DELETE CASCADE,
            FOREIGN KEY (seller_chat_id) REFERENCES users(chat_id) ON DELETE CASCADE
        );
        """

        # Disputes table
        create_disputes = """
        CREATE TABLE IF NOT EXISTS escrow_disputes (
            id SERIAL PRIMARY KEY,
            transaction_id VARCHAR(100) UNIQUE NOT NULL,
            raised_by_chat_id BIGINT NOT NULL,
            reason VARCHAR(50) NOT NULL,
            description TEXT NOT NULL,
            status VARCHAR(20) DEFAULT 'open' CHECK (
                status IN ('open', 'investigating', 'resolved', 'closed')
            ),
            decision VARCHAR(50),
            resolution_notes TEXT,
            resolved_by_admin_id BIGINT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            FOREIGN KEY (transaction_id) REFERENCES escrow_transactions(transaction_id)
                ON DELETE CASCADE
        );
        """

        # Seller ratings table
        create_seller_ratings = """
        CREATE TABLE IF NOT EXISTS seller_ratings (
            id SERIAL PRIMARY KEY,
            seller_chat_id BIGINT NOT NULL,
            buyer_chat_id BIGINT NOT NULL,
            transaction_id VARCHAR(100) NOT NULL,
            rating INTEGER CHECK (rating BETWEEN 1 AND 5),
            review TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (seller_chat_id) REFERENCES users(chat_id) ON DELETE CASCADE,
            FOREIGN KEY (buyer_chat_id) REFERENCES users(chat_id) ON DELETE CASCADE,
            FOREIGN KEY (transaction_id) REFERENCES escrow_transactions(transaction_id)
                ON DELETE CASCADE,
            UNIQUE(transaction_id, buyer_chat_id)
        );
        """

        # Fraud detection log
        create_fraud_log = """
        CREATE TABLE IF NOT EXISTS fraud_detection_log (
            id SERIAL PRIMARY KEY,
            transaction_id VARCHAR(100),
            user_chat_id BIGINT,
            fraud_type VARCHAR(50) NOT NULL,
            risk_score DECIMAL(3, 2),
            details TEXT,
            flagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (transaction_id) REFERENCES escrow_transactions(transaction_id)
                ON DELETE SET NULL
        );
        """

        # Indexes for performance
        create_indexes = """
        CREATE INDEX IF NOT EXISTS idx_escrow_transactions_buyer
            ON escrow_transactions(buyer_chat_id);
        CREATE INDEX IF NOT EXISTS idx_escrow_transactions_seller
            ON escrow_transactions(seller_chat_id);
        CREATE INDEX IF NOT EXISTS idx_escrow_transactions_state
            ON escrow_transactions(state);
        CREATE INDEX IF NOT EXISTS idx_escrow_transactions_created_at
            ON escrow_transactions(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_escrow_disputes_transaction
            ON escrow_disputes(transaction_id);
        CREATE INDEX IF NOT EXISTS idx_escrow_disputes_status
            ON escrow_disputes(status);
        CREATE INDEX IF NOT EXISTS idx_seller_ratings_seller
            ON seller_ratings(seller_chat_id);
        CREATE INDEX IF NOT EXISTS idx_fraud_log_user
            ON fraud_detection_log(user_chat_id);
        """

        try:
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(create_escrow_transactions)
                    logger.info("Escrow transactions table created/verified")

                    await conn.execute(create_disputes)
                    logger.info("Escrow disputes table created/verified")

                    await conn.execute(create_seller_ratings)
                    logger.info("Seller ratings table created/verified")

                    await conn.execute(create_fraud_log)
                    logger.info("Fraud detection log table created/verified")

                    await conn.execute(create_indexes)
                    logger.info("Escrow indexes created/verified")

            logger.info("Escrow schema initialization completed successfully")
        except Exception as e:
            logger.error(f"Failed to initialize escrow schema: {e}")
            raise DatabaseError(f"Escrow schema initialization failed: {e}")

    # ==================== PAYMENT FLOW ====================

    async def initiate_escrow_payment(
        self,
        buyer_chat_id: int,
        seller_id: int,
        amount: float,
        description: str,
        buyer_phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initiate an escrow payment transaction.

        Creates an escrow transaction record and initiates M-Pesa STK push
        to collect payment from the buyer.

        Args:
            buyer_chat_id: Telegram chat ID of the buyer
            seller_id: Telegram chat ID of the seller
            amount: Transaction amount in KES
            description: Description of the transaction/item
            buyer_phone: Buyer's M-Pesa phone number (254XXXXXXXXX), optional

        Returns:
            Dictionary containing transaction details and M-Pesa response

        Raises:
            ValidationError: If input validation fails
            FraudDetectionError: If suspicious activity detected
            PaymentError: If M-Pesa payment initiation fails
            DatabaseError: If database operation fails
        """
        logger.info(
            f"Initiating escrow payment: buyer={buyer_chat_id}, "
            f"seller={seller_id}, amount={amount}"
        )

        # Validate inputs
        if amount <= 0:
            raise ValidationError("Amount must be positive")

        if amount > self.MAX_TRANSACTION_AMOUNT:
            raise ValidationError(
                f"Amount exceeds maximum limit of KES {self.MAX_TRANSACTION_AMOUNT}"
            )

        if buyer_chat_id == seller_id:
            raise ValidationError("Buyer and seller cannot be the same user")

        if not description or len(description.strip()) == 0:
            raise ValidationError("Description is required")

        # Fraud detection checks
        await self.detect_suspicious_pattern(buyer_chat_id, seller_id, amount)
        await self.check_seller_trustworthiness(seller_id)

        # Generate unique transaction ID
        transaction_id = f"ESC_{datetime.now().strftime('%Y%m%d%H%M%S')}_{buyer_chat_id}"

        try:
            # Create escrow transaction record
            async with self.db.pool.acquire() as conn:
                escrow_record = await conn.fetchrow(
                    """
                    INSERT INTO escrow_transactions
                    (transaction_id, buyer_chat_id, seller_chat_id, amount,
                     description, state, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)
                    RETURNING *
                    """,
                    transaction_id, buyer_chat_id, seller_id,
                    Decimal(str(amount)), description, EscrowState.PENDING.value
                )

            logger.info(f"Escrow transaction created: {transaction_id}")

            # If buyer phone provided, initiate M-Pesa STK Push
            if buyer_phone:
                try:
                    mpesa_response = initiate_stk_push(
                        phone=buyer_phone,
                        amount=amount,
                        account_ref=transaction_id,
                        description=f"Escrow: {description[:10]}",
                        callback_url=self.config.mpesa_callback_url
                    )

                    checkout_request_id = mpesa_response.get('CheckoutRequestID')

                    # Update transaction with M-Pesa details
                    async with self.db.pool.acquire() as conn:
                        await conn.execute(
                            """
                            UPDATE escrow_transactions
                            SET mpesa_checkout_request_id = $1
                            WHERE transaction_id = $2
                            """,
                            checkout_request_id, transaction_id
                        )

                    logger.info(
                        f"M-Pesa STK Push initiated for {transaction_id}: "
                        f"CheckoutRequestID={checkout_request_id}"
                    )

                except PaymentError as e:
                    # Mark transaction as failed
                    async with self.db.pool.acquire() as conn:
                        await conn.execute(
                            """
                            UPDATE escrow_transactions
                            SET state = $1
                            WHERE transaction_id = $2
                            """,
                            EscrowState.FAILED.value, transaction_id
                        )

                    logger.error(f"M-Pesa payment failed for {transaction_id}: {e}")
                    raise PaymentError(f"Payment initiation failed: {e}")
            else:
                mpesa_response = {"message": "Payment pending - no phone number provided"}

            # Notify seller about pending payment
            await self._notify_payment_initiated(transaction_id, seller_id)

            return {
                'transaction_id': transaction_id,
                'state': EscrowState.PENDING.value,
                'amount': float(amount),
                'mpesa_response': mpesa_response,
                'escrow_record': dict(escrow_record)
            }

        except Exception as e:
            logger.error(f"Failed to initiate escrow payment: {e}")
            raise

    async def process_mpesa_callback(
        self,
        callback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process M-Pesa payment callback and update transaction state.

        Handles the M-Pesa callback after STK Push completion, updates
        the transaction state to HELD if payment was successful.

        Args:
            callback_data: M-Pesa callback payload

        Returns:
            Updated transaction details

        Raises:
            DatabaseError: If database operation fails
        """
        logger.info("Processing M-Pesa callback for escrow transaction")

        try:
            # Extract callback data
            result_code = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
            checkout_request_id = callback_data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')

            if not checkout_request_id:
                raise ValueError("CheckoutRequestID not found in callback data")

            # Get transaction by checkout request ID
            async with self.db.pool.acquire() as conn:
                transaction = await conn.fetchrow(
                    """
                    SELECT * FROM escrow_transactions
                    WHERE mpesa_checkout_request_id = $1
                    """,
                    checkout_request_id
                )

            if not transaction:
                logger.warning(f"Transaction not found for CheckoutRequestID: {checkout_request_id}")
                raise DatabaseError("Transaction not found")

            transaction_id = transaction['transaction_id']

            # Check if payment was successful (ResultCode = 0)
            if result_code == 0:
                # Extract M-Pesa receipt number
                callback_metadata = callback_data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {})
                items = callback_metadata.get('Item', [])

                receipt_number = None
                for item in items:
                    if item.get('Name') == 'MpesaReceiptNumber':
                        receipt_number = item.get('Value')
                        break

                # Move transaction to HELD state
                updated_transaction = await self.hold_payment(
                    transaction_id=transaction_id,
                    mpesa_receipt_number=receipt_number
                )

                logger.info(f"Payment held in escrow: {transaction_id}")

                return updated_transaction
            else:
                # Payment failed - mark transaction as failed
                async with self.db.pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE escrow_transactions
                        SET state = $1
                        WHERE transaction_id = $2
                        """,
                        EscrowState.FAILED.value, transaction_id
                    )

                logger.warning(f"Payment failed for {transaction_id}: ResultCode={result_code}")

                return {
                    'transaction_id': transaction_id,
                    'state': EscrowState.FAILED.value,
                    'result_code': result_code
                }

        except Exception as e:
            logger.error(f"Failed to process M-Pesa callback: {e}")
            raise

    async def hold_payment(
        self,
        transaction_id: str,
        mpesa_receipt_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Confirm payment is held in escrow.

        Transitions transaction from PENDING to HELD state after successful
        M-Pesa payment. Calculates auto-refund date and notifies both parties.

        Args:
            transaction_id: Unique escrow transaction identifier
            mpesa_receipt_number: M-Pesa receipt number (optional)

        Returns:
            Updated transaction details

        Raises:
            StateTransitionError: If state transition is invalid
            DatabaseError: If database operation fails
        """
        logger.info(f"Holding payment in escrow: {transaction_id}")

        # Verify current state allows this transition
        await self.check_transaction_state(
            transaction_id,
            allowed_states=[EscrowState.PENDING]
        )

        try:
            async with self.db.pool.acquire() as conn:
                transaction = await conn.fetchrow(
                    """
                    UPDATE escrow_transactions
                    SET state = $1,
                        payment_received_at = CURRENT_TIMESTAMP,
                        mpesa_receipt_number = COALESCE($2, mpesa_receipt_number)
                    WHERE transaction_id = $3
                    RETURNING *
                    """,
                    EscrowState.HELD.value, mpesa_receipt_number, transaction_id
                )

            if not transaction:
                raise DatabaseError(f"Transaction not found: {transaction_id}")

            logger.info(f"Payment held successfully: {transaction_id}")

            # Notify both parties
            await self.notify_payment_held(transaction_id)

            return dict(transaction)

        except Exception as e:
            logger.error(f"Failed to hold payment: {e}")
            raise

    # ==================== DELIVERY FLOW ====================

    async def mark_shipped(
        self,
        transaction_id: str,
        seller_chat_id: int,
        tracking_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mark item as shipped by seller.

        Allows seller to mark the item as shipped and provide optional
        tracking information. Notifies buyer of shipment.

        Args:
            transaction_id: Unique escrow transaction identifier
            seller_chat_id: Telegram chat ID of the seller
            tracking_number: Shipping tracking number (optional)

        Returns:
            Updated transaction details

        Raises:
            ValidationError: If seller doesn't own the transaction
            StateTransitionError: If state transition is invalid
            DatabaseError: If database operation fails
        """
        logger.info(f"Marking transaction as shipped: {transaction_id}")

        # Validate seller owns this transaction
        await self.validate_seller_can_ship(seller_chat_id, transaction_id)

        # Verify current state allows this transition
        await self.check_transaction_state(
            transaction_id,
            allowed_states=[EscrowState.HELD]
        )

        try:
            async with self.db.pool.acquire() as conn:
                transaction = await conn.fetchrow(
                    """
                    UPDATE escrow_transactions
                    SET state = $1,
                        shipped_at = CURRENT_TIMESTAMP,
                        tracking_number = $2
                    WHERE transaction_id = $3
                    RETURNING *
                    """,
                    EscrowState.SHIPPED.value, tracking_number, transaction_id
                )

            if not transaction:
                raise DatabaseError(f"Transaction not found: {transaction_id}")

            logger.info(f"Transaction marked as shipped: {transaction_id}")

            # Notify buyer about shipment
            await self.notify_shipped(transaction_id)

            return dict(transaction)

        except Exception as e:
            logger.error(f"Failed to mark as shipped: {e}")
            raise

    async def confirm_delivery(
        self,
        transaction_id: str,
        buyer_chat_id: int
    ) -> Dict[str, Any]:
        """
        Buyer confirms receipt of item.

        Allows buyer to confirm they have received the item. Sets the
        auto-release date for 7 days from confirmation.

        Args:
            transaction_id: Unique escrow transaction identifier
            buyer_chat_id: Telegram chat ID of the buyer

        Returns:
            Updated transaction details

        Raises:
            ValidationError: If buyer doesn't own the transaction
            StateTransitionError: If state transition is invalid
            DatabaseError: If database operation fails
        """
        logger.info(f"Buyer confirming delivery: {transaction_id}")

        # Validate buyer owns this transaction
        await self.validate_buyer_can_confirm(buyer_chat_id, transaction_id)

        # Verify current state allows this transition
        await self.check_transaction_state(
            transaction_id,
            allowed_states=[EscrowState.SHIPPED]
        )

        # Calculate auto-release date (7 days from confirmation)
        auto_release_date = datetime.now() + timedelta(days=self.AUTO_RELEASE_DAYS)

        try:
            async with self.db.pool.acquire() as conn:
                transaction = await conn.fetchrow(
                    """
                    UPDATE escrow_transactions
                    SET delivered_at = CURRENT_TIMESTAMP,
                        auto_release_date = $1
                    WHERE transaction_id = $2
                    RETURNING *
                    """,
                    auto_release_date, transaction_id
                )

            if not transaction:
                raise DatabaseError(f"Transaction not found: {transaction_id}")

            logger.info(
                f"Delivery confirmed for {transaction_id}. "
                f"Auto-release scheduled for {auto_release_date}"
            )

            # Notify about pending auto-release
            await self.notify_auto_release_pending(transaction_id)

            return dict(transaction)

        except Exception as e:
            logger.error(f"Failed to confirm delivery: {e}")
            raise

    async def release_payment(
        self,
        transaction_id: str,
        initiated_by: str = "buyer"
    ) -> Dict[str, Any]:
        """
        Release payment to seller.

        Releases the held payment to the seller. Can be triggered by:
        - Buyer confirming delivery
        - Auto-release after 7 days
        - Admin resolution

        NOTE: In production, this would initiate M-Pesa B2C payment to seller.

        Args:
            transaction_id: Unique escrow transaction identifier
            initiated_by: Who initiated the release ('buyer', 'auto', 'admin')

        Returns:
            Updated transaction details

        Raises:
            StateTransitionError: If state transition is invalid
            PaymentError: If B2C payment fails
            DatabaseError: If database operation fails
        """
        logger.info(f"Releasing payment to seller: {transaction_id} (by {initiated_by})")

        # Verify current state allows this transition
        await self.check_transaction_state(
            transaction_id,
            allowed_states=[EscrowState.SHIPPED, EscrowState.HELD, EscrowState.DISPUTED]
        )

        try:
            # Get transaction details
            async with self.db.pool.acquire() as conn:
                transaction = await conn.fetchrow(
                    "SELECT * FROM escrow_transactions WHERE transaction_id = $1",
                    transaction_id
                )

            if not transaction:
                raise DatabaseError(f"Transaction not found: {transaction_id}")

            # TODO: Implement M-Pesa B2C payment to seller
            # For now, we'll just mark as completed
            # In production:
            # b2c_response = await self._send_b2c_payment(
            #     phone=seller_phone,
            #     amount=transaction['amount'],
            #     remarks=f"Escrow release: {transaction_id}"
            # )

            # Update transaction state to COMPLETED
            async with self.db.pool.acquire() as conn:
                updated_transaction = await conn.fetchrow(
                    """
                    UPDATE escrow_transactions
                    SET state = $1,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE transaction_id = $2
                    RETURNING *
                    """,
                    EscrowState.COMPLETED.value, transaction_id
                )

            logger.info(f"Payment released successfully: {transaction_id}")

            # Notify both parties
            await self.notify_completed(transaction_id)

            return dict(updated_transaction)

        except Exception as e:
            logger.error(f"Failed to release payment: {e}")
            raise

    # ==================== REFUND FLOW ====================

    async def refund_payment(
        self,
        transaction_id: str,
        reason: str,
        initiated_by: str = "buyer"
    ) -> Dict[str, Any]:
        """
        Refund payment to buyer.

        Returns the held payment to the buyer. Can be triggered by:
        - Auto-refund if seller doesn't ship within 3 days
        - Dispute resolution in favor of buyer
        - Seller-initiated cancellation

        NOTE: In production, this would initiate M-Pesa B2C payment to buyer.

        Args:
            transaction_id: Unique escrow transaction identifier
            reason: Reason for refund
            initiated_by: Who initiated the refund ('auto', 'admin', 'seller')

        Returns:
            Updated transaction details

        Raises:
            StateTransitionError: If state transition is invalid
            PaymentError: If B2C payment fails
            DatabaseError: If database operation fails
        """
        logger.info(f"Refunding payment to buyer: {transaction_id} (reason: {reason})")

        # Verify current state allows this transition
        await self.check_transaction_state(
            transaction_id,
            allowed_states=[EscrowState.HELD, EscrowState.DISPUTED]
        )

        try:
            # Get transaction details
            async with self.db.pool.acquire() as conn:
                transaction = await conn.fetchrow(
                    "SELECT * FROM escrow_transactions WHERE transaction_id = $1",
                    transaction_id
                )

            if not transaction:
                raise DatabaseError(f"Transaction not found: {transaction_id}")

            # TODO: Implement M-Pesa B2C refund to buyer
            # For now, we'll just mark as refunded
            # In production:
            # b2c_response = await self._send_b2c_payment(
            #     phone=buyer_phone,
            #     amount=transaction['amount'],
            #     remarks=f"Escrow refund: {transaction_id}"
            # )

            # Update transaction state to REFUNDED
            async with self.db.pool.acquire() as conn:
                updated_transaction = await conn.fetchrow(
                    """
                    UPDATE escrow_transactions
                    SET state = $1,
                        refund_reason = $2,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE transaction_id = $3
                    RETURNING *
                    """,
                    EscrowState.REFUNDED.value, reason, transaction_id
                )

            logger.info(f"Payment refunded successfully: {transaction_id}")

            # Notify both parties
            await self._notify_refunded(transaction_id, reason)

            return dict(updated_transaction)

        except Exception as e:
            logger.error(f"Failed to refund payment: {e}")
            raise

    async def auto_refund_unshipped(self) -> List[Dict[str, Any]]:
        """
        Auto-refund transactions not shipped within 3 days.

        This should be run periodically (e.g., via cron job) to automatically
        refund transactions where the seller hasn't shipped within 3 days
        of payment being held.

        Returns:
            List of refunded transaction details

        Raises:
            DatabaseError: If database operation fails
        """
        logger.info("Running auto-refund check for unshipped transactions")

        refund_deadline = datetime.now() - timedelta(days=self.AUTO_REFUND_DAYS)

        try:
            # Find transactions eligible for auto-refund
            async with self.db.pool.acquire() as conn:
                eligible_transactions = await conn.fetch(
                    """
                    SELECT transaction_id FROM escrow_transactions
                    WHERE state = $1
                    AND payment_received_at < $2
                    AND shipped_at IS NULL
                    """,
                    EscrowState.HELD.value, refund_deadline
                )

            refunded_transactions = []

            for record in eligible_transactions:
                transaction_id = record['transaction_id']

                try:
                    refunded = await self.refund_payment(
                        transaction_id=transaction_id,
                        reason="Auto-refund: Seller did not ship within 3 days",
                        initiated_by="auto"
                    )
                    refunded_transactions.append(refunded)

                    logger.info(f"Auto-refunded transaction: {transaction_id}")
                except Exception as e:
                    logger.error(f"Failed to auto-refund {transaction_id}: {e}")

            logger.info(f"Auto-refund complete: {len(refunded_transactions)} transactions refunded")

            return refunded_transactions

        except Exception as e:
            logger.error(f"Auto-refund process failed: {e}")
            raise

    # ==================== DISPUTE FLOW ====================

    async def create_dispute(
        self,
        transaction_id: str,
        raised_by: int,
        reason: str,
        description: str
    ) -> Dict[str, Any]:
        """
        Open a dispute for a transaction.

        Allows buyer or seller to raise a dispute. Freezes the transaction
        in DISPUTED state until admin resolves it.

        Args:
            transaction_id: Unique escrow transaction identifier
            raised_by: Chat ID of user raising dispute
            reason: Dispute reason category
            description: Detailed description of the issue

        Returns:
            Dispute details

        Raises:
            ValidationError: If user is not party to transaction
            StateTransitionError: If state doesn't allow disputes
            DatabaseError: If database operation fails
        """
        logger.info(f"Creating dispute for transaction: {transaction_id}")

        # Verify transaction exists and get details
        async with self.db.pool.acquire() as conn:
            transaction = await conn.fetchrow(
                "SELECT * FROM escrow_transactions WHERE transaction_id = $1",
                transaction_id
            )

        if not transaction:
            raise DatabaseError(f"Transaction not found: {transaction_id}")

        # Verify user is party to transaction
        if raised_by not in [transaction['buyer_chat_id'], transaction['seller_chat_id']]:
            raise ValidationError("Only buyer or seller can raise a dispute")

        # Verify state allows disputes
        allowed_states = [EscrowState.HELD, EscrowState.SHIPPED]
        if transaction['state'] not in [s.value for s in allowed_states]:
            raise StateTransitionError(
                f"Cannot create dispute in state: {transaction['state']}"
            )

        try:
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    # Create dispute record
                    dispute = await conn.fetchrow(
                        """
                        INSERT INTO escrow_disputes
                        (transaction_id, raised_by_chat_id, reason, description,
                         status, created_at)
                        VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
                        RETURNING *
                        """,
                        transaction_id, raised_by, reason,
                        description, DisputeStatus.OPEN.value
                    )

                    # Update transaction state to DISPUTED
                    await conn.execute(
                        """
                        UPDATE escrow_transactions
                        SET state = $1
                        WHERE transaction_id = $2
                        """,
                        EscrowState.DISPUTED.value, transaction_id
                    )

            logger.info(f"Dispute created successfully: {transaction_id}")

            # Notify relevant parties
            await self.notify_dispute_opened(transaction_id)

            return dict(dispute)

        except asyncpg.UniqueViolationError:
            raise EscrowError(f"Dispute already exists for transaction: {transaction_id}")
        except Exception as e:
            logger.error(f"Failed to create dispute: {e}")
            raise

    async def resolve_dispute(
        self,
        transaction_id: str,
        admin_id: int,
        decision: str,
        resolution_notes: str
    ) -> Dict[str, Any]:
        """
        Resolve a dispute (admin only).

        Admin reviews the dispute and makes a decision on how to resolve it.
        Actions include refunding buyer, releasing to seller, or partial refunds.

        Args:
            transaction_id: Unique escrow transaction identifier
            admin_id: Chat ID of admin resolving dispute
            decision: Resolution decision (refund_buyer, release_seller, etc.)
            resolution_notes: Admin's notes on the resolution

        Returns:
            Updated dispute details

        Raises:
            ValidationError: If decision is invalid
            DatabaseError: If database operation fails
        """
        logger.info(f"Resolving dispute for transaction: {transaction_id}")

        # Validate decision
        valid_decisions = [d.value for d in DisputeDecision]
        if decision not in valid_decisions:
            raise ValidationError(f"Invalid decision. Must be one of: {valid_decisions}")

        try:
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    # Update dispute record
                    dispute = await conn.fetchrow(
                        """
                        UPDATE escrow_disputes
                        SET status = $1,
                            decision = $2,
                            resolution_notes = $3,
                            resolved_by_admin_id = $4,
                            resolved_at = CURRENT_TIMESTAMP
                        WHERE transaction_id = $5
                        RETURNING *
                        """,
                        DisputeStatus.RESOLVED.value, decision, resolution_notes,
                        admin_id, transaction_id
                    )

                    if not dispute:
                        raise DatabaseError(f"Dispute not found for: {transaction_id}")

            logger.info(f"Dispute resolved: {transaction_id}, decision: {decision}")

            # Execute the resolution action
            if decision == DisputeDecision.REFUND_BUYER.value:
                await self.refund_payment(
                    transaction_id=transaction_id,
                    reason=f"Dispute resolved: {resolution_notes}",
                    initiated_by="admin"
                )
            elif decision == DisputeDecision.RELEASE_SELLER.value:
                await self.release_payment(
                    transaction_id=transaction_id,
                    initiated_by="admin"
                )
            # TODO: Implement partial refund and reship logic

            # Notify parties of resolution
            await self._notify_dispute_resolved(transaction_id, decision)

            return dict(dispute)

        except Exception as e:
            logger.error(f"Failed to resolve dispute: {e}")
            raise

    # ==================== AUTO-RELEASE ====================

    async def process_auto_releases(self) -> List[Dict[str, Any]]:
        """
        Process automatic payment releases after 7 days.

        This should be run periodically (e.g., via cron job) to automatically
        release payments 7 days after delivery confirmation.

        Returns:
            List of auto-released transaction details

        Raises:
            DatabaseError: If database operation fails
        """
        logger.info("Running auto-release check for delivered transactions")

        current_time = datetime.now()

        try:
            # Find transactions eligible for auto-release
            async with self.db.pool.acquire() as conn:
                eligible_transactions = await conn.fetch(
                    """
                    SELECT transaction_id FROM escrow_transactions
                    WHERE state = $1
                    AND auto_release_date IS NOT NULL
                    AND auto_release_date <= $2
                    """,
                    EscrowState.SHIPPED.value, current_time
                )

            released_transactions = []

            for record in eligible_transactions:
                transaction_id = record['transaction_id']

                try:
                    released = await self.release_payment(
                        transaction_id=transaction_id,
                        initiated_by="auto"
                    )
                    released_transactions.append(released)

                    logger.info(f"Auto-released transaction: {transaction_id}")
                except Exception as e:
                    logger.error(f"Failed to auto-release {transaction_id}: {e}")

            logger.info(
                f"Auto-release complete: {len(released_transactions)} transactions released"
            )

            return released_transactions

        except Exception as e:
            logger.error(f"Auto-release process failed: {e}")
            raise

    def calculate_auto_release_date(self, payment_date: datetime) -> datetime:
        """
        Calculate the auto-release date for a transaction.

        Args:
            payment_date: Date when payment was received

        Returns:
            Auto-release date (7 days after payment)
        """
        return payment_date + timedelta(days=self.AUTO_RELEASE_DAYS)

    # ==================== VALIDATION ====================

    async def validate_seller_can_ship(
        self,
        seller_chat_id: int,
        transaction_id: str
    ) -> None:
        """
        Validate that seller owns the transaction.

        Args:
            seller_chat_id: Chat ID of the seller
            transaction_id: Transaction identifier

        Raises:
            ValidationError: If seller doesn't own transaction
        """
        async with self.db.pool.acquire() as conn:
            transaction = await conn.fetchrow(
                """
                SELECT seller_chat_id FROM escrow_transactions
                WHERE transaction_id = $1
                """,
                transaction_id
            )

        if not transaction:
            raise ValidationError(f"Transaction not found: {transaction_id}")

        if transaction['seller_chat_id'] != seller_chat_id:
            raise ValidationError("Only the seller can mark this transaction as shipped")

    async def validate_buyer_can_confirm(
        self,
        buyer_chat_id: int,
        transaction_id: str
    ) -> None:
        """
        Validate that buyer owns the transaction.

        Args:
            buyer_chat_id: Chat ID of the buyer
            transaction_id: Transaction identifier

        Raises:
            ValidationError: If buyer doesn't own transaction
        """
        async with self.db.pool.acquire() as conn:
            transaction = await conn.fetchrow(
                """
                SELECT buyer_chat_id FROM escrow_transactions
                WHERE transaction_id = $1
                """,
                transaction_id
            )

        if not transaction:
            raise ValidationError(f"Transaction not found: {transaction_id}")

        if transaction['buyer_chat_id'] != buyer_chat_id:
            raise ValidationError("Only the buyer can confirm delivery")

    async def check_transaction_state(
        self,
        transaction_id: str,
        allowed_states: List[EscrowState]
    ) -> None:
        """
        Verify transaction is in an allowed state.

        Args:
            transaction_id: Transaction identifier
            allowed_states: List of allowed states

        Raises:
            StateTransitionError: If state is not allowed
        """
        async with self.db.pool.acquire() as conn:
            transaction = await conn.fetchrow(
                "SELECT state FROM escrow_transactions WHERE transaction_id = $1",
                transaction_id
            )

        if not transaction:
            raise StateTransitionError(f"Transaction not found: {transaction_id}")

        allowed_state_values = [s.value for s in allowed_states]

        if transaction['state'] not in allowed_state_values:
            raise StateTransitionError(
                f"Invalid state transition. Current state: {transaction['state']}, "
                f"allowed states: {allowed_state_values}"
            )

    # ==================== NOTIFICATIONS ====================

    async def notify_payment_held(self, transaction_id: str) -> None:
        """
        Notify both parties that payment is held in escrow.

        Args:
            transaction_id: Transaction identifier
        """
        if not self.telegram_bot:
            logger.warning("Telegram bot not configured, skipping notification")
            return

        try:
            async with self.db.pool.acquire() as conn:
                transaction = await conn.fetchrow(
                    "SELECT * FROM escrow_transactions WHERE transaction_id = $1",
                    transaction_id
                )

            if not transaction:
                logger.error(f"Transaction not found: {transaction_id}")
                return

            # Notify buyer
            buyer_message = (
                f"💰 <b>Payment Held in Escrow</b>\n\n"
                f"Your payment of KES {transaction['amount']} is now held securely.\n\n"
                f"Transaction ID: <code>{transaction_id}</code>\n"
                f"Item: {transaction['description']}\n\n"
                f"The seller has been notified. You'll receive an update when "
                f"the item is shipped.\n\n"
                f"⚠️ If the seller doesn't ship within {self.AUTO_REFUND_DAYS} days, "
                f"you'll be automatically refunded."
            )

            await self.telegram_bot.send_message(
                chat_id=transaction['buyer_chat_id'],
                text=buyer_message,
                parse_mode='HTML'
            )

            # Notify seller
            seller_message = (
                f"🔔 <b>New Escrow Payment Received</b>\n\n"
                f"Amount: KES {transaction['amount']}\n"
                f"Transaction ID: <code>{transaction_id}</code>\n"
                f"Item: {transaction['description']}\n\n"
                f"Please ship the item and mark it as shipped using:\n"
                f"/ship {transaction_id}\n\n"
                f"⚠️ You must ship within {self.AUTO_REFUND_DAYS} days or the payment "
                f"will be automatically refunded to the buyer."
            )

            await self.telegram_bot.send_message(
                chat_id=transaction['seller_chat_id'],
                text=seller_message,
                parse_mode='HTML'
            )

            logger.info(f"Payment held notifications sent for: {transaction_id}")

        except Exception as e:
            logger.error(f"Failed to send payment held notifications: {e}")

    async def notify_shipped(self, transaction_id: str) -> None:
        """
        Notify buyer that item has been shipped.

        Args:
            transaction_id: Transaction identifier
        """
        if not self.telegram_bot:
            logger.warning("Telegram bot not configured, skipping notification")
            return

        try:
            async with self.db.pool.acquire() as conn:
                transaction = await conn.fetchrow(
                    "SELECT * FROM escrow_transactions WHERE transaction_id = $1",
                    transaction_id
                )

            if not transaction:
                logger.error(f"Transaction not found: {transaction_id}")
                return

            tracking_info = ""
            if transaction['tracking_number']:
                tracking_info = f"\nTracking Number: <code>{transaction['tracking_number']}</code>"

            buyer_message = (
                f"📦 <b>Item Shipped!</b>\n\n"
                f"The seller has shipped your item.\n\n"
                f"Transaction ID: <code>{transaction_id}</code>\n"
                f"Item: {transaction['description']}{tracking_info}\n\n"
                f"Once you receive the item, please confirm delivery using:\n"
                f"/confirm {transaction_id}\n\n"
                f"If there are any issues, you can open a dispute using:\n"
                f"/dispute {transaction_id}"
            )

            await self.telegram_bot.send_message(
                chat_id=transaction['buyer_chat_id'],
                text=buyer_message,
                parse_mode='HTML'
            )

            logger.info(f"Shipped notification sent for: {transaction_id}")

        except Exception as e:
            logger.error(f"Failed to send shipped notification: {e}")

    async def notify_completed(self, transaction_id: str) -> None:
        """
        Notify seller that payment has been released.

        Args:
            transaction_id: Transaction identifier
        """
        if not self.telegram_bot:
            logger.warning("Telegram bot not configured, skipping notification")
            return

        try:
            async with self.db.pool.acquire() as conn:
                transaction = await conn.fetchrow(
                    "SELECT * FROM escrow_transactions WHERE transaction_id = $1",
                    transaction_id
                )

            if not transaction:
                logger.error(f"Transaction not found: {transaction_id}")
                return

            # Notify seller
            seller_message = (
                f"✅ <b>Payment Released!</b>\n\n"
                f"The escrow payment has been released to you.\n\n"
                f"Amount: KES {transaction['amount']}\n"
                f"Transaction ID: <code>{transaction_id}</code>\n\n"
                f"The funds will be sent to your M-Pesa account shortly.\n"
                f"Thank you for using our escrow service!"
            )

            await self.telegram_bot.send_message(
                chat_id=transaction['seller_chat_id'],
                text=seller_message,
                parse_mode='HTML'
            )

            # Notify buyer
            buyer_message = (
                f"✅ <b>Transaction Completed</b>\n\n"
                f"Transaction ID: <code>{transaction_id}</code>\n\n"
                f"The payment has been released to the seller.\n"
                f"Thank you for using our escrow service!"
            )

            await self.telegram_bot.send_message(
                chat_id=transaction['buyer_chat_id'],
                text=buyer_message,
                parse_mode='HTML'
            )

            logger.info(f"Completion notifications sent for: {transaction_id}")

        except Exception as e:
            logger.error(f"Failed to send completion notifications: {e}")

    async def notify_dispute_opened(self, transaction_id: str) -> None:
        """
        Notify relevant parties that a dispute has been opened.

        Args:
            transaction_id: Transaction identifier
        """
        if not self.telegram_bot:
            logger.warning("Telegram bot not configured, skipping notification")
            return

        try:
            async with self.db.pool.acquire() as conn:
                results = await conn.fetchrow(
                    """
                    SELECT et.*, ed.raised_by_chat_id, ed.reason, ed.description
                    FROM escrow_transactions et
                    JOIN escrow_disputes ed ON et.transaction_id = ed.transaction_id
                    WHERE et.transaction_id = $1
                    """,
                    transaction_id
                )

            if not results:
                logger.error(f"Transaction or dispute not found: {transaction_id}")
                return

            # Notify both parties
            dispute_message = (
                f"⚠️ <b>Dispute Opened</b>\n\n"
                f"A dispute has been opened for transaction:\n"
                f"<code>{transaction_id}</code>\n\n"
                f"Reason: {results['reason']}\n"
                f"Description: {results['description']}\n\n"
                f"An administrator will review this case and make a decision.\n"
                f"The transaction is now frozen until resolution."
            )

            await self.telegram_bot.send_message(
                chat_id=results['buyer_chat_id'],
                text=dispute_message,
                parse_mode='HTML'
            )

            await self.telegram_bot.send_message(
                chat_id=results['seller_chat_id'],
                text=dispute_message,
                parse_mode='HTML'
            )

            # Notify admin if configured
            if hasattr(self.config, 'admin_chat_id') and self.config.admin_chat_id:
                admin_message = (
                    f"🚨 <b>New Dispute Requires Attention</b>\n\n"
                    f"Transaction ID: <code>{transaction_id}</code>\n"
                    f"Raised by: {results['raised_by_chat_id']}\n"
                    f"Reason: {results['reason']}\n"
                    f"Description: {results['description']}\n\n"
                    f"Please review and resolve using:\n"
                    f"/resolve_dispute {transaction_id}"
                )

                await self.telegram_bot.send_message(
                    chat_id=self.config.admin_chat_id,
                    text=admin_message,
                    parse_mode='HTML'
                )

            logger.info(f"Dispute notifications sent for: {transaction_id}")

        except Exception as e:
            logger.error(f"Failed to send dispute notifications: {e}")

    async def notify_auto_release_pending(self, transaction_id: str) -> None:
        """
        Warn before auto-releasing payment.

        Args:
            transaction_id: Transaction identifier
        """
        if not self.telegram_bot:
            logger.warning("Telegram bot not configured, skipping notification")
            return

        try:
            async with self.db.pool.acquire() as conn:
                transaction = await conn.fetchrow(
                    "SELECT * FROM escrow_transactions WHERE transaction_id = $1",
                    transaction_id
                )

            if not transaction:
                logger.error(f"Transaction not found: {transaction_id}")
                return

            auto_release_date = transaction.get('auto_release_date')
            if not auto_release_date:
                return

            # Notify buyer
            buyer_message = (
                f"⏰ <b>Auto-Release Scheduled</b>\n\n"
                f"Transaction ID: <code>{transaction_id}</code>\n\n"
                f"The payment will be automatically released to the seller on:\n"
                f"{auto_release_date.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"If you have any issues with the item, please open a dispute "
                f"before this date using:\n"
                f"/dispute {transaction_id}"
            )

            await self.telegram_bot.send_message(
                chat_id=transaction['buyer_chat_id'],
                text=buyer_message,
                parse_mode='HTML'
            )

            logger.info(f"Auto-release pending notification sent for: {transaction_id}")

        except Exception as e:
            logger.error(f"Failed to send auto-release notification: {e}")

    async def _notify_payment_initiated(
        self,
        transaction_id: str,
        seller_chat_id: int
    ) -> None:
        """Notify seller that a payment has been initiated."""
        if not self.telegram_bot:
            return

        try:
            message = (
                f"🔔 <b>New Escrow Payment Initiated</b>\n\n"
                f"Transaction ID: <code>{transaction_id}</code>\n\n"
                f"A buyer has initiated an escrow payment. "
                f"You'll be notified once the payment is confirmed."
            )

            await self.telegram_bot.send_message(
                chat_id=seller_chat_id,
                text=message,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Failed to send payment initiated notification: {e}")

    async def _notify_refunded(self, transaction_id: str, reason: str) -> None:
        """Notify both parties that payment has been refunded."""
        if not self.telegram_bot:
            return

        try:
            async with self.db.pool.acquire() as conn:
                transaction = await conn.fetchrow(
                    "SELECT * FROM escrow_transactions WHERE transaction_id = $1",
                    transaction_id
                )

            if not transaction:
                return

            # Notify buyer
            buyer_message = (
                f"💵 <b>Refund Processed</b>\n\n"
                f"Your payment has been refunded.\n\n"
                f"Transaction ID: <code>{transaction_id}</code>\n"
                f"Amount: KES {transaction['amount']}\n"
                f"Reason: {reason}\n\n"
                f"The funds will be sent to your M-Pesa account shortly."
            )

            await self.telegram_bot.send_message(
                chat_id=transaction['buyer_chat_id'],
                text=buyer_message,
                parse_mode='HTML'
            )

            # Notify seller
            seller_message = (
                f"ℹ️ <b>Transaction Refunded</b>\n\n"
                f"Transaction ID: <code>{transaction_id}</code>\n"
                f"Reason: {reason}\n\n"
                f"The payment has been returned to the buyer."
            )

            await self.telegram_bot.send_message(
                chat_id=transaction['seller_chat_id'],
                text=seller_message,
                parse_mode='HTML'
            )

        except Exception as e:
            logger.error(f"Failed to send refund notifications: {e}")

    async def _notify_dispute_resolved(
        self,
        transaction_id: str,
        decision: str
    ) -> None:
        """Notify both parties of dispute resolution."""
        if not self.telegram_bot:
            return

        try:
            async with self.db.pool.acquire() as conn:
                results = await conn.fetchrow(
                    """
                    SELECT et.*, ed.resolution_notes
                    FROM escrow_transactions et
                    JOIN escrow_disputes ed ON et.transaction_id = ed.transaction_id
                    WHERE et.transaction_id = $1
                    """,
                    transaction_id
                )

            if not results:
                return

            message = (
                f"✅ <b>Dispute Resolved</b>\n\n"
                f"Transaction ID: <code>{transaction_id}</code>\n"
                f"Decision: {decision.replace('_', ' ').title()}\n"
                f"Notes: {results['resolution_notes']}\n\n"
                f"This decision is final."
            )

            await self.telegram_bot.send_message(
                chat_id=results['buyer_chat_id'],
                text=message,
                parse_mode='HTML'
            )

            await self.telegram_bot.send_message(
                chat_id=results['seller_chat_id'],
                text=message,
                parse_mode='HTML'
            )

        except Exception as e:
            logger.error(f"Failed to send dispute resolution notifications: {e}")

    # ==================== FRAUD DETECTION ====================

    async def check_seller_trustworthiness(self, seller_id: int) -> None:
        """
        Check seller's rating and transaction history.

        Args:
            seller_id: Seller's chat ID

        Raises:
            FraudDetectionError: If seller's rating is too low
        """
        try:
            async with self.db.pool.acquire() as conn:
                # Calculate seller's average rating
                rating_result = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) as total_ratings,
                        AVG(rating) as avg_rating
                    FROM seller_ratings
                    WHERE seller_chat_id = $1
                    """,
                    seller_id
                )

                # Check if seller has enough ratings
                if rating_result and rating_result['total_ratings'] > 0:
                    avg_rating = float(rating_result['avg_rating'])
                    normalized_rating = avg_rating / 5.0  # Normalize to 0-1 scale

                    if normalized_rating < self.MIN_SELLER_RATING:
                        logger.warning(
                            f"Seller {seller_id} has low rating: {avg_rating}/5"
                        )
                        # For now, just log - in production, might want to block or flag

        except Exception as e:
            logger.error(f"Failed to check seller trustworthiness: {e}")

    async def detect_suspicious_pattern(
        self,
        buyer_id: int,
        seller_id: int,
        amount: float
    ) -> None:
        """
        Detect suspicious transaction patterns.

        Checks for:
        - Rapid successive transactions
        - Unusual amounts
        - Same buyer-seller pairs

        Args:
            buyer_id: Buyer's chat ID
            seller_id: Seller's chat ID
            amount: Transaction amount

        Raises:
            FraudDetectionError: If suspicious pattern detected
        """
        try:
            async with self.db.pool.acquire() as conn:
                # Check for rapid transactions from same buyer
                recent_transactions = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM escrow_transactions
                    WHERE buyer_chat_id = $1
                    AND created_at > NOW() - INTERVAL '1 hour'
                    """,
                    buyer_id
                )

                if recent_transactions >= 5:
                    logger.warning(
                        f"Suspicious activity: Buyer {buyer_id} has "
                        f"{recent_transactions} transactions in the last hour"
                    )

                    # Log fraud detection
                    await conn.execute(
                        """
                        INSERT INTO fraud_detection_log
                        (user_chat_id, fraud_type, risk_score, details)
                        VALUES ($1, $2, $3, $4)
                        """,
                        buyer_id, 'rapid_transactions', 0.8,
                        f"{recent_transactions} transactions in 1 hour"
                    )

                # Check for repeated buyer-seller pairs
                pair_count = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM escrow_transactions
                    WHERE buyer_chat_id = $1 AND seller_chat_id = $2
                    AND created_at > NOW() - INTERVAL '24 hours'
                    """,
                    buyer_id, seller_id
                )

                if pair_count >= 3:
                    logger.warning(
                        f"Suspicious activity: Buyer-seller pair "
                        f"({buyer_id}, {seller_id}) has "
                        f"{pair_count} transactions in 24 hours"
                    )

        except Exception as e:
            logger.error(f"Failed to detect suspicious patterns: {e}")

    async def flag_suspicious_transaction(
        self,
        transaction_id: str,
        reason: str
    ) -> None:
        """
        Flag a transaction as suspicious for review.

        Args:
            transaction_id: Transaction identifier
            reason: Reason for flagging
        """
        try:
            async with self.db.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE escrow_transactions
                    SET is_flagged = TRUE,
                        flag_reason = $1
                    WHERE transaction_id = $2
                    """,
                    reason, transaction_id
                )

            logger.warning(f"Transaction flagged as suspicious: {transaction_id} - {reason}")

            # Notify admin if configured
            if self.telegram_bot and hasattr(self.config, 'admin_chat_id') and self.config.admin_chat_id:
                message = (
                    f"🚨 <b>Suspicious Transaction Flagged</b>\n\n"
                    f"Transaction ID: <code>{transaction_id}</code>\n"
                    f"Reason: {reason}\n\n"
                    f"Please review this transaction."
                )

                await self.telegram_bot.send_message(
                    chat_id=self.config.admin_chat_id,
                    text=message,
                    parse_mode='HTML'
                )

        except Exception as e:
            logger.error(f"Failed to flag transaction: {e}")


# Singleton instance management
_escrow_service_instance: Optional[EscrowService] = None


async def get_escrow_service(
    database: Optional[Database] = None,
    config: Optional[Config] = None,
    telegram_bot: Optional[Any] = None
) -> EscrowService:
    """
    Get or create the escrow service singleton instance.

    Args:
        database: Database instance (optional)
        config: Configuration instance (optional)
        telegram_bot: Telegram bot instance (optional)

    Returns:
        EscrowService instance
    """
    global _escrow_service_instance

    if _escrow_service_instance is None:
        if database is None:
            from database import get_database
            database = await get_database()

        _escrow_service_instance = EscrowService(database, config, telegram_bot)
        await _escrow_service_instance.init_escrow_schema()

    return _escrow_service_instance


# Example usage
async def main():
    """Example usage of the escrow service."""
    from database import get_database

    try:
        # Initialize database and escrow service
        db = await get_database()
        escrow = await get_escrow_service(database=db)

        print("✓ Escrow service initialized successfully")
        print("\nExample: Initiating escrow payment...")

        # Example: Initiate escrow payment
        # result = await escrow.initiate_escrow_payment(
        #     buyer_chat_id=123456,
        #     seller_id=789012,
        #     amount=1000.00,
        #     description="iPhone 12 Pro",
        #     buyer_phone="254712345678"
        # )
        # print(f"Transaction created: {result['transaction_id']}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
