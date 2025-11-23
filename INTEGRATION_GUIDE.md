# M-Pesa Callback Server Integration Guide

## Overview

This guide shows how to integrate the callback server with your existing M-Pesa bot.

## Step 1: Update STK Push to Use Callback URL

In your bot code (e.g., `mpesabotgig.py`), update the STK Push function:

```python
def initiate_stk_push(phone_number, amount):
    """Initiate M-Pesa STK Push with callback URL."""
    import base64
    from datetime import datetime
    
    access_token = get_mpesa_access_token()
    if not access_token:
        return "Failed to authenticate with M-Pesa."
    
    # Generate timestamp and password
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    password_str = f"{SHORTCODE}{PASSKEY}{timestamp}"
    password = base64.b64encode(password_str.encode()).decode('utf-8')
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "BusinessShortCode": "174379",
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": "174379",
        "PhoneNumber": phone_number,
        # UPDATE THIS LINE - Use your callback server URL
        "CallBackURL": "https://your-domain.com/mpesa/callback",
        "AccountReference": "Payment",
        "TransactionDesc": "Payment for services"
    }
    
    try:
        response = requests.post(MPESA_STK_PUSH_URL, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error initiating STK push: {e}")
        return {"error": str(e)}
```

## Step 2: Store User Phone Numbers in Database

Add this function to save user phone numbers when they use `/pay`:

```python
import aiomysql
import os

async def save_user_to_database(chat_id, username, phone_number):
    """Save or update user in database."""
    try:
        connection = await aiomysql.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            db=os.getenv('DB_NAME', 'mpesa_bot')
        )
        
        async with connection.cursor() as cursor:
            query = """
                INSERT INTO users (telegram_chat_id, telegram_username, phone_number)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    telegram_username = VALUES(telegram_username),
                    phone_number = VALUES(phone_number)
            """
            await cursor.execute(query, (chat_id, username, phone_number))
            await connection.commit()
        
        connection.close()
    except Exception as e:
        print(f"Error saving user: {e}")
```

Update your `/pay` command to save user info:

```python
async def pay(update: Update, context: CallbackContext) -> None:
    """Handle /pay command."""
    text = update.message.text.split()
    
    if len(text) == 3:
        _, phone, amount = text
        
        # Save user to database
        await save_user_to_database(
            chat_id=update.message.chat_id,
            username=update.message.from_user.username,
            phone_number=phone
        )
        
        context.user_data["phone"] = phone
        context.user_data["amount"] = amount
        
        # Show confirmation
        keyboard = [
            [InlineKeyboardButton("✅ Confirm", callback_data="confirm")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"💰 Amount: KES {amount}\n📱 Phone: {phone}\n\nConfirm payment?",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "Please use format: /pay <phone> <amount>\n"
            "Example: /pay 254712345678 100"
        )
```

## Step 3: Save Transaction Before STK Push

Update your confirm function to save the transaction:

```python
async def save_payment_request(user_id, checkout_request_id, phone, amount):
    """Save payment request to database."""
    try:
        connection = await aiomysql.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            db=os.getenv('DB_NAME', 'mpesa_bot')
        )
        
        async with connection.cursor() as cursor:
            # Get user ID
            await cursor.execute(
                "SELECT id FROM users WHERE telegram_chat_id = %s",
                (user_id,)
            )
            result = await cursor.fetchone()
            user_db_id = result[0] if result else None
            
            if user_db_id:
                query = """
                    INSERT INTO payment_requests 
                    (user_id, checkout_request_id, phone_number, amount, status)
                    VALUES (%s, %s, %s, %s, 'Initiated')
                """
                await cursor.execute(query, (user_db_id, checkout_request_id, phone, amount))
                await connection.commit()
        
        connection.close()
    except Exception as e:
        print(f"Error saving payment request: {e}")


async def button_callback(update: Update, context: CallbackContext) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm":
        phone = context.user_data.get("phone")
        amount = context.user_data.get("amount")
        
        if not phone or not amount:
            await query.edit_message_text("No payment details found.")
            return
        
        # Initiate M-Pesa payment
        result = initiate_stk_push(phone, amount)
        
        if "errorCode" in result:
            await query.edit_message_text(f"❌ Payment failed: {result.get('errorMessage')}")
        else:
            # Save to database
            checkout_request_id = result.get('CheckoutRequestID')
            if checkout_request_id:
                await save_payment_request(
                    user_id=query.message.chat_id,
                    checkout_request_id=checkout_request_id,
                    phone=phone,
                    amount=amount
                )
            
            await query.edit_message_text(
                "✅ Payment request sent!\n"
                "Please check your phone and enter M-Pesa PIN.\n\n"
                "You'll receive a confirmation once payment is complete."
            )
    
    elif query.data == "cancel":
        context.user_data.clear()
        await query.edit_message_text("Payment canceled.")
```

## Step 4: Run Both Services

### Option A: Separate Processes

Run the bot and callback server separately:

```bash
# Terminal 1: Run the bot
python mpesabotgig.py

# Terminal 2: Run the callback server
python callback_server.py
```

### Option B: Combined Service (Docker)

Update `docker-compose.yml`:

```yaml
version: '3.8'

services:
  mysql:
    image: mysql:8.0
    container_name: mpesa-mysql
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_PASSWORD}
      MYSQL_DATABASE: ${DB_NAME}
    volumes:
      - mysql-data:/var/lib/mysql
      - ./database_schema.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - mpesa-network

  telegram-bot:
    build: .
    container_name: mpesa-telegram-bot
    restart: unless-stopped
    command: python mpesabotgig.py
    env_file: .env
    depends_on:
      - mysql
    networks:
      - mpesa-network

  callback-server:
    build: .
    container_name: mpesa-callback-server
    restart: unless-stopped
    command: uvicorn callback_server:app --host 0.0.0.0 --port 8000
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      - mysql
    networks:
      - mpesa-network

volumes:
  mysql-data:

networks:
  mpesa-network:
    driver: bridge
```

Then run:

```bash
docker-compose up -d
```

## Step 5: Get Your Callback URL

### Development (ngrok)

```bash
# Start callback server
python callback_server.py

# In another terminal, expose it
ngrok http 8000

# Copy the HTTPS URL
# Example: https://abc123.ngrok.io
# Your callback URL: https://abc123.ngrok.io/mpesa/callback
```

### Production

1. Deploy to a VPS
2. Get a domain (e.g., mpesa.yourdomain.com)
3. Set up SSL with Let's Encrypt
4. Your callback URL: https://mpesa.yourdomain.com/mpesa/callback

## Step 6: Update M-Pesa Sandbox Settings

1. Go to https://developer.safaricom.co.ke/
2. Navigate to your app
3. Update the callback URL (if required)
4. Test with sandbox

## Complete Example Flow

```
User                  Bot                  M-Pesa API           Callback Server
 |                     |                        |                      |
 |--[/pay 254... 100]->|                        |                      |
 |                     |--[Save user DB]------->|                      |
 |<-[Confirm button]---|                        |                      |
 |                     |                        |                      |
 |--[Click confirm]--->|                        |                      |
 |                     |--[STK Push request]--->|                      |
 |                     |                        |                      |
 |                     |--[Save payment DB]---->|                      |
 |                     |                        |                      |
 |<-[Check phone]------|                        |                      |
 |                     |                        |                      |
 |<-[M-Pesa prompt]----|<-[STK Push]------------|                      |
 |                     |                        |                      |
 |--[Enter PIN]------->|--[Confirm payment]---->|                      |
 |                     |                        |                      |
 |                     |                        |--[Callback POST]---->|
 |                     |                        |                      |
 |                     |                        |                      |--[Update DB]
 |                     |                        |                      |
 |                     |<-[Admin notification]--|<-[Send notification]-|
 |<-[Receipt]----------|<-[User notification]---|<-[Send receipt]------|
```

## Environment Variables

Make sure your `.env` has all required variables:

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
ADMIN_CHAT_ID=your_admin_chat_id

# M-Pesa
MPESA_CONSUMER_KEY=your_key
MPESA_CONSUMER_SECRET=your_secret
MPESA_SHORTCODE=174379
MPESA_PASSKEY=your_passkey

# Database
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=mpesa_bot

# Callback URL (for reference)
CALLBACK_URL=https://your-domain.com/mpesa/callback
```

## Testing the Integration

1. **Start services:**
   ```bash
   python callback_server.py
   python mpesabotgig.py  # or your bot file
   ```

2. **Test callback server:**
   ```bash
   python test_callback.py
   ```

3. **Test full flow:**
   - Send `/start` to your bot
   - Send `/pay 254712345678 10`
   - Click Confirm
   - Enter M-Pesa PIN (1234 for sandbox)
   - Wait for notifications

4. **Check database:**
   ```sql
   USE mpesa_bot;
   SELECT * FROM transactions ORDER BY created_at DESC LIMIT 5;
   SELECT * FROM users;
   SELECT * FROM payment_requests ORDER BY created_at DESC LIMIT 5;
   ```

## Troubleshooting

### No callback received
- Verify callback URL is publicly accessible
- Check M-Pesa sandbox logs
- Ensure callback server is running
- Check `mpesa_callbacks.log`

### Database errors
- Verify database exists: `SHOW DATABASES;`
- Check credentials in `.env`
- Ensure tables created: `mysql -u root -p mpesa_bot < database_schema.sql`

### User not receiving receipt
- Verify user exists in database
- Check phone number matches
- Ensure TELEGRAM_BOT_TOKEN is correct
- Check bot logs

## Production Checklist

- [ ] Update callback URL in STK Push code
- [ ] Deploy callback server to production
- [ ] Set up SSL/HTTPS
- [ ] Test with sandbox
- [ ] Monitor logs
- [ ] Set up database backups
- [ ] Configure monitoring/alerts
- [ ] Test failure scenarios
- [ ] Document deployment

## Support

For issues:
1. Check logs: `tail -f mpesa_callbacks.log`
2. Test health: `curl http://localhost:8000/health`
3. Review documentation: `CALLBACK_SERVER_README.md`
4. Check M-Pesa docs: https://developer.safaricom.co.ke/

---

Happy integrating! 🚀
