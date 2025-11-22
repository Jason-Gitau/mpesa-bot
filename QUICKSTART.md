# Quick Start Guide

Get your M-Pesa Telegram bot running in 5 minutes!

## Prerequisites

- Python 3.11+ installed
- Git installed
- Telegram account
- M-Pesa Daraja API credentials

## Step 1: Clone and Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/mpesa-bot.git
cd mpesa-bot

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Get Your Credentials

### Telegram Bot Token

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow prompts
3. Copy your bot token

### Telegram Chat ID

1. Search for `@userinfobot` on Telegram
2. Send `/start`
3. Copy your Chat ID

### M-Pesa Sandbox Credentials

1. Visit https://developer.safaricom.co.ke/
2. Sign up and log in
3. Create new app → Select "Lipa Na M-Pesa Sandbox"
4. Copy Consumer Key, Consumer Secret, and Passkey

## Step 3: Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit the .env file with your credentials
nano .env  # or use any text editor
```

Add your credentials:
```env
TELEGRAM_BOT_TOKEN=your_actual_bot_token
SELLER_CHAT_ID=your_actual_chat_id
MPESA_CONSUMER_KEY=your_actual_consumer_key
MPESA_CONSUMER_SECRET=your_actual_consumer_secret
MPESA_PASSKEY=your_actual_passkey
```

## Step 4: Run the Bot

### Simple Version (for testing)

```bash
python mpesabotgig.py
```

### Production Version (with database)

First, set up your database (MySQL or PostgreSQL), then:

```bash
python weekendvibe.py
```

### Callback Server (M-Pesa payment callbacks)

For handling M-Pesa payment callbacks:

```bash
# Set up database first
mysql -u root -p < database_schema.sql

# Run the callback server
python callback_server.py

# Test it
python test_callback.py
```

See [CALLBACK_SERVER_README.md](CALLBACK_SERVER_README.md) for detailed documentation.

## Step 5: Test Your Bot

1. Open Telegram
2. Search for your bot username
3. Send `/start`
4. Try a payment: `/pay 254712345678 10`
5. Click "Confirm" button
6. Enter M-Pesa PIN `1234` (sandbox only)

## Using Docker (Alternative)

```bash
# Create .env file first
cp .env.example .env
# Edit .env with your credentials

# Run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the bot
docker-compose down
```

## Troubleshooting

**Bot not responding?**
- Check your bot token is correct
- Make sure the bot is running (check terminal)

**Payment fails?**
- Verify M-Pesa credentials
- Check phone number format: `254XXXXXXXXX`
- For sandbox, use test number and PIN `1234`

**Need help?**
- Check the full [README.md](README.md) for detailed documentation
- Open an issue on GitHub

## Next Steps

- Read the full documentation in [README.md](README.md)
- Set up callback URL with ngrok for testing
- Configure database for production use
- Deploy to production server

---

Happy coding! If this helps, give us a star ⭐
