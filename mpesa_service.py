"""
M-Pesa Integration Service.

This module provides a comprehensive service layer for integrating with Safaricom's
M-Pesa API, supporting both sandbox and production environments. It includes
functionality for initiating STK Push payments, querying transaction status,
and handling authentication.

Features:
    - Dynamic password and timestamp generation
    - STK Push payment initiation
    - Transaction status queries
    - Automatic retry logic for network failures
    - Support for sandbox and production environments
    - Comprehensive error handling and logging

Example:
    >>> from mpesa_service import initiate_stk_push, query_transaction_status
    >>>
    >>> result = initiate_stk_push(
    ...     phone="254712345678",
    ...     amount=100,
    ...     account_ref="INV001",
    ...     description="Payment for services",
    ...     callback_url="https://example.com/callback"
    ... )
    >>> print(result)
"""

import base64
import logging
import time
from datetime import datetime
from typing import Dict, Optional, Any, Union
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import get_config, Config, ConfigError

# Initialize config with error handling
try:
    config = get_config()
    REQUEST_TIMEOUT = config.api_timeout
    LOG_LEVEL = config.log_level.upper()
    LOG_FILE = config.log_file
except ConfigError:
    # Fallback to defaults if config cannot be loaded
    # This allows the module to be imported for testing
    config = None
    REQUEST_TIMEOUT = 30
    LOG_LEVEL = 'INFO'
    LOG_FILE = 'mpesa_bot.log'

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
MAX_RETRIES = 3
RETRY_DELAY = 2


class MpesaError(Exception):
    """Base exception for M-Pesa related errors."""
    pass


class AuthenticationError(MpesaError):
    """Raised when authentication with M-Pesa API fails."""
    pass


class PaymentError(MpesaError):
    """Raised when payment initiation fails."""
    pass


class QueryError(MpesaError):
    """Raised when transaction status query fails."""
    pass


def _get_session_with_retry() -> requests.Session:
    """
    Create a requests session with automatic retry logic.

    Configures retry strategy for handling transient network errors,
    connection issues, and server errors.

    Returns:
        requests.Session: Configured session with retry adapter.
    """
    session = requests.Session()

    retry_strategy = Retry(
        total=MAX_RETRIES,
        backoff_factor=RETRY_DELAY,
        status_forcelist=[408, 429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


def get_access_token() -> str:
    """
    Authenticate with M-Pesa API and retrieve an access token.

    Makes a request to the M-Pesa OAuth endpoint using consumer key and secret
    credentials. The access token is required for all subsequent API calls.

    Returns:
        str: Valid M-Pesa API access token.

    Raises:
        AuthenticationError: If authentication fails or token cannot be retrieved.

    Example:
        >>> token = get_access_token()
        >>> print(f"Access token: {token[:20]}...")
    """
    if config is None:
        raise AuthenticationError("Configuration not loaded. Please check your .env file.")

    auth_url = config.mpesa_auth_url
    consumer_key = config.mpesa_consumer_key
    consumer_secret = config.mpesa_consumer_secret

    logger.info(f"Requesting M-Pesa access token from {config.mpesa_environment} environment")

    try:
        session = _get_session_with_retry()
        response = session.get(
            auth_url,
            auth=(consumer_key, consumer_secret),
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()

        token_data = response.json()
        access_token = token_data.get('access_token')

        if not access_token:
            raise AuthenticationError("Access token not found in response")

        logger.info("Successfully obtained M-Pesa access token")
        return access_token

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error during authentication: {e}")
        logger.error(f"Response content: {e.response.text if e.response else 'No response'}")
        raise AuthenticationError(f"HTTP error: {e}") from e

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error during authentication: {e}")
        raise AuthenticationError(f"Connection error: {e}") from e

    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout during authentication: {e}")
        raise AuthenticationError(f"Request timeout: {e}") from e

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error during authentication: {e}")
        raise AuthenticationError(f"Request failed: {e}") from e

    except Exception as e:
        logger.error(f"Unexpected error during authentication: {e}")
        raise AuthenticationError(f"Unexpected error: {e}") from e


def generate_timestamp() -> str:
    """
    Generate a timestamp in the format required by M-Pesa API.

    Creates a timestamp string in YYYYMMDDHHmmss format based on the current
    datetime. This timestamp is used for password generation and API requests.

    Returns:
        str: Timestamp in YYYYMMDDHHmmss format.

    Example:
        >>> timestamp = generate_timestamp()
        >>> print(timestamp)
        '20231215143025'
    """
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    logger.debug(f"Generated timestamp: {timestamp}")
    return timestamp


def generate_password(timestamp: Optional[str] = None) -> tuple[str, str]:
    """
    Generate the password required for M-Pesa STK Push requests.

    Creates a Base64-encoded password by combining the business shortcode,
    passkey, and timestamp. If no timestamp is provided, generates a new one.

    Args:
        timestamp: Optional timestamp string in YYYYMMDDHHmmss format.
                  If not provided, a new timestamp will be generated.

    Returns:
        tuple[str, str]: A tuple containing (password, timestamp).
                        - password: Base64-encoded password string
                        - timestamp: The timestamp used for password generation

    Example:
        >>> password, timestamp = generate_password()
        >>> print(f"Password length: {len(password)}")
        >>> print(f"Timestamp: {timestamp}")
    """
    if config is None:
        raise MpesaError("Configuration not loaded. Please check your .env file.")

    shortcode = config.mpesa_shortcode
    passkey = config.mpesa_passkey

    if timestamp is None:
        timestamp = generate_timestamp()

    # Concatenate shortcode + passkey + timestamp
    raw_password = f"{shortcode}{passkey}{timestamp}"

    # Base64 encode the password
    encoded_password = base64.b64encode(raw_password.encode()).decode('utf-8')

    logger.debug(f"Generated password for timestamp {timestamp}")
    return encoded_password, timestamp


def initiate_stk_push(
    phone: str,
    amount: Union[int, float],
    account_ref: str,
    description: str,
    callback_url: str
) -> Dict[str, Any]:
    """
    Initiate an M-Pesa STK Push payment request.

    Sends a payment request to the customer's phone via the M-Pesa STK Push API.
    The customer will receive a prompt on their phone to enter their M-Pesa PIN
    to complete the transaction.

    Args:
        phone: Customer's phone number in format 254XXXXXXXXX (Kenya).
        amount: Amount to be charged (minimum 1).
        account_ref: Account reference/invoice number (max 12 characters).
        description: Transaction description (max 13 characters).
        callback_url: URL to receive payment callback notifications.

    Returns:
        Dict[str, Any]: API response containing:
            - MerchantRequestID: Unique request identifier
            - CheckoutRequestID: Unique checkout identifier (use for status query)
            - ResponseCode: Response code (0 for success)
            - ResponseDescription: Response message
            - CustomerMessage: Message to display to customer

    Raises:
        PaymentError: If payment initiation fails.
        ValueError: If input parameters are invalid.

    Example:
        >>> result = initiate_stk_push(
        ...     phone="254712345678",
        ...     amount=100,
        ...     account_ref="INV001",
        ...     description="Payment",
        ...     callback_url="https://example.com/callback"
        ... )
        >>> print(f"Checkout ID: {result['CheckoutRequestID']}")
    """
    # Validate inputs
    if not phone or not phone.startswith('254'):
        raise ValueError("Phone number must start with 254 (Kenya country code)")

    if len(phone) != 12 or not phone.isdigit():
        raise ValueError("Phone number must be 12 digits (254XXXXXXXXX)")

    if not isinstance(amount, (int, float)) or amount < 1:
        raise ValueError("Amount must be at least 1")

    if not account_ref or len(account_ref) > 12:
        raise ValueError("Account reference must be 1-12 characters")

    if not description or len(description) > 13:
        raise ValueError("Description must be 1-13 characters")

    if not callback_url or not callback_url.startswith(('http://', 'https://')):
        raise ValueError("Valid callback URL is required")

    if config is None:
        raise PaymentError("Configuration not loaded. Please check your .env file.")

    stk_push_url = config.mpesa_stk_push_url
    shortcode = config.mpesa_shortcode
    transaction_type = config.mpesa_transaction_type

    # Generate password and timestamp
    password, timestamp = generate_password()

    # Get access token
    try:
        access_token = get_access_token()
    except AuthenticationError as e:
        logger.error(f"Failed to get access token: {e}")
        raise PaymentError(f"Authentication failed: {e}") from e

    # Prepare request headers
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    # Prepare request payload
    payload = {
        'BusinessShortCode': shortcode,
        'Password': password,
        'Timestamp': timestamp,
        'TransactionType': transaction_type,
        'Amount': int(amount),
        'PartyA': phone,
        'PartyB': shortcode,
        'PhoneNumber': phone,
        'CallBackURL': callback_url,
        'AccountReference': account_ref,
        'TransactionDesc': description
    }

    logger.info(f"Initiating STK Push: Phone={phone}, Amount={amount}, Ref={account_ref}")
    logger.debug(f"STK Push payload: {payload}")

    try:
        session = _get_session_with_retry()
        response = session.post(
            stk_push_url,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )

        response_data = response.json()

        # Check for errors in response
        if response.status_code != 200:
            error_msg = response_data.get('errorMessage', 'Unknown error')
            error_code = response_data.get('errorCode', 'Unknown')
            logger.error(f"STK Push failed: {error_code} - {error_msg}")
            raise PaymentError(f"Payment failed: {error_msg} (Code: {error_code})")

        # Check response code
        response_code = response_data.get('ResponseCode', '')
        if response_code != '0':
            error_msg = response_data.get('ResponseDescription', 'Unknown error')
            logger.error(f"STK Push rejected: {response_code} - {error_msg}")
            raise PaymentError(f"Payment rejected: {error_msg}")

        checkout_request_id = response_data.get('CheckoutRequestID')
        merchant_request_id = response_data.get('MerchantRequestID')

        logger.info(
            f"STK Push initiated successfully - "
            f"CheckoutRequestID: {checkout_request_id}, "
            f"MerchantRequestID: {merchant_request_id}"
        )

        return response_data

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error during STK Push: {e}")
        logger.error(f"Response content: {e.response.text if e.response else 'No response'}")
        raise PaymentError(f"HTTP error: {e}") from e

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error during STK Push: {e}")
        raise PaymentError(f"Connection error: {e}") from e

    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout during STK Push: {e}")
        raise PaymentError(f"Request timeout: {e}") from e

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error during STK Push: {e}")
        raise PaymentError(f"Request failed: {e}") from e

    except PaymentError:
        raise

    except Exception as e:
        logger.error(f"Unexpected error during STK Push: {e}")
        raise PaymentError(f"Unexpected error: {e}") from e


def query_transaction_status(checkout_request_id: str) -> Dict[str, Any]:
    """
    Query the status of an M-Pesa STK Push transaction.

    Checks the current status of a previously initiated STK Push transaction
    using its CheckoutRequestID.

    Args:
        checkout_request_id: The CheckoutRequestID returned from initiate_stk_push().

    Returns:
        Dict[str, Any]: API response containing:
            - ResponseCode: Response code (0 for success)
            - ResponseDescription: Response message
            - MerchantRequestID: Original merchant request ID
            - CheckoutRequestID: Original checkout request ID
            - ResultCode: Transaction result code
            - ResultDesc: Transaction result description

    Raises:
        QueryError: If status query fails.
        ValueError: If checkout_request_id is invalid.

    Example:
        >>> status = query_transaction_status("ws_CO_12345678901234567890")
        >>> print(f"Result: {status['ResultDesc']}")
    """
    if not checkout_request_id:
        raise ValueError("CheckoutRequestID is required")

    if config is None:
        raise QueryError("Configuration not loaded. Please check your .env file.")

    query_url = config.mpesa_query_url
    shortcode = config.mpesa_shortcode

    # Generate password and timestamp
    password, timestamp = generate_password()

    # Get access token
    try:
        access_token = get_access_token()
    except AuthenticationError as e:
        logger.error(f"Failed to get access token: {e}")
        raise QueryError(f"Authentication failed: {e}") from e

    # Prepare request headers
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    # Prepare request payload
    payload = {
        'BusinessShortCode': shortcode,
        'Password': password,
        'Timestamp': timestamp,
        'CheckoutRequestID': checkout_request_id
    }

    logger.info(f"Querying transaction status for CheckoutRequestID: {checkout_request_id}")
    logger.debug(f"Query payload: {payload}")

    try:
        session = _get_session_with_retry()
        response = session.post(
            query_url,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )

        response_data = response.json()

        # Check for errors in response
        if response.status_code != 200:
            error_msg = response_data.get('errorMessage', 'Unknown error')
            error_code = response_data.get('errorCode', 'Unknown')
            logger.error(f"Transaction query failed: {error_code} - {error_msg}")
            raise QueryError(f"Query failed: {error_msg} (Code: {error_code})")

        result_code = response_data.get('ResultCode', '')
        result_desc = response_data.get('ResultDesc', 'Unknown')

        logger.info(
            f"Transaction status retrieved - "
            f"ResultCode: {result_code}, ResultDesc: {result_desc}"
        )

        return response_data

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error during transaction query: {e}")
        logger.error(f"Response content: {e.response.text if e.response else 'No response'}")
        raise QueryError(f"HTTP error: {e}") from e

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error during transaction query: {e}")
        raise QueryError(f"Connection error: {e}") from e

    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout during transaction query: {e}")
        raise QueryError(f"Request timeout: {e}") from e

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error during transaction query: {e}")
        raise QueryError(f"Request failed: {e}") from e

    except QueryError:
        raise

    except Exception as e:
        logger.error(f"Unexpected error during transaction query: {e}")
        raise QueryError(f"Unexpected error: {e}") from e


def get_environment_info() -> Dict[str, str]:
    """
    Get information about the current M-Pesa environment configuration.

    Returns:
        Dict[str, str]: Dictionary containing:
            - environment: Current environment (sandbox/production)
            - business_short_code: Configured business shortcode
            - auth_url: Authentication endpoint URL
            - stk_push_url: STK Push endpoint URL
            - query_url: Transaction query endpoint URL

    Example:
        >>> info = get_environment_info()
        >>> print(f"Environment: {info['environment']}")
        >>> print(f"Shortcode: {info['business_short_code']}")
    """
    if config is None:
        raise MpesaError("Configuration not loaded. Please check your .env file.")

    return {
        'environment': config.mpesa_environment,
        'business_short_code': config.mpesa_shortcode,
        'auth_url': config.mpesa_auth_url,
        'stk_push_url': config.mpesa_stk_push_url,
        'query_url': config.mpesa_query_url
    }


# Convenience function for testing
if __name__ == '__main__':
    """
    Test module functionality.

    This section demonstrates basic usage of the M-Pesa service module.
    """
    print("M-Pesa Service Module")
    print("=" * 50)

    if config is None:
        print("\n⚠ Warning: Configuration not loaded!")
        print("Please create a .env file with required M-Pesa credentials.")
        print("See .env.example for reference.")
        print("\n" + "=" * 50)
        exit(1)

    # Display environment info
    try:
        env_info = get_environment_info()
        print(f"\nEnvironment: {env_info['environment']}")
        print(f"Business Shortcode: {env_info['business_short_code']}")
    except MpesaError as e:
        print(f"✗ Error getting environment info: {e}")

    # Test timestamp generation
    timestamp = generate_timestamp()
    print(f"\nGenerated Timestamp: {timestamp}")

    # Test password generation
    try:
        password, ts = generate_password()
        print(f"Generated Password: {password[:20]}...")
        print(f"Password Timestamp: {ts}")
    except MpesaError as e:
        print(f"✗ Error generating password: {e}")

    # Test access token retrieval
    try:
        print("\nTesting access token retrieval...")
        token = get_access_token()
        print(f"Access Token: {token[:20]}...")
        print("✓ Successfully retrieved access token")
    except AuthenticationError as e:
        print(f"✗ Authentication failed: {e}")

    print("\n" + "=" * 50)
    print("Module loaded successfully!")
