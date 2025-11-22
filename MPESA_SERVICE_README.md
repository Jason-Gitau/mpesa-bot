# M-Pesa Service Module Documentation

## Overview

The `mpesa_service.py` module provides a comprehensive service layer for integrating with Safaricom's M-Pesa API. It supports both sandbox and production environments with automatic retry logic, proper error handling, and comprehensive logging.

## Features

- **Dynamic Password Generation**: Automatically generates Base64-encoded passwords
- **Dynamic Timestamp**: Creates timestamps in YYYYMMDDHHmmss format
- **STK Push Integration**: Initiates payment requests to customer phones
- **Transaction Status Query**: Check payment status using CheckoutRequestID
- **Environment Support**: Seamlessly switch between sandbox and production
- **Retry Logic**: Automatic retry for transient network errors
- **Error Handling**: Custom exceptions for different error types
- **Type Hints**: Full type annotation support
- **Comprehensive Logging**: Detailed logging for debugging and monitoring

## Installation

1. Install required dependencies:
```bash
pip install requests python-dotenv
```

2. Create a `.env` file (see `.env.example`):
```bash
cp .env.example .env
```

3. Configure your M-Pesa credentials in `.env`:
```env
# M-Pesa Configuration
MPESA_CONSUMER_KEY=your_consumer_key
MPESA_CONSUMER_SECRET=your_consumer_secret
MPESA_SHORTCODE=your_shortcode
MPESA_PASSKEY=your_passkey
CALLBACK_URL=https://yourdomain.com/callback

# Environment (sandbox or production)
ENVIRONMENT=sandbox
```

## Functions

### 1. `get_access_token()` → `str`

Authenticate with M-Pesa API and retrieve an access token.

**Returns:** Valid M-Pesa API access token

**Raises:** `AuthenticationError` if authentication fails

**Example:**
```python
from mpesa_service import get_access_token

try:
    token = get_access_token()
    print(f"Access Token: {token[:20]}...")
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
```

---

### 2. `generate_timestamp()` → `str`

Generate a timestamp in YYYYMMDDHHmmss format.

**Returns:** Timestamp string

**Example:**
```python
from mpesa_service import generate_timestamp

timestamp = generate_timestamp()
print(timestamp)  # e.g., '20231215143025'
```

---

### 3. `generate_password(timestamp: Optional[str] = None)` → `tuple[str, str]`

Generate the Base64-encoded password for M-Pesa requests.

**Parameters:**
- `timestamp` (optional): Custom timestamp. If not provided, generates a new one.

**Returns:** Tuple of (password, timestamp)

**Example:**
```python
from mpesa_service import generate_password

# Auto-generate timestamp
password, timestamp = generate_password()
print(f"Password: {password[:30]}...")
print(f"Timestamp: {timestamp}")

# Use custom timestamp
password, ts = generate_password("20231215143025")
```

---

### 4. `initiate_stk_push()` - Initiate Payment

Initiate an M-Pesa STK Push payment request.

**Parameters:**
- `phone` (str): Customer's phone number (format: 254XXXXXXXXX)
- `amount` (int/float): Amount to charge (minimum 1)
- `account_ref` (str): Account reference/invoice number (max 12 chars)
- `description` (str): Transaction description (max 13 chars)
- `callback_url` (str): URL for payment callbacks

**Returns:** Dict with payment response

**Raises:** `PaymentError`, `ValueError`

**Example:**
```python
from mpesa_service import initiate_stk_push, PaymentError

try:
    result = initiate_stk_push(
        phone="254712345678",
        amount=100,
        account_ref="INV001",
        description="Test Payment",
        callback_url="https://yourdomain.com/callback"
    )

    print(f"✓ Payment initiated!")
    print(f"CheckoutRequestID: {result['CheckoutRequestID']}")
    print(f"Customer Message: {result['CustomerMessage']}")

except PaymentError as e:
    print(f"✗ Payment failed: {e}")
except ValueError as e:
    print(f"✗ Invalid input: {e}")
```

**Response Structure:**
```json
{
    "MerchantRequestID": "12345-67890-1",
    "CheckoutRequestID": "ws_CO_12345678901234567890",
    "ResponseCode": "0",
    "ResponseDescription": "Success. Request accepted for processing",
    "CustomerMessage": "Success. Request accepted for processing"
}
```

---

### 5. `query_transaction_status(checkout_request_id: str)` → `Dict[str, Any]`

Query the status of an M-Pesa STK Push transaction.

**Parameters:**
- `checkout_request_id` (str): CheckoutRequestID from `initiate_stk_push()`

**Returns:** Dict with transaction status

**Raises:** `QueryError`, `ValueError`

**Example:**
```python
from mpesa_service import query_transaction_status, QueryError

checkout_id = "ws_CO_12345678901234567890"

try:
    status = query_transaction_status(checkout_id)

    result_code = status['ResultCode']
    result_desc = status['ResultDesc']

    if result_code == '0':
        print("✓ Payment successful!")
    elif result_code == '1032':
        print("✗ Payment cancelled by user")
    elif result_code == '1037':
        print("✗ Payment timeout (user didn't enter PIN)")
    else:
        print(f"✗ Payment failed: {result_desc}")

except QueryError as e:
    print(f"Query failed: {e}")
```

**Common Result Codes:**
- `0` - Success
- `1032` - Request cancelled by user
- `1037` - Timeout (user didn't enter PIN)
- `1` - Insufficient balance
- `2001` - Invalid parameters

---

### 6. `get_environment_info()` → `Dict[str, str]`

Get information about the current M-Pesa environment configuration.

**Returns:** Dict with environment information

**Example:**
```python
from mpesa_service import get_environment_info

info = get_environment_info()
print(f"Environment: {info['environment']}")
print(f"Shortcode: {info['business_short_code']}")
print(f"Auth URL: {info['auth_url']}")
```

---

## Error Handling

The module defines custom exceptions for different error types:

### `MpesaError`
Base exception for all M-Pesa errors.

### `AuthenticationError`
Raised when M-Pesa API authentication fails.

### `PaymentError`
Raised when payment initiation fails.

### `QueryError`
Raised when transaction status query fails.

**Example:**
```python
from mpesa_service import (
    initiate_stk_push,
    MpesaError,
    PaymentError,
    AuthenticationError
)

try:
    result = initiate_stk_push(...)
except PaymentError as e:
    print(f"Payment error: {e}")
except AuthenticationError as e:
    print(f"Auth error: {e}")
except MpesaError as e:
    print(f"General M-Pesa error: {e}")
```

---

## Complete Payment Flow Example

```python
from mpesa_service import (
    initiate_stk_push,
    query_transaction_status,
    PaymentError,
    QueryError
)
import time

# Step 1: Initiate payment
print("Initiating payment...")
try:
    payment = initiate_stk_push(
        phone="254712345678",
        amount=100,
        account_ref="ORDER123",
        description="Product A",
        callback_url="https://yourdomain.com/callback"
    )

    checkout_id = payment['CheckoutRequestID']
    print(f"✓ Payment request sent. CheckoutID: {checkout_id}")
    print("Waiting for customer to enter PIN...")

except PaymentError as e:
    print(f"✗ Payment initiation failed: {e}")
    exit(1)

# Step 2: Wait for user to enter PIN (30-60 seconds)
time.sleep(30)

# Step 3: Check payment status
print("\nChecking payment status...")
try:
    status = query_transaction_status(checkout_id)

    if status['ResultCode'] == '0':
        print("✓ Payment completed successfully!")
        # Process order, send confirmation, etc.
    else:
        print(f"✗ Payment failed: {status['ResultDesc']}")
        # Handle failed payment

except QueryError as e:
    print(f"✗ Status query failed: {e}")
```

---

## Retry Logic

The module implements automatic retry logic for transient network errors:

- **Max Retries:** 3 attempts
- **Backoff Factor:** 2 seconds
- **Retry Status Codes:** 408, 429, 500, 502, 503, 504
- **Retry Methods:** GET, POST

Network errors are automatically retried with exponential backoff.

---

## Logging

The module uses Python's logging module for comprehensive logging:

```python
import logging

# Configure logging level (if needed)
logging.basicConfig(level=logging.DEBUG)

# Now all M-Pesa operations will be logged
from mpesa_service import initiate_stk_push
result = initiate_stk_push(...)
```

**Log Levels:**
- `INFO`: Normal operations (token retrieval, payment initiation)
- `DEBUG`: Detailed information (payloads, timestamps)
- `ERROR`: Error conditions (authentication failures, network errors)

---

## Configuration

### Sandbox Configuration

For testing, use sandbox credentials:

```env
ENVIRONMENT=sandbox
MPESA_CONSUMER_KEY=your_sandbox_consumer_key
MPESA_CONSUMER_SECRET=your_sandbox_consumer_secret
MPESA_SHORTCODE=174379
MPESA_PASSKEY=bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919
```

### Production Configuration

For live transactions:

```env
ENVIRONMENT=production
MPESA_CONSUMER_KEY=your_production_consumer_key
MPESA_CONSUMER_SECRET=your_production_consumer_secret
MPESA_SHORTCODE=your_production_shortcode
MPESA_PASSKEY=your_production_passkey
```

---

## Testing

Test the module directly:

```bash
python3 mpesa_service.py
```

This will:
1. Display environment information
2. Generate timestamps and passwords
3. Attempt to retrieve an access token

---

## API Endpoints

### Sandbox URLs
- Auth: `https://sandbox.safaricom.co.ke/oauth/v1/generate`
- STK Push: `https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest`
- Query: `https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query`

### Production URLs
- Auth: `https://api.safaricom.co.ke/oauth/v1/generate`
- STK Push: `https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest`
- Query: `https://api.safaricom.co.ke/mpesa/stkpushquery/v1/query`

---

## Best Practices

1. **Always validate phone numbers** before calling `initiate_stk_push()`
2. **Store CheckoutRequestID** for status queries
3. **Implement callback handling** for real-time payment notifications
4. **Use try-except blocks** for all M-Pesa operations
5. **Log all transactions** for audit trail
6. **Test in sandbox** before going to production
7. **Handle all result codes** appropriately
8. **Set appropriate timeouts** for payment status checks

---

## Troubleshooting

### "Configuration not loaded" Error
**Solution:** Create a `.env` file with required credentials

### "Invalid phone number" Error
**Solution:** Ensure phone format is 254XXXXXXXXX (12 digits)

### "Authentication failed" Error
**Solution:** Check consumer key and secret in `.env`

### "Payment timeout" Error
**Solution:** Increase wait time before querying status (30-60 seconds)

---

## Support

For M-Pesa API documentation:
- [Safaricom Developer Portal](https://developer.safaricom.co.ke/)
- [M-Pesa API Documentation](https://developer.safaricom.co.ke/Documentation)

---

## File Location

- **Module:** `/home/user/mpesa-bot/mpesa_service.py`
- **Config:** `/home/user/mpesa-bot/config.py`
- **Example:** `/home/user/mpesa-bot/mpesa_service_example.py`
