# M-Pesa Bot - Config & Utils Usage Guide

## Overview

This guide shows how to use the `config.py` and `utils.py` modules in your M-Pesa bot project.

## Setup

### 1. Install Dependencies

```bash
pip install python-dotenv
```

All required dependencies are listed in `requirements.txt`.

### 2. Create Environment File

Copy `.env.example` to `.env` and fill in your actual values:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:
- Telegram bot token
- M-Pesa API credentials (consumer key, secret, shortcode, passkey)
- Database credentials (optional)
- Other settings

## Using config.py

### Basic Usage

```python
from config import get_config, ConfigError

try:
    # Load configuration
    config = get_config()

    # Access configuration values
    print(config.mpesa_shortcode)
    print(config.telegram_bot_token)
    print(config.mpesa_environment)  # 'sandbox' or 'production'

except ConfigError as e:
    print(f"Configuration error: {e}")
```

### Available Configuration Properties

```python
# Telegram
config.telegram_bot_token
config.seller_chat_id
config.admin_chat_id

# M-Pesa
config.mpesa_environment         # 'sandbox' or 'production'
config.mpesa_consumer_key
config.mpesa_consumer_secret
config.mpesa_shortcode
config.mpesa_passkey
config.mpesa_callback_url
config.mpesa_auth_url           # Auto-set based on environment
config.mpesa_stk_push_url       # Auto-set based on environment

# Payment Limits
config.min_amount
config.max_amount

# Database
config.db_host
config.db_port
config.db_user
config.db_password
config.db_name

# Logging
config.log_level
config.log_file
config.log_format

# Helper Properties
config.is_production            # True if in production
config.is_sandbox               # True if in sandbox
config.has_database_config      # True if DB is configured
config.has_supabase_config      # True if Supabase is configured
```

### Reload Configuration

```python
# Force reload configuration (useful after env changes)
config = get_config(reload=True)

# Load from specific file
config = get_config(env_file='/path/to/.env')
```

## Using utils.py

### 1. Logger Setup

```python
from utils import setup_logger

# Basic logger
logger = setup_logger('my_app')
logger.info('Application started')

# Advanced logger with file output
logger = setup_logger(
    name='mpesa_bot',
    log_level='DEBUG',
    log_file='logs/app.log',
    log_format='json',          # 'text' or 'json'
    colorful_console=True       # Colored console output
)

logger.debug('Debug message')
logger.info('Info message')
logger.warning('Warning message')
logger.error('Error message')
logger.critical('Critical message')
```

### 2. Phone Number Validation

```python
from utils import validate_kenyan_phone

# Validate and format phone number
is_valid, formatted_phone, error = validate_kenyan_phone('0712345678')

if is_valid:
    print(f"Phone: {formatted_phone}")  # Output: 254712345678
else:
    print(f"Error: {error}")

# Accepts multiple formats:
# - 0712345678
# - 254712345678
# - +254712345678
# - 712345678
```

### 3. Amount Validation

```python
from utils import validate_amount

# Validate payment amount
is_valid, amount, error = validate_amount(
    '1000',
    min_amount=10,
    max_amount=500000
)

if is_valid:
    print(f"Amount: KES {amount:,}")
else:
    print(f"Error: {error}")
```

### 4. M-Pesa Password Generation

```python
from utils import get_mpesa_timestamp, generate_mpesa_password
from config import get_config

config = get_config()

# Generate timestamp
timestamp = get_mpesa_timestamp()  # Format: YYYYMMDDHHmmss

# Generate M-Pesa password
password = generate_mpesa_password(
    shortcode=config.mpesa_shortcode,
    passkey=config.mpesa_passkey,
    timestamp=timestamp
)

print(f"Timestamp: {timestamp}")
print(f"Password: {password}")
```

### 5. Receipt Formatting

```python
from utils import format_receipt

receipt = format_receipt(
    transaction_id='ABC123XYZ456',
    phone_number='254712345678',
    amount=1500,
    status='Success',              # Success, Failed, Pending, etc.
    reference='ORDER001',
    description='Payment for goods',
    merchant_name='My Store'
)

print(receipt)
```

Output:
```
╔══════════════════════════════════════╗
║         TRANSACTION RECEIPT          ║
╠══════════════════════════════════════╣
║                                      ║
║               My Store               ║
║                                      ║
╟──────────────────────────────────────╢
...
```

### 6. Error Message Formatting

```python
from utils import format_error_message

# User-friendly error messages
error_msg = format_error_message(
    error_code='1032',
    error_message='Transaction cancelled by user',
    user_friendly=True
)

print(error_msg)  # Output: "Transaction was cancelled by user."

# Technical error messages
error_msg = format_error_message(
    error_code='1032',
    error_message='Transaction cancelled by user',
    user_friendly=False
)

print(error_msg)  # Output: "Transaction cancelled by user"
```

### 7. Parse M-Pesa Callback

```python
from utils import parse_mpesa_callback

# Parse M-Pesa STK Push callback
callback_data = {
    'Body': {
        'stkCallback': {
            'ResultCode': 0,
            'ResultDesc': 'Success',
            'CheckoutRequestID': 'ws_CO_123456',
            'CallbackMetadata': {
                'Item': [
                    {'Name': 'Amount', 'Value': 1000},
                    {'Name': 'MpesaReceiptNumber', 'Value': 'ABC123'},
                    {'Name': 'PhoneNumber', 'Value': 254712345678},
                    {'Name': 'TransactionDate', 'Value': 20231215143022}
                ]
            }
        }
    }
}

result = parse_mpesa_callback(callback_data)

if result['success']:
    print(f"Transaction ID: {result['transaction_id']}")
    print(f"Amount: {result['amount']}")
    print(f"Phone: {result['phone']}")
    print(f"Receipt: {result['receipt']}")
```

### 8. Other Utility Functions

```python
from utils import format_currency, sanitize_input, mask_sensitive_data

# Format currency
formatted = format_currency(1234567)  # Output: KES 1,234,567

# Sanitize user input
safe_text = sanitize_input('<script>alert("xss")</script>')

# Mask sensitive data for logging
masked_phone = mask_sensitive_data('254712345678', visible_chars=4)
print(masked_phone)  # Output: ********5678
```

## Complete Example

```python
from config import get_config, ConfigError
from utils import (
    setup_logger,
    validate_kenyan_phone,
    validate_amount,
    get_mpesa_timestamp,
    generate_mpesa_password,
    format_receipt,
    format_error_message
)

def process_payment(phone: str, amount: str):
    """Process an M-Pesa payment."""

    # Setup logger
    logger = setup_logger('payment', log_level='INFO')

    try:
        # Load configuration
        config = get_config()
        logger.info(f"Processing payment in {config.mpesa_environment} mode")

        # Validate phone number
        is_valid, formatted_phone, error = validate_kenyan_phone(phone)
        if not is_valid:
            logger.error(f"Invalid phone: {error}")
            return {'success': False, 'message': error}

        # Validate amount
        is_valid, amount_int, error = validate_amount(
            amount,
            min_amount=config.min_amount,
            max_amount=config.max_amount
        )
        if not is_valid:
            logger.error(f"Invalid amount: {error}")
            return {'success': False, 'message': error}

        # Generate M-Pesa password
        timestamp = get_mpesa_timestamp()
        password = generate_mpesa_password(
            config.mpesa_shortcode,
            config.mpesa_passkey,
            timestamp
        )

        # Build STK Push payload
        payload = {
            'BusinessShortCode': config.mpesa_shortcode,
            'Password': password,
            'Timestamp': timestamp,
            'TransactionType': config.mpesa_transaction_type,
            'Amount': amount_int,
            'PartyA': formatted_phone,
            'PartyB': config.mpesa_shortcode,
            'PhoneNumber': formatted_phone,
            'CallBackURL': config.mpesa_callback_url,
            'AccountReference': config.mpesa_account_reference,
            'TransactionDesc': config.mpesa_transaction_desc
        }

        logger.info(f"Payment initiated: {formatted_phone}, KES {amount_int}")

        # Here you would make the actual API call to M-Pesa
        # response = requests.post(config.mpesa_stk_push_url, json=payload, headers=headers)

        # Format receipt
        receipt = format_receipt(
            transaction_id='TEST123',
            phone_number=formatted_phone,
            amount=amount_int,
            status='Success'
        )

        return {
            'success': True,
            'receipt': receipt,
            'payload': payload
        }

    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        return {
            'success': False,
            'message': format_error_message(None, str(e))
        }
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {
            'success': False,
            'message': format_error_message(None, str(e))
        }

# Usage
result = process_payment('0712345678', '1000')
if result['success']:
    print(result['receipt'])
else:
    print(f"Error: {result['message']}")
```

## Testing

Run the example script to test both modules:

```bash
python example_usage.py
```

Or test individual modules:

```bash
# Test config module
python config.py

# Test utils module
python utils.py
```

## Error Handling

Always handle `ConfigError` when loading configuration:

```python
from config import get_config, ConfigError

try:
    config = get_config()
except ConfigError as e:
    print(f"Configuration error: {e}")
    print("Please check your .env file")
    exit(1)
```

## Best Practices

1. **Load config once** at application startup using the singleton pattern
2. **Use logger consistently** throughout your application
3. **Validate all user inputs** before processing
4. **Mask sensitive data** in logs using `mask_sensitive_data()`
5. **Use user-friendly error messages** for better UX
6. **Keep .env file secure** - never commit it to version control

## Environment Variables

All environment variables are documented in `.env.example`. Required variables:

- `TELEGRAM_BOT_TOKEN`
- `SELLER_CHAT_ID`
- `MPESA_CONSUMER_KEY`
- `MPESA_CONSUMER_SECRET`
- `MPESA_SHORTCODE`
- `MPESA_PASSKEY`

Optional variables have sensible defaults.
