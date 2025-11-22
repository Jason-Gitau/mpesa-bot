"""
Example usage of the M-Pesa Service module.

This file demonstrates how to use the mpesa_service module for
integrating M-Pesa payments in your application.
"""

from mpesa_service import (
    initiate_stk_push,
    query_transaction_status,
    get_access_token,
    generate_password,
    generate_timestamp,
    get_environment_info,
    AuthenticationError,
    PaymentError,
    QueryError
)


def example_stk_push():
    """Example: Initiate an STK Push payment."""
    print("\n=== Example: Initiate STK Push Payment ===")

    try:
        result = initiate_stk_push(
            phone="254712345678",           # Customer's phone number
            amount=100,                      # Amount to charge
            account_ref="INV001",           # Your invoice/reference number
            description="Test Payment",     # Transaction description
            callback_url="https://yourdomain.com/callback"  # Your callback URL
        )

        print(f"✓ Payment initiated successfully!")
        print(f"  CheckoutRequestID: {result.get('CheckoutRequestID')}")
        print(f"  MerchantRequestID: {result.get('MerchantRequestID')}")
        print(f"  Customer Message: {result.get('CustomerMessage')}")

        # Save the CheckoutRequestID to query status later
        checkout_request_id = result.get('CheckoutRequestID')
        return checkout_request_id

    except PaymentError as e:
        print(f"✗ Payment failed: {e}")
        return None
    except ValueError as e:
        print(f"✗ Invalid input: {e}")
        return None


def example_query_status(checkout_request_id: str):
    """Example: Query transaction status."""
    print("\n=== Example: Query Transaction Status ===")

    try:
        result = query_transaction_status(checkout_request_id)

        print(f"✓ Status retrieved successfully!")
        print(f"  ResultCode: {result.get('ResultCode')}")
        print(f"  ResultDesc: {result.get('ResultDesc')}")

        # Common result codes:
        # 0 - Success
        # 1032 - Request cancelled by user
        # 1037 - Timeout (user didn't enter PIN)
        # 1 - Insufficient balance

    except QueryError as e:
        print(f"✗ Query failed: {e}")


def example_get_access_token():
    """Example: Get M-Pesa access token."""
    print("\n=== Example: Get Access Token ===")

    try:
        token = get_access_token()
        print(f"✓ Access token retrieved: {token[:20]}...")
    except AuthenticationError as e:
        print(f"✗ Authentication failed: {e}")


def example_generate_password():
    """Example: Generate M-Pesa password."""
    print("\n=== Example: Generate Password ===")

    # Generate with auto timestamp
    password, timestamp = generate_password()
    print(f"Password: {password[:30]}...")
    print(f"Timestamp: {timestamp}")

    # Generate with custom timestamp
    custom_timestamp = "20231215143025"
    password2, timestamp2 = generate_password(custom_timestamp)
    print(f"Custom Password: {password2[:30]}...")
    print(f"Custom Timestamp: {timestamp2}")


def example_environment_info():
    """Example: Get environment information."""
    print("\n=== Example: Environment Information ===")

    info = get_environment_info()
    print(f"Environment: {info['environment']}")
    print(f"Business Shortcode: {info['business_short_code']}")
    print(f"Auth URL: {info['auth_url']}")
    print(f"STK Push URL: {info['stk_push_url']}")


def example_full_payment_flow():
    """Example: Complete payment flow from initiation to status check."""
    print("\n=== Example: Complete Payment Flow ===")

    # Step 1: Initiate payment
    print("\n1. Initiating payment...")
    checkout_request_id = example_stk_push()

    if checkout_request_id:
        # Step 2: Wait for user to enter PIN (in real scenario)
        print("\n2. Waiting for customer to enter M-Pesa PIN...")
        print("   (In production, wait 30-60 seconds)")

        # Step 3: Query payment status
        print("\n3. Querying payment status...")
        example_query_status(checkout_request_id)
    else:
        print("Payment initiation failed. Cannot proceed with status check.")


if __name__ == '__main__':
    """Run all examples."""
    print("=" * 60)
    print("M-Pesa Service Module - Usage Examples")
    print("=" * 60)

    # Display environment info
    example_environment_info()

    # Generate timestamp
    print("\n=== Example: Generate Timestamp ===")
    timestamp = generate_timestamp()
    print(f"Timestamp: {timestamp}")

    # Generate password
    example_generate_password()

    # Try to get access token
    example_get_access_token()

    # Note: The following examples will only work if you have:
    # 1. Valid M-Pesa credentials in config.py
    # 2. A working callback URL
    # Uncomment to test:

    # example_full_payment_flow()

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)
