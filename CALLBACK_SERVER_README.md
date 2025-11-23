# M-Pesa Callback Server Documentation

## Overview

The **callback_server.py** is a production-ready FastAPI server designed to handle M-Pesa STK Push payment callbacks. It processes payment notifications, updates your database, and sends real-time notifications via Telegram.

## Features

✅ **Complete Callback Handling**
- Parses M-Pesa callback JSON payloads
- Extracts all payment details (Amount, Receipt, Phone, etc.)
- Handles both successful and failed transactions

✅ **Database Integration**
- Automatic transaction updates
- Transaction history tracking
- Efficient indexing for fast queries

✅ **Telegram Notifications**
- Admin notifications for all payments
- User receipts for successful payments
- Rich formatted messages with payment details

✅ **Production Ready**
- Comprehensive error handling
- Request validation with Pydantic
- Detailed logging to file and console
- Health check endpoint
- API documentation (auto-generated)

## Architecture

```
┌─────────────┐
│   M-Pesa    │
│   Server    │
└──────┬──────┘
       │ POST /mpesa/callback
       ▼
┌─────────────────────────────┐
│  FastAPI Callback Server    │
│  ┌─────────────────────┐   │
│  │ Validate Request    │   │
│  └──────┬──────────────┘   │
│         ▼                   │
│  ┌─────────────────────┐   │
│  │ Parse Transaction   │   │
│  └──────┬──────────────┘   │
│         ▼                   │
│  ┌─────────────────────┐   │
│  │ Update Database     │   │
│  └──────┬──────────────┘   │
│         ▼                   │
│  ┌─────────────────────┐   │
│  │ Send Notifications  │   │
│  └─────────────────────┘   │
└─────────────────────────────┘
       │
       ├──► MySQL Database
       │
       └──► Telegram Bot
```

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Database

```bash
# Import the database schema
mysql -u root -p < database_schema.sql
```

Or create the database manually:

```sql
CREATE DATABASE mpesa_bot;
USE mpesa_bot;
-- Then run the SQL from database_schema.sql
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and update:

```bash
cp .env.example .env
nano .env
```

**Required Variables:**
```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
ADMIN_CHAT_ID=your_admin_chat_id

# Database
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=mpesa_bot
```

## Running the Server

### Development Mode

```bash
# Run with auto-reload
python callback_server.py
```

Or using uvicorn directly:

```bash
uvicorn callback_server:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
# Using gunicorn with uvicorn workers
gunicorn callback_server:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --log-level info
```

## API Endpoints

### 1. Welcome Endpoint
```
GET /
```

Returns API information and available endpoints.

**Response:**
```json
{
  "service": "M-Pesa Callback Server",
  "version": "1.0.0",
  "status": "running",
  "endpoints": {
    "callback": "/mpesa/callback",
    "health": "/health",
    "docs": "/docs"
  }
}
```

### 2. Health Check
```
GET /health
```

Check server and dependency health status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00",
  "service": "mpesa-callback-server",
  "database": "connected",
  "telegram": "connected as @your_bot"
}
```

### 3. M-Pesa Callback
```
POST /mpesa/callback
```

Handles M-Pesa payment callbacks.

**Request Body:** (Sent by M-Pesa)
```json
{
  "Body": {
    "stkCallback": {
      "MerchantRequestID": "29115-34620561-1",
      "CheckoutRequestID": "ws_CO_191220191020363925",
      "ResultCode": 0,
      "ResultDesc": "The service request is processed successfully.",
      "CallbackMetadata": {
        "Item": [
          {"Name": "Amount", "Value": 1000},
          {"Name": "MpesaReceiptNumber", "Value": "NLJ7RT61SV"},
          {"Name": "TransactionDate", "Value": 20191219102115},
          {"Name": "PhoneNumber", "Value": 254708374149}
        ]
      }
    }
  }
}
```

**Response:**
```json
{
  "ResultCode": 0,
  "ResultDesc": "Callback received successfully",
  "CheckoutRequestID": "ws_CO_191220191020363925"
}
```

## Callback Data Structure

### Successful Payment
When a payment succeeds (ResultCode = 0), the callback includes:

| Field | Type | Description |
|-------|------|-------------|
| CheckoutRequestID | string | Unique request identifier |
| MerchantRequestID | string | Merchant request ID |
| ResultCode | int | 0 for success |
| ResultDesc | string | Success message |
| Amount | float | Payment amount |
| MpesaReceiptNumber | string | M-Pesa receipt number |
| PhoneNumber | string | Customer phone number |
| TransactionDate | datetime | Payment timestamp |

### Failed Payment
When a payment fails (ResultCode ≠ 0):

| Field | Type | Description |
|-------|------|-------------|
| CheckoutRequestID | string | Unique request identifier |
| ResultCode | int | Error code |
| ResultDesc | string | Error description |
| CallbackMetadata | null | No metadata for failed payments |

## Notification Examples

### Admin Notification (Success)
```
✅ Payment Successful

💰 Amount: KES 1,000.00
📱 Phone: 254708374149
🧾 Receipt: NLJ7RT61SV
🆔 Request ID: ws_CO_191220191020363925
📅 Date: 2024-01-15 10:30:15
```

### Admin Notification (Failure)
```
❌ Payment Failed

📱 Phone: 254708374149
🆔 Request ID: ws_CO_191220191020363925
❗ Reason: User cancelled the transaction
📅 Date: 2024-01-15 10:30:15
```

### User Receipt
```
🎉 Payment Receipt

Thank you for your payment!

💰 Amount: KES 1,000.00
🧾 M-Pesa Receipt: NLJ7RT61SV
📅 Date: 2024-01-15 10:30:15

Transaction ID: ws_CO_191220191020363925
```

## Database Schema

### Transactions Table
```sql
CREATE TABLE transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    checkout_request_id VARCHAR(100) UNIQUE NOT NULL,
    merchant_request_id VARCHAR(100) NOT NULL,
    result_code INT,
    result_desc VARCHAR(255),
    amount DECIMAL(10, 2),
    mpesa_receipt_number VARCHAR(50),
    phone_number VARCHAR(15),
    transaction_date DATETIME,
    status ENUM('Pending', 'Success', 'Failed', 'Cancelled'),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### Users Table
```sql
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    telegram_chat_id BIGINT UNIQUE NOT NULL,
    phone_number VARCHAR(15),
    telegram_username VARCHAR(100),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Logging

Logs are written to both console and `mpesa_callbacks.log`.

**Log Format:**
```
2024-01-15 10:30:15,123 - __main__ - INFO - Received M-Pesa callback: {...}
2024-01-15 10:30:15,456 - __main__ - INFO - Processing transaction ws_CO_191220191020363925 - Result: 0 (Success)
2024-01-15 10:30:15,789 - __main__ - INFO - Database connection established
2024-01-15 10:30:16,012 - __main__ - INFO - Transaction ws_CO_191220191020363925 updated successfully
2024-01-15 10:30:16,345 - __main__ - INFO - Admin notification sent
```

## Integration with M-Pesa

### 1. Update Callback URL in STK Push

In your STK Push request, set the callback URL:

```python
payload = {
    "BusinessShortCode": "174379",
    "Password": "...",
    "Timestamp": "...",
    "TransactionType": "CustomerPayBillOnline",
    "Amount": amount,
    "PartyA": phone_number,
    "PartyB": "174379",
    "PhoneNumber": phone_number,
    "CallBackURL": "https://your-domain.com/mpesa/callback",  # Your callback URL
    "AccountReference": "Account",
    "TransactionDesc": "Payment"
}
```

### 2. Expose Server to Internet

For development/testing, use ngrok:

```bash
# Install ngrok
npm install -g ngrok

# Start your server
python callback_server.py

# In another terminal, expose it
ngrok http 8000
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`) and use `https://abc123.ngrok.io/mpesa/callback` as your CallBackURL.

### 3. Production Deployment

For production, deploy behind a reverse proxy:

**Nginx Configuration:**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /mpesa/callback {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## Testing

### Manual Testing

```bash
# Test with curl
curl -X POST http://localhost:8000/mpesa/callback \
  -H "Content-Type: application/json" \
  -d '{
    "Body": {
      "stkCallback": {
        "MerchantRequestID": "test-123",
        "CheckoutRequestID": "test-checkout-456",
        "ResultCode": 0,
        "ResultDesc": "Success",
        "CallbackMetadata": {
          "Item": [
            {"Name": "Amount", "Value": 1000},
            {"Name": "MpesaReceiptNumber", "Value": "TEST123"},
            {"Name": "TransactionDate", "Value": 20240115103000},
            {"Name": "PhoneNumber", "Value": 254708374149}
          ]
        }
      }
    }
  }'
```

### Using the Test Script

```bash
python test_callback.py
```

## API Documentation

FastAPI auto-generates interactive API documentation:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## Troubleshooting

### Issue: Database Connection Failed

**Solution:**
- Verify MySQL is running: `systemctl status mysql`
- Check credentials in `.env`
- Ensure database exists: `mysql -u root -p -e "SHOW DATABASES;"`

### Issue: Telegram Notifications Not Sent

**Solution:**
- Verify `ADMIN_CHAT_ID` is set correctly
- Check bot token is valid
- Ensure bot has permission to send messages

### Issue: Callback Not Received

**Solution:**
- Verify callback URL is publicly accessible
- Check M-Pesa dashboard for callback errors
- Review `mpesa_callbacks.log` for incoming requests

## Security Considerations

1. **HTTPS Required:** M-Pesa only sends callbacks to HTTPS endpoints (except sandbox)
2. **Validate Requests:** The server validates all incoming requests
3. **Environment Variables:** Never commit `.env` file
4. **Database Security:** Use strong passwords and limit database access
5. **Rate Limiting:** Consider adding rate limiting for production

## Performance Tips

1. **Use Connection Pooling:** For high traffic, implement connection pooling
2. **Async Operations:** All database and API calls are async
3. **Logging:** Adjust log level in production (`INFO` or `WARNING`)
4. **Monitoring:** Set up monitoring for the `/health` endpoint

## Support

For issues or questions:
- Check logs: `tail -f mpesa_callbacks.log`
- Review M-Pesa documentation
- Test with `/health` endpoint

## License

MIT License
