# M-Pesa Telegram Bot

A Python-based Telegram bot that integrates with Safaricom's M-Pesa (Daraja API) to facilitate mobile payments directly through Telegram. This bot allows users to initiate M-Pesa STK Push payments and receive transaction notifications in real-time.

## Features

- **M-Pesa Integration**: Seamless integration with Safaricom's Daraja API for STK Push payments
- **Telegram Bot Interface**: User-friendly commands for payment initiation
- **Real-time Notifications**: Instant transaction updates for both buyers and sellers
- **Payment Confirmation**: Interactive inline buttons for payment confirmation
- **Transaction Tracking**: Database storage for all payment transactions
- **Callback Handling**: FastAPI webhook endpoint for M-Pesa callbacks
- **Chat Memory**: Conversation tracking for enhanced user experience

## Project Structure

```
mpesa-bot/
├── mpesabotgig.py          # Simple bot version (hardcoded credentials - for testing)
├── weekendvibe.py          # Advanced bot version (with database & FastAPI callbacks)
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (create from .env.example)
├── .env.example           # Environment variables template
├── Dockerfile             # Docker container configuration
├── docker-compose.yml     # Docker Compose orchestration
└── README.md             # This file
```

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.11+** - [Download Python](https://www.python.org/downloads/)
- **Git** - [Download Git](https://git-scm.com/downloads)
- **pip** - Python package installer (comes with Python)
- **A Telegram Account** - [Download Telegram](https://telegram.org/)
- **M-Pesa Developer Account** - [Safaricom Daraja Portal](https://developer.safaricom.co.ke/)
- **Docker** (optional) - [Download Docker](https://www.docker.com/get-started)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/mpesa-bot.git
cd mpesa-bot
```

### 2. Create Virtual Environment

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Configuration

### 1. Telegram Bot Setup

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` to create a new bot
3. Follow the prompts to choose a name and username for your bot
4. Copy the **Bot Token** (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. To get your **Chat ID**:
   - Search for [@userinfobot](https://t.me/userinfobot) on Telegram
   - Send `/start` and copy your ID

### 2. M-Pesa Sandbox Setup

1. **Create Developer Account**:
   - Visit [Safaricom Daraja Portal](https://developer.safaricom.co.ke/)
   - Sign up and verify your email
   - Log in to the developer portal

2. **Create a Sandbox App**:
   - Go to "My Apps" → "Create New App"
   - Select "Lipa Na M-Pesa Sandbox"
   - Fill in app details and submit

3. **Get API Credentials**:
   - Click on your app to view details
   - Copy the **Consumer Key** (Client ID)
   - Copy the **Consumer Secret** (Client Secret)
   - Note the **Business Short Code** (Sandbox: `174379`)
   - Copy the **Passkey** (found in "Test Credentials" section)

4. **Configure Callback URL**:
   - Use ngrok for local testing: `ngrok http 8000`
   - Or use your deployed server URL: `https://yourdomain.com/mpesa-callback`
   - Add this URL in your M-Pesa app settings

### 3. Database Setup (Optional - for weekendvibe.py)

If using the advanced version with database integration:

**Using MySQL:**
```sql
CREATE DATABASE mpesa_bot;
USE mpesa_bot;

CREATE TABLE transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transaction_id VARCHAR(100) UNIQUE,
    buyer_name VARCHAR(255),
    amount DECIMAL(10, 2),
    timestamp DATETIME,
    status VARCHAR(50),
    payment_method VARCHAR(50)
);
```

**Using Supabase (Recommended for beginners):**
1. Visit [Supabase](https://supabase.com/)
2. Create a new project
3. Go to "SQL Editor" and run the above SQL query
4. Get your database credentials from Project Settings → Database

### 4. Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
SELLER_CHAT_ID=your_telegram_chat_id_here

# M-Pesa API Configuration (Sandbox)
MPESA_CONSUMER_KEY=your_consumer_key_here
MPESA_CONSUMER_SECRET=your_consumer_secret_here
MPESA_SHORTCODE=174379
MPESA_PASSKEY=your_passkey_here

# Database Configuration (for weekendvibe.py)
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_db_password
DB_NAME=mpesa_bot

# Production M-Pesa (uncomment when going live)
# MPESA_SHORTCODE=your_production_shortcode
# MPESA_PASSKEY=your_production_passkey
```

**Security Warning**: Never commit your `.env` file to Git. It's already in `.gitignore`.

## Running the Application

### Option 1: Simple Version (mpesabotgig.py)

Best for testing and learning:

```bash
python mpesabotgig.py
```

**Note**: This version has hardcoded credentials for quick testing. Replace them with your own before using.

### Option 2: Production Version (weekendvibe.py)

For production use with database and callbacks:

```bash
# Make sure you have configured the .env file
python weekendvibe.py
```

This will start:
- The Telegram bot (polling for messages)
- FastAPI server on port 8000 (for M-Pesa callbacks)

### Option 3: Using Docker

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the bot
docker-compose down
```

## Available Commands

Once your bot is running, users can interact with it using these commands:

### Basic Commands
- `/start` - Start the bot and see welcome message
- `/help` - Display all available commands
- `/info` - Get information about the bot
- `/service` - See what the bot can do

### Payment Commands
- `/pay` - Start payment process
  - Format 1: `/pay <phone> <amount>` (e.g., `/pay 254712345678 100`)
  - Format 2: `/pay` (then follow prompts)
- `/confirm` - Confirm and process the payment
- `/status` - Check payment status
- `/cancel` - Cancel the current payment process

### Example Usage

1. **Initiate Payment**:
   ```
   User: /pay 254712345678 500
   Bot: Payment of 500 to 254712345678 confirmed. Use /confirm to proceed.
   [✅ Confirm] [❌ Cancel]
   ```

2. **Confirm Payment**:
   - Click the "✅ Confirm" button or type `/confirm`
   - User receives M-Pesa STK Push prompt on their phone
   - Enter M-Pesa PIN to complete payment

3. **Check Status**:
   ```
   User: /status
   Bot: Payment status check results...
   ```

## Deployment

### Deploy to Heroku

1. **Install Heroku CLI**:
   ```bash
   # On macOS
   brew tap heroku/brew && brew install heroku

   # On Windows
   # Download from https://devcenter.heroku.com/articles/heroku-cli
   ```

2. **Login and Create App**:
   ```bash
   heroku login
   heroku create your-mpesa-bot
   ```

3. **Set Environment Variables**:
   ```bash
   heroku config:set TELEGRAM_BOT_TOKEN=your_token
   heroku config:set MPESA_CONSUMER_KEY=your_key
   heroku config:set MPESA_CONSUMER_SECRET=your_secret
   heroku config:set MPESA_SHORTCODE=174379
   heroku config:set MPESA_PASSKEY=your_passkey
   heroku config:set SELLER_CHAT_ID=your_chat_id
   ```

4. **Deploy**:
   ```bash
   git push heroku main
   ```

5. **Scale Worker**:
   ```bash
   heroku ps:scale worker=1
   ```

### Deploy to Railway

1. **Visit [Railway.app](https://railway.app/)**
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repository
4. Add environment variables in the "Variables" tab
5. Railway will automatically deploy using your Dockerfile

### Deploy to VPS (Ubuntu/Debian)

1. **Connect to your VPS**:
   ```bash
   ssh user@your-vps-ip
   ```

2. **Install dependencies**:
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip python3-venv git -y
   ```

3. **Clone and setup**:
   ```bash
   git clone https://github.com/yourusername/mpesa-bot.git
   cd mpesa-bot
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   nano .env
   # Add your credentials and save
   ```

5. **Run with systemd (keeps bot running)**:
   ```bash
   sudo nano /etc/systemd/system/mpesa-bot.service
   ```

   Add this content:
   ```ini
   [Unit]
   Description=M-Pesa Telegram Bot
   After=network.target

   [Service]
   Type=simple
   User=yourusername
   WorkingDirectory=/home/yourusername/mpesa-bot
   Environment="PATH=/home/yourusername/mpesa-bot/venv/bin"
   ExecStart=/home/yourusername/mpesa-bot/venv/bin/python weekendvibe.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

6. **Start service**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable mpesa-bot
   sudo systemctl start mpesa-bot
   sudo systemctl status mpesa-bot
   ```

### Deploy with Docker on VPS

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose -y

# Clone and run
git clone https://github.com/yourusername/mpesa-bot.git
cd mpesa-bot
nano .env  # Add your credentials
docker-compose up -d
```

## Testing with M-Pesa Sandbox

The sandbox environment allows you to test without real money:

1. **Test Phone Numbers**: Use Safaricom test numbers from the Daraja portal
2. **Test PIN**: Default sandbox PIN is `1234`
3. **Callback URL**: Use ngrok for local testing:
   ```bash
   ngrok http 8000
   # Use the HTTPS URL in your M-Pesa app settings
   ```

## Troubleshooting

### Bot not responding
- Check if bot token is correct in `.env`
- Verify the bot is running: `ps aux | grep python`
- Check logs for errors

### M-Pesa payment fails
- Verify Consumer Key and Secret are correct
- Check if callback URL is accessible (test with ngrok)
- Ensure phone number format is correct: `254XXXXXXXXX`
- Check M-Pesa API credentials are for correct environment (sandbox/production)
- Review Daraja portal logs for detailed error messages

### Database connection errors
- Verify database credentials in `.env`
- Check if MySQL/PostgreSQL service is running
- Test database connection manually

### Docker issues
- Make sure Docker daemon is running: `sudo systemctl start docker`
- Check logs: `docker-compose logs -f`
- Rebuild containers: `docker-compose up -d --build`

### Common Error Messages

**"Invalid access token"**
- Your Consumer Key or Secret is incorrect
- Re-check credentials in M-Pesa Daraja portal

**"Invalid phone number"**
- Phone must be in format: `254XXXXXXXXX` (12 digits)
- Example: `254712345678`

**"Callback URL not accessible"**
- For local testing, use ngrok
- For production, ensure your server is accessible from the internet
- Check firewall settings

## Going to Production

Before deploying to production:

1. **Update M-Pesa Credentials**:
   - Apply for production credentials on Daraja portal
   - Update `MPESA_SHORTCODE` and `MPESA_PASSKEY` in `.env`

2. **Security Checklist**:
   - [ ] Never commit `.env` file
   - [ ] Use environment variables for all secrets
   - [ ] Enable HTTPS for callback URLs
   - [ ] Implement rate limiting
   - [ ] Add input validation
   - [ ] Set up error logging

3. **Update Callback URL**:
   - Use your production domain
   - Update in M-Pesa app settings

4. **Database**:
   - Use production database (not SQLite)
   - Set up regular backups
   - Implement connection pooling

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/AmazingFeature`
3. Commit your changes: `git commit -m 'Add some AmazingFeature'`
4. Push to the branch: `git push origin feature/AmazingFeature`
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guide for Python code
- Add comments for complex logic
- Update documentation for new features
- Test thoroughly before submitting PR
- Keep commits atomic and descriptive

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For help and support:

- **Issues**: [GitHub Issues](https://github.com/yourusername/mpesa-bot/issues)
- **M-Pesa API Docs**: [Daraja API Documentation](https://developer.safaricom.co.ke/docs)
- **Telegram Bot API**: [Telegram Bot API Docs](https://core.telegram.org/bots/api)

## Acknowledgments

- Safaricom for the Daraja API
- Python Telegram Bot library
- All contributors to this project

## Disclaimer

This bot is for educational and testing purposes. Always comply with M-Pesa's terms of service and local regulations when handling financial transactions. The developers are not responsible for any misuse or financial losses.

---

**Happy Coding!** If you find this project helpful, please give it a star ⭐
