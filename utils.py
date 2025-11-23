"""
Utilities module for M-Pesa Bot.

Provides helper functions for logging, validation, formatting,
and M-Pesa-specific operations.
"""

import re
import base64
import logging
import sys
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from logging.handlers import RotatingFileHandler
from pathlib import Path


# ANSI color codes for console output
class Colors:
    """ANSI color codes for terminal output."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to console output."""

    COLORS = {
        'DEBUG': Colors.GRAY,
        'INFO': Colors.BLUE,
        'WARNING': Colors.YELLOW,
        'ERROR': Colors.RED,
        'CRITICAL': f"{Colors.BOLD}{Colors.RED}",
    }

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with colors.

        Args:
            record: Log record to format

        Returns:
            Formatted log message with color codes
        """
        # Get color for log level
        color = self.COLORS.get(record.levelname, Colors.RESET)

        # Add color to level name
        record.levelname = f"{color}{record.levelname}{Colors.RESET}"

        # Add color to logger name
        record.name = f"{Colors.CYAN}{record.name}{Colors.RESET}"

        # Format timestamp
        if self.usesTime():
            record.asctime = f"{Colors.GRAY}{self.formatTime(record, self.datefmt)}{Colors.RESET}"

        return super().format(record)


def setup_logger(
    name: str = 'mpesa_bot',
    log_level: str = 'INFO',
    log_file: Optional[str] = None,
    log_format: str = 'text',
    max_bytes: int = 10485760,  # 10MB
    backup_count: int = 5,
    colorful_console: bool = True
) -> logging.Logger:
    """
    Set up a logger with both console and file handlers.

    Args:
        name: Logger name
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        log_format: Format type ('text' or 'json')
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep
        colorful_console: Whether to use colored console output

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logger('my_app', 'DEBUG', 'app.log')
        >>> logger.info('Application started')
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers to avoid duplicates
    logger.handlers = []

    # Define log format
    if log_format == 'json':
        formatter_str = '{"time": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'
    else:
        formatter_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))

    if colorful_console and log_format != 'json':
        console_formatter = ColoredFormatter(formatter_str)
    else:
        console_formatter = logging.Formatter(formatter_str)

    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler with rotation (if log file is specified)
    if log_file:
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_formatter = logging.Formatter(formatter_str)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def validate_kenyan_phone(phone: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate Kenyan phone number format.

    Accepts formats:
    - 254XXXXXXXXX (preferred)
    - +254XXXXXXXXX
    - 07XXXXXXXX or 01XXXXXXXX
    - 7XXXXXXXX or 1XXXXXXXX

    Args:
        phone: Phone number to validate

    Returns:
        Tuple of (is_valid, formatted_number, error_message)

    Example:
        >>> is_valid, formatted, error = validate_kenyan_phone('0712345678')
        >>> print(formatted)
        254712345678
    """
    if not phone:
        return False, None, "Phone number is required"

    # Remove spaces and hyphens
    phone = re.sub(r'[\s\-]', '', phone)

    # Remove + prefix if present
    if phone.startswith('+'):
        phone = phone[1:]

    # Validate and format based on pattern
    if phone.startswith('254'):
        # Already in correct format: 254XXXXXXXXX
        if len(phone) == 12 and phone.isdigit():
            return True, phone, None
        else:
            return False, None, "Invalid format. Expected 254XXXXXXXXX (12 digits)"

    elif phone.startswith('0'):
        # Format: 07XXXXXXXX or 01XXXXXXXX
        if len(phone) == 10 and phone.isdigit():
            formatted = f"254{phone[1:]}"
            return True, formatted, None
        else:
            return False, None, "Invalid format. Expected 0XXXXXXXXX (10 digits)"

    elif len(phone) == 9 and phone.isdigit():
        # Format: 7XXXXXXXX or 1XXXXXXXX
        formatted = f"254{phone}"
        return True, formatted, None

    else:
        return False, None, (
            "Invalid phone number format. Use: 254XXXXXXXXX, "
            "+254XXXXXXXXX, 0XXXXXXXXX, or XXXXXXXXX"
        )


def validate_amount(
    amount: Any,
    min_amount: int = 1,
    max_amount: int = 500000
) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Validate payment amount.

    Args:
        amount: Amount to validate (can be str, int, or float)
        min_amount: Minimum allowed amount
        max_amount: Maximum allowed amount

    Returns:
        Tuple of (is_valid, amount_as_int, error_message)

    Example:
        >>> is_valid, amt, error = validate_amount('100', min_amount=10, max_amount=10000)
        >>> print(amt)
        100
    """
    # Convert to number
    try:
        if isinstance(amount, str):
            # Remove commas and whitespace
            amount = amount.replace(',', '').strip()

        amount_num = float(amount)

        # Check if it's a whole number
        if amount_num != int(amount_num):
            return False, None, "Amount must be a whole number"

        amount_int = int(amount_num)

    except (ValueError, TypeError):
        return False, None, f"Invalid amount format: '{amount}'"

    # Validate range
    if amount_int < min_amount:
        return False, None, f"Amount must be at least KES {min_amount:,}"

    if amount_int > max_amount:
        return False, None, f"Amount must not exceed KES {max_amount:,}"

    return True, amount_int, None


def get_mpesa_timestamp() -> str:
    """
    Generate M-Pesa timestamp in the required format.

    Returns:
        Timestamp string in format YYYYMMDDHHmmss

    Example:
        >>> timestamp = get_mpesa_timestamp()
        >>> print(timestamp)
        20231215143022
    """
    return datetime.now().strftime('%Y%m%d%H%M%S')


def generate_mpesa_password(
    shortcode: str,
    passkey: str,
    timestamp: Optional[str] = None
) -> str:
    """
    Generate M-Pesa password by Base64 encoding: shortcode + passkey + timestamp.

    Args:
        shortcode: Business shortcode
        passkey: M-Pesa passkey
        timestamp: Optional timestamp (uses current time if not provided)

    Returns:
        Base64-encoded password string

    Example:
        >>> password = generate_mpesa_password('174379', 'mypasskey', '20231215143022')
        >>> print(password)
        MTc0Mzc5bXlwYXNza2V5MjAyMzEyMTUxNDMwMjI=
    """
    if timestamp is None:
        timestamp = get_mpesa_timestamp()

    # Concatenate shortcode, passkey, and timestamp
    raw_password = f"{shortcode}{passkey}{timestamp}"

    # Base64 encode
    encoded = base64.b64encode(raw_password.encode('utf-8'))

    return encoded.decode('utf-8')


def format_receipt(
    transaction_id: str,
    phone_number: str,
    amount: int,
    timestamp: Optional[str] = None,
    status: str = 'Success',
    reference: Optional[str] = None,
    description: Optional[str] = None,
    merchant_name: str = 'M-Pesa Bot'
) -> str:
    """
    Format a pretty text receipt for a transaction.

    Args:
        transaction_id: Unique transaction ID
        phone_number: Customer phone number
        amount: Transaction amount
        timestamp: Transaction timestamp
        status: Transaction status
        reference: Account reference
        description: Transaction description
        merchant_name: Business/merchant name

    Returns:
        Formatted receipt as a string

    Example:
        >>> receipt = format_receipt('ABC123', '254712345678', 1000)
        >>> print(receipt)
    """
    if timestamp is None:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    elif len(timestamp) == 14:  # M-Pesa timestamp format
        # Convert YYYYMMDDHHmmss to readable format
        dt = datetime.strptime(timestamp, '%Y%m%d%H%M%S')
        timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')

    # Status emoji
    status_emoji = {
        'Success': '✓',
        'Completed': '✓',
        'Failed': '✗',
        'Pending': '⏳',
        'Cancelled': '✗'
    }.get(status, '•')

    receipt = f"""
╔══════════════════════════════════════╗
║         TRANSACTION RECEIPT          ║
╠══════════════════════════════════════╣
║                                      ║
║  {merchant_name:^36}  ║
║                                      ║
╟──────────────────────────────────────╢
║                                      ║
║  Transaction ID: {transaction_id[:20]:<20} ║
║  Status: {status_emoji} {status:<28} ║
║  Date: {timestamp:<29} ║
║                                      ║
╟──────────────────────────────────────╢
║                                      ║
║  Phone Number: {phone_number:<23} ║
║  Amount: KES {amount:>24,} ║
"""

    if reference:
        receipt += f"║  Reference: {reference[:27]:<27} ║\n"

    if description:
        receipt += f"║  Description: {description[:25]:<25} ║\n"

    receipt += """║                                      ║
╚══════════════════════════════════════╝
"""

    return receipt


def format_error_message(
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    user_friendly: bool = True
) -> str:
    """
    Format error messages to be user-friendly.

    Args:
        error_code: M-Pesa error code
        error_message: Raw error message
        user_friendly: Whether to return user-friendly message

    Returns:
        Formatted error message

    Example:
        >>> msg = format_error_message('500.001.1001', 'Invalid phone number')
        >>> print(msg)
    """
    # Common M-Pesa error codes and user-friendly messages
    error_map = {
        '1': 'Insufficient balance. Please top up and try again.',
        '17': 'Request cancelled by user.',
        '26': 'Transaction failed. Please try again.',
        '1032': 'Transaction cancelled by user.',
        '1037': 'The transaction timed out. Please try again.',
        '2001': 'Invalid authentication. Please contact support.',
        '404.001.03': 'Invalid phone number. Please check and try again.',
        '500.001.1001': 'Invalid phone number format.',
        '500.001.1006': 'Invalid amount. Please enter a valid amount.',
    }

    if not user_friendly:
        return error_message or 'An unknown error occurred'

    # Try to find user-friendly message
    if error_code and error_code in error_map:
        return f"{error_map[error_code]}"

    # Check for common patterns in error message
    if error_message:
        error_lower = error_message.lower()

        if 'timeout' in error_lower or 'timed out' in error_lower:
            return 'The request timed out. Please try again.'

        if 'insufficient' in error_lower or 'balance' in error_lower:
            return 'Insufficient balance. Please top up your M-Pesa account.'

        if 'invalid' in error_lower and 'phone' in error_lower:
            return 'Invalid phone number. Please use format: 254XXXXXXXXX'

        if 'invalid' in error_lower and 'amount' in error_lower:
            return 'Invalid amount. Please enter a valid amount.'

        if 'cancel' in error_lower:
            return 'Transaction was cancelled.'

        if 'authentication' in error_lower or 'unauthorized' in error_lower:
            return 'Authentication failed. Please contact support.'

        if 'duplicate' in error_lower:
            return 'Duplicate transaction detected. Please wait a moment before retrying.'

    # Default message
    return (
        'Transaction failed. Please try again or contact support if the problem persists.'
    )


def format_currency(amount: int, currency: str = 'KES') -> str:
    """
    Format amount as currency string.

    Args:
        amount: Amount to format
        currency: Currency code (default: KES)

    Returns:
        Formatted currency string

    Example:
        >>> formatted = format_currency(1234567)
        >>> print(formatted)
        KES 1,234,567
    """
    return f"{currency} {amount:,}"


def sanitize_input(text: str, max_length: int = 200) -> str:
    """
    Sanitize user input to prevent injection attacks.

    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized text

    Example:
        >>> safe_text = sanitize_input('<script>alert("xss")</script>')
        >>> print(safe_text)
    """
    if not text:
        return ''

    # Truncate to max length
    text = text[:max_length]

    # Remove potentially dangerous characters
    text = re.sub(r'[<>"\';`]', '', text)

    # Remove control characters
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')

    return text.strip()


def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """
    Mask sensitive data for logging (e.g., phone numbers, tokens).

    Args:
        data: Sensitive data to mask
        visible_chars: Number of characters to keep visible at the end

    Returns:
        Masked string

    Example:
        >>> masked = mask_sensitive_data('254712345678', 4)
        >>> print(masked)
        ********5678
    """
    if not data or len(data) <= visible_chars:
        return '*' * len(data) if data else ''

    masked_length = len(data) - visible_chars
    return '*' * masked_length + data[-visible_chars:]


def parse_mpesa_callback(callback_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse M-Pesa STK Push callback data.

    Args:
        callback_data: Raw callback data from M-Pesa

    Returns:
        Parsed transaction data

    Example:
        >>> data = parse_mpesa_callback(callback_response)
        >>> print(data['transaction_id'])
    """
    result = {
        'success': False,
        'transaction_id': None,
        'amount': None,
        'phone': None,
        'receipt': None,
        'timestamp': None,
        'result_code': None,
        'result_desc': None,
    }

    try:
        # Navigate the callback structure
        body = callback_data.get('Body', {})
        stk_callback = body.get('stkCallback', {})

        result['result_code'] = stk_callback.get('ResultCode')
        result['result_desc'] = stk_callback.get('ResultDesc')
        result['transaction_id'] = stk_callback.get('CheckoutRequestID')

        # Check if successful
        if result['result_code'] == 0:
            result['success'] = True

            # Parse callback metadata
            metadata = stk_callback.get('CallbackMetadata', {})
            items = metadata.get('Item', [])

            for item in items:
                name = item.get('Name')
                value = item.get('Value')

                if name == 'Amount':
                    result['amount'] = int(value)
                elif name == 'MpesaReceiptNumber':
                    result['receipt'] = value
                elif name == 'PhoneNumber':
                    result['phone'] = str(value)
                elif name == 'TransactionDate':
                    result['timestamp'] = str(value)

    except Exception as e:
        result['error'] = str(e)

    return result


if __name__ == '__main__':
    # Test utility functions
    print("Testing M-Pesa Bot Utilities\n")

    # Test phone validation
    print("1. Phone Number Validation:")
    test_phones = ['0712345678', '254712345678', '+254712345678', '712345678', 'invalid']
    for phone in test_phones:
        valid, formatted, error = validate_kenyan_phone(phone)
        if valid:
            print(f"  ✓ {phone} -> {formatted}")
        else:
            print(f"  ✗ {phone} -> {error}")

    # Test amount validation
    print("\n2. Amount Validation:")
    test_amounts = ['100', 1000, '5000.00', 'invalid', '-100', '1000000']
    for amount in test_amounts:
        valid, amt, error = validate_amount(amount, min_amount=10, max_amount=500000)
        if valid:
            print(f"  ✓ {amount} -> KES {amt:,}")
        else:
            print(f"  ✗ {amount} -> {error}")

    # Test timestamp
    print(f"\n3. M-Pesa Timestamp:")
    timestamp = get_mpesa_timestamp()
    print(f"  Current timestamp: {timestamp}")

    # Test password generation
    print(f"\n4. M-Pesa Password:")
    password = generate_mpesa_password('174379', 'testpasskey', timestamp)
    print(f"  Generated password: {password[:20]}...")

    # Test receipt formatting
    print(f"\n5. Receipt Formatting:")
    receipt = format_receipt(
        'ABC123XYZ',
        '254712345678',
        1500,
        status='Success',
        reference='Order123'
    )
    print(receipt)

    # Test error formatting
    print(f"\n6. Error Message Formatting:")
    print(f"  User-friendly: {format_error_message('1032', 'User cancelled')}")
    print(f"  Technical: {format_error_message('1032', 'User cancelled', user_friendly=False)}")

    # Test logger
    print(f"\n7. Logger Setup:")
    logger = setup_logger('test_logger', 'INFO', colorful_console=True)
    logger.debug('This is a debug message')
    logger.info('This is an info message')
    logger.warning('This is a warning message')
    logger.error('This is an error message')
