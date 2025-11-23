"""
Supabase PostgreSQL Database Integration Module for M-Pesa Bot

This module handles all database operations for the M-Pesa Telegram bot,
including transaction tracking, user management, and statistics.

Dependencies:
    - asyncpg: For async PostgreSQL operations
    - python-dotenv: For environment variable management
"""

import asyncpg
import os
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database-related errors."""
    pass


class Database:
    """
    Database manager for M-Pesa bot using Supabase PostgreSQL.

    Attributes:
        pool: Connection pool for database operations
        connection_string: PostgreSQL connection string
    """

    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize database manager.

        Args:
            connection_string: PostgreSQL connection string. If not provided,
                             will be read from SUPABASE_DB_URL environment variable.
        """
        self.pool: Optional[asyncpg.Pool] = None
        self.connection_string = connection_string or os.getenv('SUPABASE_DB_URL')

        if not self.connection_string:
            raise DatabaseError(
                "Database connection string not provided. "
                "Set SUPABASE_DB_URL environment variable or pass connection_string parameter."
            )

    async def connect(self) -> None:
        """
        Establish connection pool to the database.

        Raises:
            DatabaseError: If connection fails
        """
        try:
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("Database connection pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create database connection pool: {e}")
            raise DatabaseError(f"Database connection failed: {e}")

    async def disconnect(self) -> None:
        """Close the database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")

    async def init_database(self) -> None:
        """
        Initialize database schema by creating tables if they don't exist.

        Creates:
            - users table: Stores user information and activity
            - transactions table: Stores M-Pesa transaction records

        Raises:
            DatabaseError: If table creation fails
        """
        if not self.pool:
            raise DatabaseError("Database not connected. Call connect() first.")

        create_users_table = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT UNIQUE NOT NULL,
            phone_number VARCHAR(15),
            total_transactions INTEGER DEFAULT 0,
            total_amount DECIMAL(10, 2) DEFAULT 0.00,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT positive_total_transactions CHECK (total_transactions >= 0),
            CONSTRAINT positive_total_amount CHECK (total_amount >= 0)
        );
        """

        create_transactions_table = """
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            transaction_id VARCHAR(100) UNIQUE,
            checkout_request_id VARCHAR(100) UNIQUE NOT NULL,
            phone_number VARCHAR(15) NOT NULL,
            amount DECIMAL(10, 2) NOT NULL,
            status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'success', 'failed')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            user_chat_id BIGINT,
            mpesa_receipt_number VARCHAR(100),
            CONSTRAINT positive_amount CHECK (amount > 0),
            FOREIGN KEY (user_chat_id) REFERENCES users(chat_id) ON DELETE SET NULL
        );
        """

        create_indexes = """
        CREATE INDEX IF NOT EXISTS idx_transactions_checkout_request_id
            ON transactions(checkout_request_id);
        CREATE INDEX IF NOT EXISTS idx_transactions_user_chat_id
            ON transactions(user_chat_id);
        CREATE INDEX IF NOT EXISTS idx_transactions_status
            ON transactions(status);
        CREATE INDEX IF NOT EXISTS idx_transactions_created_at
            ON transactions(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_users_chat_id
            ON users(chat_id);
        """

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(create_users_table)
                    logger.info("Users table created/verified successfully")

                    await conn.execute(create_transactions_table)
                    logger.info("Transactions table created/verified successfully")

                    await conn.execute(create_indexes)
                    logger.info("Database indexes created/verified successfully")

            logger.info("Database initialization completed successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise DatabaseError(f"Failed to initialize database: {e}")

    async def create_or_update_user(
        self,
        chat_id: int,
        phone_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new user or update existing user's last active timestamp.

        Args:
            chat_id: Telegram chat ID of the user
            phone_number: User's phone number (optional)

        Returns:
            Dictionary containing user information

        Raises:
            DatabaseError: If operation fails
        """
        if not self.pool:
            raise DatabaseError("Database not connected. Call connect() first.")

        try:
            async with self.pool.acquire() as conn:
                # Check if user exists
                existing_user = await conn.fetchrow(
                    "SELECT * FROM users WHERE chat_id = $1",
                    chat_id
                )

                if existing_user:
                    # Update existing user
                    update_query = """
                    UPDATE users
                    SET last_active = CURRENT_TIMESTAMP
                    """
                    params = [chat_id]

                    if phone_number:
                        update_query += ", phone_number = $2"
                        params.insert(0, phone_number)
                        update_query += " WHERE chat_id = $" + str(len(params))
                    else:
                        update_query += " WHERE chat_id = $1"

                    update_query += " RETURNING *"

                    user = await conn.fetchrow(update_query, *params)
                    logger.info(f"Updated user with chat_id: {chat_id}")
                else:
                    # Create new user
                    user = await conn.fetchrow(
                        """
                        INSERT INTO users (chat_id, phone_number, last_active)
                        VALUES ($1, $2, CURRENT_TIMESTAMP)
                        RETURNING *
                        """,
                        chat_id, phone_number
                    )
                    logger.info(f"Created new user with chat_id: {chat_id}")

                return dict(user)
        except Exception as e:
            logger.error(f"Failed to create/update user {chat_id}: {e}")
            raise DatabaseError(f"Failed to create/update user: {e}")

    async def save_transaction(
        self,
        checkout_request_id: str,
        phone_number: str,
        amount: float,
        user_chat_id: int,
        transaction_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Save a new M-Pesa payment transaction.

        Args:
            checkout_request_id: Unique checkout request ID from M-Pesa
            phone_number: Phone number used for payment
            amount: Payment amount
            user_chat_id: Telegram chat ID of the user
            transaction_id: M-Pesa transaction ID (optional, set later)

        Returns:
            Dictionary containing transaction information

        Raises:
            DatabaseError: If save operation fails
        """
        if not self.pool:
            raise DatabaseError("Database not connected. Call connect() first.")

        try:
            async with self.pool.acquire() as conn:
                transaction = await conn.fetchrow(
                    """
                    INSERT INTO transactions
                    (transaction_id, checkout_request_id, phone_number, amount,
                     user_chat_id, status, created_at)
                    VALUES ($1, $2, $3, $4, $5, 'pending', CURRENT_TIMESTAMP)
                    RETURNING *
                    """,
                    transaction_id, checkout_request_id, phone_number,
                    Decimal(str(amount)), user_chat_id
                )
                logger.info(
                    f"Saved transaction: checkout_request_id={checkout_request_id}, "
                    f"amount={amount}, user_chat_id={user_chat_id}"
                )
                return dict(transaction)
        except asyncpg.UniqueViolationError:
            logger.warning(
                f"Transaction with checkout_request_id {checkout_request_id} already exists"
            )
            raise DatabaseError("Transaction already exists")
        except Exception as e:
            logger.error(f"Failed to save transaction: {e}")
            raise DatabaseError(f"Failed to save transaction: {e}")

    async def update_transaction_status(
        self,
        checkout_request_id: str,
        status: str,
        transaction_id: Optional[str] = None,
        mpesa_receipt_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update transaction status after M-Pesa callback.

        Args:
            checkout_request_id: Unique checkout request ID from M-Pesa
            status: Transaction status ('success', 'failed', or 'pending')
            transaction_id: M-Pesa transaction ID (optional)
            mpesa_receipt_number: M-Pesa receipt number (optional)

        Returns:
            Dictionary containing updated transaction information

        Raises:
            DatabaseError: If update operation fails
        """
        if not self.pool:
            raise DatabaseError("Database not connected. Call connect() first.")

        if status not in ['pending', 'success', 'failed']:
            raise ValueError("Status must be 'pending', 'success', or 'failed'")

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Update transaction
                    transaction = await conn.fetchrow(
                        """
                        UPDATE transactions
                        SET status = $1,
                            transaction_id = COALESCE($2, transaction_id),
                            mpesa_receipt_number = COALESCE($3, mpesa_receipt_number),
                            completed_at = CASE
                                WHEN $1 IN ('success', 'failed') THEN CURRENT_TIMESTAMP
                                ELSE completed_at
                            END
                        WHERE checkout_request_id = $4
                        RETURNING *
                        """,
                        status, transaction_id, mpesa_receipt_number, checkout_request_id
                    )

                    if not transaction:
                        raise DatabaseError(
                            f"Transaction with checkout_request_id {checkout_request_id} not found"
                        )

                    # If successful, update user statistics
                    if status == 'success' and transaction['user_chat_id']:
                        await conn.execute(
                            """
                            UPDATE users
                            SET total_transactions = total_transactions + 1,
                                total_amount = total_amount + $1,
                                last_active = CURRENT_TIMESTAMP
                            WHERE chat_id = $2
                            """,
                            transaction['amount'], transaction['user_chat_id']
                        )
                        logger.info(
                            f"Updated user statistics for chat_id: {transaction['user_chat_id']}"
                        )

                    logger.info(
                        f"Updated transaction status: checkout_request_id={checkout_request_id}, "
                        f"status={status}"
                    )
                    return dict(transaction)
        except Exception as e:
            logger.error(f"Failed to update transaction status: {e}")
            raise DatabaseError(f"Failed to update transaction status: {e}")

    async def get_transaction_by_checkout_id(
        self,
        checkout_request_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a transaction by its checkout request ID.

        Args:
            checkout_request_id: Unique checkout request ID from M-Pesa

        Returns:
            Dictionary containing transaction information, or None if not found

        Raises:
            DatabaseError: If query fails
        """
        if not self.pool:
            raise DatabaseError("Database not connected. Call connect() first.")

        try:
            async with self.pool.acquire() as conn:
                transaction = await conn.fetchrow(
                    "SELECT * FROM transactions WHERE checkout_request_id = $1",
                    checkout_request_id
                )
                return dict(transaction) if transaction else None
        except Exception as e:
            logger.error(f"Failed to get transaction by checkout_request_id: {e}")
            raise DatabaseError(f"Failed to get transaction: {e}")

    async def get_user_transactions(
        self,
        chat_id: int,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get transaction history for a specific user.

        Args:
            chat_id: Telegram chat ID of the user
            limit: Maximum number of transactions to return
            offset: Number of transactions to skip

        Returns:
            List of dictionaries containing transaction information

        Raises:
            DatabaseError: If query fails
        """
        if not self.pool:
            raise DatabaseError("Database not connected. Call connect() first.")

        try:
            async with self.pool.acquire() as conn:
                transactions = await conn.fetch(
                    """
                    SELECT * FROM transactions
                    WHERE user_chat_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                    """,
                    chat_id, limit, offset
                )
                return [dict(transaction) for transaction in transactions]
        except Exception as e:
            logger.error(f"Failed to get user transactions for chat_id {chat_id}: {e}")
            raise DatabaseError(f"Failed to get user transactions: {e}")

    async def get_all_transactions(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all transactions (admin function).

        Args:
            limit: Maximum number of transactions to return
            offset: Number of transactions to skip
            status: Filter by status ('pending', 'success', 'failed'), or None for all

        Returns:
            List of dictionaries containing transaction information

        Raises:
            DatabaseError: If query fails
        """
        if not self.pool:
            raise DatabaseError("Database not connected. Call connect() first.")

        try:
            async with self.pool.acquire() as conn:
                if status:
                    if status not in ['pending', 'success', 'failed']:
                        raise ValueError("Status must be 'pending', 'success', or 'failed'")

                    transactions = await conn.fetch(
                        """
                        SELECT * FROM transactions
                        WHERE status = $1
                        ORDER BY created_at DESC
                        LIMIT $2 OFFSET $3
                        """,
                        status, limit, offset
                    )
                else:
                    transactions = await conn.fetch(
                        """
                        SELECT * FROM transactions
                        ORDER BY created_at DESC
                        LIMIT $1 OFFSET $2
                        """,
                        limit, offset
                    )

                return [dict(transaction) for transaction in transactions]
        except Exception as e:
            logger.error(f"Failed to get all transactions: {e}")
            raise DatabaseError(f"Failed to get all transactions: {e}")

    async def get_transaction_stats(self) -> Dict[str, Any]:
        """
        Get transaction statistics (admin function).

        Returns:
            Dictionary containing:
                - total_transactions: Total number of transactions
                - successful_transactions: Number of successful transactions
                - failed_transactions: Number of failed transactions
                - pending_transactions: Number of pending transactions
                - total_amount: Total amount from successful transactions
                - success_rate: Percentage of successful transactions
                - average_amount: Average transaction amount

        Raises:
            DatabaseError: If query fails
        """
        if not self.pool:
            raise DatabaseError("Database not connected. Call connect() first.")

        try:
            async with self.pool.acquire() as conn:
                stats = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) as total_transactions,
                        COUNT(*) FILTER (WHERE status = 'success') as successful_transactions,
                        COUNT(*) FILTER (WHERE status = 'failed') as failed_transactions,
                        COUNT(*) FILTER (WHERE status = 'pending') as pending_transactions,
                        COALESCE(SUM(amount) FILTER (WHERE status = 'success'), 0) as total_amount,
                        COALESCE(AVG(amount) FILTER (WHERE status = 'success'), 0) as average_amount
                    FROM transactions
                    """
                )

                result = dict(stats)

                # Calculate success rate
                total = result['total_transactions']
                successful = result['successful_transactions']
                result['success_rate'] = (
                    (successful / total * 100) if total > 0 else 0
                )

                # Convert Decimal to float for JSON serialization
                result['total_amount'] = float(result['total_amount'])
                result['average_amount'] = float(result['average_amount'])

                logger.info("Retrieved transaction statistics")
                return result
        except Exception as e:
            logger.error(f"Failed to get transaction stats: {e}")
            raise DatabaseError(f"Failed to get transaction stats: {e}")

    async def get_user_by_chat_id(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user information by chat ID.

        Args:
            chat_id: Telegram chat ID of the user

        Returns:
            Dictionary containing user information, or None if not found

        Raises:
            DatabaseError: If query fails
        """
        if not self.pool:
            raise DatabaseError("Database not connected. Call connect() first.")

        try:
            async with self.pool.acquire() as conn:
                user = await conn.fetchrow(
                    "SELECT * FROM users WHERE chat_id = $1",
                    chat_id
                )
                return dict(user) if user else None
        except Exception as e:
            logger.error(f"Failed to get user by chat_id {chat_id}: {e}")
            raise DatabaseError(f"Failed to get user: {e}")


# Singleton instance for easy access
_db_instance: Optional[Database] = None


async def get_database(connection_string: Optional[str] = None) -> Database:
    """
    Get or create the database singleton instance.

    Args:
        connection_string: PostgreSQL connection string (optional)

    Returns:
        Database instance
    """
    global _db_instance

    if _db_instance is None:
        _db_instance = Database(connection_string)
        await _db_instance.connect()
        await _db_instance.init_database()

    return _db_instance


async def close_database() -> None:
    """Close the database singleton instance."""
    global _db_instance

    if _db_instance:
        await _db_instance.disconnect()
        _db_instance = None


# Example usage and testing
async def main():
    """Example usage of the database module."""
    try:
        # Initialize database
        db = await get_database()

        # Create/update user
        user = await db.create_or_update_user(
            chat_id=123456789,
            phone_number="254712345678"
        )
        print(f"User created/updated: {user}")

        # Save a transaction
        transaction = await db.save_transaction(
            checkout_request_id="ws_CO_12345",
            phone_number="254712345678",
            amount=100.00,
            user_chat_id=123456789
        )
        print(f"Transaction saved: {transaction}")

        # Update transaction status
        updated_transaction = await db.update_transaction_status(
            checkout_request_id="ws_CO_12345",
            status="success",
            transaction_id="MPX123456",
            mpesa_receipt_number="NLJ7RT61SV"
        )
        print(f"Transaction updated: {updated_transaction}")

        # Get user transactions
        user_transactions = await db.get_user_transactions(chat_id=123456789)
        print(f"User transactions: {user_transactions}")

        # Get statistics
        stats = await db.get_transaction_stats()
        print(f"Transaction stats: {stats}")

    except DatabaseError as e:
        print(f"Database error: {e}")
    finally:
        await close_database()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
