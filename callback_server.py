"""
FastAPI server for handling M-Pesa payment callbacks.

This server receives payment notifications from M-Pesa, processes them,
updates the database, and sends notifications via Telegram.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
import os

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
import aiomysql
from telegram import Bot
from telegram.error import TelegramError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mpesa_callbacks.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="M-Pesa Callback Server",
    description="Handle M-Pesa STK Push callbacks and notifications",
    version="1.0.0"
)

# Configuration from environment variables
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '7805514118:AAHjxdGzS6t5Whfyr7SVY1ogb-OLDHBy1tA')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', None)
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'mpesa_bot')

# Global bot instance
telegram_bot: Optional[Bot] = None


# ==================== Pydantic Models ====================

class CallbackMetadataItem(BaseModel):
    """Individual item in callback metadata."""
    Name: str
    Value: Optional[Any] = None


class CallbackMetadata(BaseModel):
    """Metadata containing payment details."""
    Item: List[CallbackMetadataItem] = Field(default_factory=list)


class StkCallback(BaseModel):
    """M-Pesa STK Push callback structure."""
    MerchantRequestID: str
    CheckoutRequestID: str
    ResultCode: int
    ResultDesc: str
    CallbackMetadata: Optional[CallbackMetadata] = None


class CallbackBody(BaseModel):
    """Body of the M-Pesa callback request."""
    stkCallback: StkCallback


class MpesaCallbackRequest(BaseModel):
    """Complete M-Pesa callback request structure."""
    Body: CallbackBody

    @validator('Body')
    def validate_body(cls, v):
        """Validate that the body contains required callback information."""
        if not v.stkCallback:
            raise ValueError("Missing stkCallback in request body")
        return v


class TransactionDetails(BaseModel):
    """Extracted transaction details from callback."""
    checkout_request_id: str
    merchant_request_id: str
    result_code: int
    result_desc: str
    amount: Optional[float] = None
    mpesa_receipt_number: Optional[str] = None
    phone_number: Optional[str] = None
    transaction_date: Optional[datetime] = None
    balance: Optional[float] = None

    @property
    def is_successful(self) -> bool:
        """Check if the transaction was successful."""
        return self.result_code == 0


# ==================== Database Operations ====================

async def get_db_connection():
    """
    Create and return a database connection.

    Returns:
        aiomysql.Connection: Database connection object

    Raises:
        Exception: If database connection fails
    """
    try:
        connection = await aiomysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            db=DB_NAME,
            autocommit=False
        )
        logger.info("Database connection established")
        return connection
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise


async def update_transaction(transaction: TransactionDetails) -> bool:
    """
    Update transaction status in the database.

    Args:
        transaction: TransactionDetails object with payment information

    Returns:
        bool: True if update successful, False otherwise
    """
    try:
        connection = await get_db_connection()
        async with connection.cursor() as cursor:
            # Check if transaction exists
            await cursor.execute(
                "SELECT id FROM transactions WHERE checkout_request_id = %s",
                (transaction.checkout_request_id,)
            )
            result = await cursor.fetchone()

            if result:
                # Update existing transaction
                update_query = """
                    UPDATE transactions
                    SET result_code = %s,
                        result_desc = %s,
                        amount = %s,
                        mpesa_receipt_number = %s,
                        phone_number = %s,
                        transaction_date = %s,
                        status = %s,
                        updated_at = %s
                    WHERE checkout_request_id = %s
                """
                status_text = 'Success' if transaction.is_successful else 'Failed'

                await cursor.execute(update_query, (
                    transaction.result_code,
                    transaction.result_desc,
                    transaction.amount,
                    transaction.mpesa_receipt_number,
                    transaction.phone_number,
                    transaction.transaction_date,
                    status_text,
                    datetime.now(),
                    transaction.checkout_request_id
                ))
            else:
                # Insert new transaction
                insert_query = """
                    INSERT INTO transactions (
                        checkout_request_id,
                        merchant_request_id,
                        result_code,
                        result_desc,
                        amount,
                        mpesa_receipt_number,
                        phone_number,
                        transaction_date,
                        status,
                        created_at,
                        updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                status_text = 'Success' if transaction.is_successful else 'Failed'
                now = datetime.now()

                await cursor.execute(insert_query, (
                    transaction.checkout_request_id,
                    transaction.merchant_request_id,
                    transaction.result_code,
                    transaction.result_desc,
                    transaction.amount,
                    transaction.mpesa_receipt_number,
                    transaction.phone_number,
                    transaction.transaction_date,
                    status_text,
                    now,
                    now
                ))

            await connection.commit()
            logger.info(f"Transaction {transaction.checkout_request_id} updated successfully")
            return True

    except Exception as e:
        logger.error(f"Failed to update transaction: {e}")
        if connection:
            await connection.rollback()
        return False
    finally:
        if connection:
            connection.close()


# ==================== Telegram Notifications ====================

def get_telegram_bot() -> Bot:
    """
    Get or create Telegram bot instance.

    Returns:
        Bot: Telegram bot instance
    """
    global telegram_bot
    if telegram_bot is None:
        telegram_bot = Bot(token=BOT_TOKEN)
    return telegram_bot


async def send_admin_notification(transaction: TransactionDetails) -> bool:
    """
    Send payment notification to admin via Telegram.

    Args:
        transaction: TransactionDetails object with payment information

    Returns:
        bool: True if notification sent successfully, False otherwise
    """
    if not ADMIN_CHAT_ID:
        logger.warning("Admin chat ID not configured, skipping notification")
        return False

    try:
        bot = get_telegram_bot()

        if transaction.is_successful:
            message = (
                "✅ *Payment Successful*\n\n"
                f"💰 Amount: KES {transaction.amount:,.2f}\n"
                f"📱 Phone: {transaction.phone_number}\n"
                f"🧾 Receipt: {transaction.mpesa_receipt_number}\n"
                f"🆔 Request ID: {transaction.checkout_request_id}\n"
                f"📅 Date: {transaction.transaction_date.strftime('%Y-%m-%d %H:%M:%S') if transaction.transaction_date else 'N/A'}"
            )
        else:
            message = (
                "❌ *Payment Failed*\n\n"
                f"📱 Phone: {transaction.phone_number or 'Unknown'}\n"
                f"🆔 Request ID: {transaction.checkout_request_id}\n"
                f"❗ Reason: {transaction.result_desc}\n"
                f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=message,
            parse_mode='Markdown'
        )
        logger.info(f"Admin notification sent for transaction {transaction.checkout_request_id}")
        return True

    except TelegramError as e:
        logger.error(f"Failed to send admin notification: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending notification: {e}")
        return False


async def send_user_receipt(phone_number: str, transaction: TransactionDetails) -> bool:
    """
    Send payment receipt to user via Telegram.

    Note: This requires the user's Telegram chat ID to be stored in the database.

    Args:
        phone_number: User's phone number
        transaction: TransactionDetails object with payment information

    Returns:
        bool: True if receipt sent successfully, False otherwise
    """
    try:
        # Get user's chat ID from database
        connection = await get_db_connection()
        async with connection.cursor() as cursor:
            await cursor.execute(
                "SELECT telegram_chat_id FROM users WHERE phone_number = %s",
                (phone_number,)
            )
            result = await cursor.fetchone()

        if not result or not result[0]:
            logger.warning(f"No Telegram chat ID found for phone {phone_number}")
            return False

        chat_id = result[0]
        bot = get_telegram_bot()

        message = (
            "🎉 *Payment Receipt*\n\n"
            f"Thank you for your payment!\n\n"
            f"💰 Amount: KES {transaction.amount:,.2f}\n"
            f"🧾 M-Pesa Receipt: {transaction.mpesa_receipt_number}\n"
            f"📅 Date: {transaction.transaction_date.strftime('%Y-%m-%d %H:%M:%S') if transaction.transaction_date else 'N/A'}\n\n"
            f"Transaction ID: {transaction.checkout_request_id}"
        )

        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode='Markdown'
        )
        logger.info(f"Receipt sent to user {phone_number}")
        return True

    except Exception as e:
        logger.error(f"Failed to send user receipt: {e}")
        return False
    finally:
        if connection:
            connection.close()


# ==================== Helper Functions ====================

def extract_callback_metadata(metadata: Optional[CallbackMetadata]) -> Dict[str, Any]:
    """
    Extract metadata items into a dictionary.

    Args:
        metadata: CallbackMetadata object

    Returns:
        Dict containing extracted metadata values
    """
    if not metadata or not metadata.Item:
        return {}

    result = {}
    for item in metadata.Item:
        result[item.Name] = item.Value

    return result


def parse_transaction_details(callback_data: MpesaCallbackRequest) -> TransactionDetails:
    """
    Parse M-Pesa callback data into TransactionDetails object.

    Args:
        callback_data: MpesaCallbackRequest object

    Returns:
        TransactionDetails object with extracted information
    """
    stk_callback = callback_data.Body.stkCallback

    # Extract metadata if available
    metadata = {}
    if stk_callback.CallbackMetadata:
        metadata = extract_callback_metadata(stk_callback.CallbackMetadata)

    # Parse transaction date
    transaction_date = None
    if 'TransactionDate' in metadata:
        try:
            date_str = str(metadata['TransactionDate'])
            transaction_date = datetime.strptime(date_str, '%Y%m%d%H%M%S')
        except Exception as e:
            logger.warning(f"Failed to parse transaction date: {e}")

    return TransactionDetails(
        checkout_request_id=stk_callback.CheckoutRequestID,
        merchant_request_id=stk_callback.MerchantRequestID,
        result_code=stk_callback.ResultCode,
        result_desc=stk_callback.ResultDesc,
        amount=metadata.get('Amount'),
        mpesa_receipt_number=metadata.get('MpesaReceiptNumber'),
        phone_number=str(metadata.get('PhoneNumber')) if metadata.get('PhoneNumber') else None,
        transaction_date=transaction_date,
        balance=metadata.get('Balance')
    )


# ==================== API Endpoints ====================

@app.get("/", tags=["Info"])
async def root():
    """
    Welcome endpoint with API information.

    Returns:
        JSON response with API details and available endpoints
    """
    return {
        "service": "M-Pesa Callback Server",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "callback": "/mpesa/callback",
            "health": "/health",
            "docs": "/docs"
        },
        "description": "FastAPI server for handling M-Pesa payment callbacks and notifications"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.

    Returns:
        JSON response with service health status
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "mpesa-callback-server"
    }

    # Check database connection
    try:
        connection = await get_db_connection()
        connection.close()
        health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    # Check Telegram bot
    try:
        bot = get_telegram_bot()
        me = await bot.get_me()
        health_status["telegram"] = f"connected as @{me.username}"
    except Exception as e:
        health_status["telegram"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    status_code = status.HTTP_200_OK if health_status["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(content=health_status, status_code=status_code)


@app.post("/mpesa/callback", tags=["M-Pesa"])
async def mpesa_callback(request: Request):
    """
    Handle M-Pesa payment callbacks.

    This endpoint receives payment notifications from M-Pesa's STK Push service,
    processes the payment data, updates the database, and sends notifications.

    Args:
        request: FastAPI Request object containing M-Pesa callback data

    Returns:
        JSON response acknowledging receipt of the callback

    Raises:
        HTTPException: If callback processing fails
    """
    try:
        # Get raw request body for logging
        raw_body = await request.body()
        logger.info(f"Received M-Pesa callback: {raw_body.decode('utf-8')}")

        # Parse JSON data
        json_data = await request.json()

        # Validate callback structure
        try:
            callback_data = MpesaCallbackRequest(**json_data)
        except Exception as e:
            logger.error(f"Invalid callback structure: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid callback data structure: {str(e)}"
            )

        # Extract transaction details
        transaction = parse_transaction_details(callback_data)
        logger.info(
            f"Processing transaction {transaction.checkout_request_id} - "
            f"Result: {transaction.result_code} ({transaction.result_desc})"
        )

        # Update database
        db_updated = await update_transaction(transaction)
        if not db_updated:
            logger.error(f"Failed to update database for transaction {transaction.checkout_request_id}")

        # Send admin notification
        await send_admin_notification(transaction)

        # Send receipt to user if successful
        if transaction.is_successful and transaction.phone_number:
            await send_user_receipt(transaction.phone_number, transaction)

        # Log callback summary
        logger.info(
            f"Callback processed successfully - "
            f"CheckoutRequestID: {transaction.checkout_request_id}, "
            f"Status: {'Success' if transaction.is_successful else 'Failed'}, "
            f"Amount: {transaction.amount}, "
            f"Phone: {transaction.phone_number}"
        )

        return {
            "ResultCode": 0,
            "ResultDesc": "Callback received successfully",
            "CheckoutRequestID": transaction.checkout_request_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing M-Pesa callback: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled errors.

    Args:
        request: The request that caused the error
        exc: The exception that was raised

    Returns:
        JSON response with error details
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "path": str(request.url)
        }
    )


# ==================== Startup/Shutdown Events ====================

@app.on_event("startup")
async def startup_event():
    """Initialize resources on application startup."""
    logger.info("M-Pesa Callback Server starting up...")
    logger.info(f"Database: {DB_HOST}/{DB_NAME}")
    logger.info(f"Admin notifications: {'enabled' if ADMIN_CHAT_ID else 'disabled'}")

    # Test database connection
    try:
        connection = await get_db_connection()
        connection.close()
        logger.info("Database connection test successful")
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")

    # Initialize Telegram bot
    try:
        bot = get_telegram_bot()
        me = await bot.get_me()
        logger.info(f"Telegram bot initialized: @{me.username}")
    except Exception as e:
        logger.error(f"Failed to initialize Telegram bot: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on application shutdown."""
    logger.info("M-Pesa Callback Server shutting down...")
    # Add any cleanup code here if needed


if __name__ == "__main__":
    import uvicorn

    # Run the server
    uvicorn.run(
        "callback_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
