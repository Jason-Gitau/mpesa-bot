"""
Example usage of config.py and utils.py modules.

This script demonstrates how to use the configuration management
and utility functions in your M-Pesa bot.
"""

from config import get_config, ConfigError
from utils import (
    setup_logger,
    validate_kenyan_phone,
    validate_amount,
    get_mpesa_timestamp,
    generate_mpesa_password,
    format_receipt,
    format_error_message,
    format_currency
)


def main():
    """Demonstrate usage of config and utils modules."""

    # 1. Setup Logger
    print("=" * 60)
    print("M-Pesa Bot - Configuration & Utilities Demo")
    print("=" * 60)

    logger = setup_logger(
        name='mpesa_bot_demo',
        log_level='INFO',
        log_file='logs/demo.log',
        colorful_console=True
    )

    logger.info("Starting M-Pesa Bot Demo")

    # 2. Load Configuration
    try:
        config = get_config()
        logger.info(f"Configuration loaded: {config}")
        print(f"\n✓ Configuration loaded successfully")
        print(f"  Environment: {config.mpesa_environment}")
        print(f"  Shortcode: {config.mpesa_shortcode}")
        print(f"  Amount limits: {format_currency(config.min_amount)} - {format_currency(config.max_amount)}")
        print(f"  Database configured: {config.has_database_config}")

    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        print(f"\n✗ Configuration error: {e}")
        print("\nPlease create a .env file based on .env.example")
        return

    # 3. Validate Phone Number
    print("\n" + "=" * 60)
    print("Phone Number Validation")
    print("=" * 60)

    test_phone = "0712345678"
    is_valid, formatted_phone, error = validate_kenyan_phone(test_phone)

    if is_valid:
        logger.info(f"Phone validated: {test_phone} -> {formatted_phone}")
        print(f"✓ {test_phone} -> {formatted_phone}")
    else:
        logger.error(f"Invalid phone: {test_phone} - {error}")
        print(f"✗ {test_phone}: {error}")

    # 4. Validate Amount
    print("\n" + "=" * 60)
    print("Amount Validation")
    print("=" * 60)

    test_amount = "1000"
    is_valid, amount, error = validate_amount(
        test_amount,
        min_amount=config.min_amount,
        max_amount=config.max_amount
    )

    if is_valid:
        logger.info(f"Amount validated: {test_amount} -> {amount}")
        print(f"✓ {test_amount} -> {format_currency(amount)}")
    else:
        logger.error(f"Invalid amount: {test_amount} - {error}")
        print(f"✗ {test_amount}: {error}")

    # 5. Generate M-Pesa Password
    print("\n" + "=" * 60)
    print("M-Pesa Password Generation")
    print("=" * 60)

    timestamp = get_mpesa_timestamp()
    password = generate_mpesa_password(
        config.mpesa_shortcode,
        config.mpesa_passkey,
        timestamp
    )

    logger.info(f"Generated M-Pesa password for timestamp: {timestamp}")
    print(f"Timestamp: {timestamp}")
    print(f"Password: {password[:30]}...")

    # 6. Format Receipt
    print("\n" + "=" * 60)
    print("Transaction Receipt")
    print("=" * 60)

    if is_valid and formatted_phone:
        receipt = format_receipt(
            transaction_id='TEST123456789',
            phone_number=formatted_phone,
            amount=amount if amount else 1000,
            timestamp=timestamp,
            status='Success',
            reference='ORDER001',
            description='Test Payment',
            merchant_name='Demo Store'
        )

        logger.info("Generated transaction receipt")
        print(receipt)

    # 7. Error Message Formatting
    print("\n" + "=" * 60)
    print("Error Message Formatting")
    print("=" * 60)

    error_codes = ['1', '1032', '404.001.03', 'unknown']
    for code in error_codes:
        friendly_msg = format_error_message(code, f"Error code {code}")
        print(f"Code {code}: {friendly_msg}")

    # 8. Display Configuration Summary
    print("\n" + "=" * 60)
    print("Configuration Summary")
    print("=" * 60)

    print(f"""
Environment Settings:
  - M-Pesa Environment: {config.mpesa_environment}
  - App Environment: {config.app_env}
  - Debug Mode: {config.is_debug}

M-Pesa Settings:
  - Shortcode: {config.mpesa_shortcode}
  - Transaction Type: {config.mpesa_transaction_type}
  - Auth URL: {config.mpesa_auth_url}
  - STK Push URL: {config.mpesa_stk_push_url}
  - Callback URL: {config.mpesa_callback_url}

Payment Limits:
  - Minimum: {format_currency(config.min_amount)}
  - Maximum: {format_currency(config.max_amount)}

Logging:
  - Level: {config.log_level}
  - Format: {config.log_format}
  - File: {config.log_file}

Database:
  - MySQL Configured: {config.has_database_config}
  - Supabase Configured: {config.has_supabase_config}
    """)

    logger.info("Demo completed successfully")
    print("=" * 60)
    print("Demo completed!")
    print("=" * 60)


if __name__ == '__main__':
    main()
