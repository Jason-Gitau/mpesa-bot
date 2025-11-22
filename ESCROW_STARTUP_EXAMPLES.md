# Escrow Integration - Startup Examples

## Example 1: Bot Startup WITHOUT Escrow Modules

```
WARNING:__main__:Escrow modules not available: No module named 'escrow_database'
WARNING:__main__:Bot will run without escrow functionality

╔==========================================================╗
║                  M-PESA TELEGRAM BOT                   ║
╚==========================================================╝

📅 Startup Time: 2025-11-22 19:30:45

🔧 Configuration:
   • Environment:        production
   • M-Pesa Mode:        SANDBOX
   • Bot Token:          1234567890:ABCDEF...
   • Callback URL:       https://example.com/callback
   • Callback Server:    0.0.0.0:8000
   • Database:           localhost:3306/mpesa_bot
   • Log Level:          INFO

💰 Escrow System Status:
   • Status:             DISABLED

🚀 Starting services...

INFO:__main__:Setting up Telegram bot application...
INFO:__main__:Registering payment command handlers...
INFO:__main__:Registering callback query handlers...
INFO:__main__:Registering message handlers...
INFO:__main__:✓ Telegram bot configured successfully with 10 handlers
INFO:__main__:✓ Telegram bot is now running and polling for updates
============================================================
🤖 Bot is ready to accept commands!
============================================================

Available commands:
  • /start - Start the bot
  • /help - Show help
  • /pay - Make M-Pesa payment
  • /status - Check payment status
  • /cancel - Cancel payment
  • /info - Bot information
  • /service - Service details
```

## Example 2: Bot Startup WITH Escrow Modules (Initial State)

```
INFO:__main__:✓ Escrow modules imported successfully

╔==========================================================╗
║                  M-PESA TELEGRAM BOT                   ║
╚==========================================================╝

📅 Startup Time: 2025-11-22 19:30:45

🔧 Configuration:
   • Environment:        production
   • M-Pesa Mode:        SANDBOX
   • Bot Token:          1234567890:ABCDEF...
   • Callback URL:       https://example.com/callback
   • Callback Server:    0.0.0.0:8000
   • Database:           localhost:3306/mpesa_bot
   • Log Level:          INFO

💰 Escrow System Status:
   • Status:             ENABLED
   • Active Transactions: 0
   • Total Held (KES):   0.00
   • Pending Disputes:   0
   • Background Tasks:   RUNNING

🚀 Starting services...

INFO:__main__:Setting up Telegram bot application...
INFO:__main__:Registering payment command handlers...
INFO:__main__:Registering escrow command handlers...
INFO:__main__:  - Registering buyer commands...
INFO:__main__:  - Registering seller commands...
INFO:__main__:  - Registering admin commands...
INFO:__main__:✓ Escrow command handlers registered successfully
INFO:__main__:Registering callback query handlers...
INFO:__main__:Registering message handlers...
INFO:__main__:✓ Telegram bot configured successfully with 29 handlers
INFO:__main__:Setting up escrow automation scheduler...
INFO:__main__:  ✓ Scheduled auto-release task (every 1 hour)
INFO:__main__:  ✓ Scheduled auto-refund task (every 6 hours)
INFO:__main__:  ✓ Scheduled reminder notifications (every 12 hours)
INFO:__main__:  ✓ Scheduled fraud detection (daily at midnight)
INFO:__main__:  ✓ Scheduled seller rating updates (daily at 1 AM)
INFO:__main__:✓ Escrow automation scheduler started successfully
INFO:__main__:✓ Health checks completed
INFO:__main__:✓ Telegram bot is now running and polling for updates
============================================================
🤖 Bot is ready to accept commands!
============================================================

Available commands:

📱 Payment Commands:
  • /start - Start the bot
  • /help - Show help
  • /pay - Make M-Pesa payment
  • /status - Check payment status
  • /cancel - Cancel payment
  • /info - Bot information
  • /service - Service details

🛒 Buyer Commands:
  • /buy - Initiate escrow purchase
  • /my_purchases - View purchase history
  • /confirm_delivery - Confirm delivery received
  • /dispute - Open dispute
  • /track - Track order status
  • /cancel_order - Cancel pending order

🏪 Seller Commands:
  • /register_seller - Register as seller
  • /my_sales - View sales history
  • /mark_shipped - Mark order shipped
  • /request_release - Request funds release
  • /seller_stats - View statistics
  • /withdraw - Withdraw funds
  • /seller_help - Seller help guide

👨‍💼 Admin Commands:
  • /verify_seller - Verify seller account
  • /suspend_seller - Suspend seller account
  • /resolve_dispute - Resolve dispute
  • /escrow_dashboard - View dashboard
  • /disputed_transactions - View disputes
  • /suspicious_users - View flagged users
  • /freeze_transaction - Freeze transaction
  • /manual_refund - Process refund
  • /manual_release - Release funds
```

## Example 3: Bot Startup WITH Escrow Modules (Active Transactions)

```
INFO:__main__:✓ Escrow modules imported successfully

╔==========================================================╗
║                  M-PESA TELEGRAM BOT                   ║
╚==========================================================╝

📅 Startup Time: 2025-11-22 19:30:45

🔧 Configuration:
   • Environment:        production
   • M-Pesa Mode:        LIVE
   • Bot Token:          1234567890:ABCDEF...
   • Callback URL:       https://example.com/callback
   • Callback Server:    0.0.0.0:8000
   • Database:           localhost:3306/mpesa_bot
   • Log Level:          INFO

💰 Escrow System Status:
   • Status:             ENABLED
   • Active Transactions: 47
   • Total Held (KES):   285,450.00
   • Pending Disputes:   3
   • Background Tasks:   RUNNING

🚀 Starting services...

INFO:__main__:✓ Health checks completed
INFO:__main__:✓ Telegram bot is now running and polling for updates
============================================================
🤖 Bot is ready to accept commands!
============================================================
```

## Example 4: Health Check Warnings (During Operation)

```
INFO:__main__:Running health checks...
WARNING:__main__:⚠️  HIGH DISPUTE COUNT: 12 pending disputes!
INFO:__main__:✓ Health checks completed
```

```
INFO:__main__:Running health checks...
WARNING:__main__:⚠️  AUTO-RELEASE FAILURES: 7 failed attempts
WARNING:__main__:⚠️  OLD FROZEN TRANSACTIONS: 3 transactions frozen >7 days
INFO:__main__:✓ Health checks completed
```

## Example 5: Graceful Shutdown WITH Escrow

```
============================================================
Received SIGTERM signal. Initiating graceful shutdown...
============================================================

INFO:__main__:Performing cleanup...
INFO:__main__:Stopping escrow scheduler...
INFO:__main__:Completing pending auto-releases...
INFO:__main__:  - Processing transaction #1234: 5,000 KES
INFO:__main__:  - Processing transaction #1235: 12,500 KES
INFO:__main__:  - Processing transaction #1236: 3,200 KES
INFO:__main__:✓ Pending auto-releases completed (3 transactions)
INFO:__main__:✓ Escrow scheduler stopped
INFO:__main__:Closing escrow database connections...
INFO:__main__:✓ Escrow database connections closed
INFO:__main__:Closing database connections...
INFO:__main__:✓ Database connections closed
INFO:__main__:Waiting for FastAPI thread to terminate...
INFO:__main__:✓ Cleanup complete
INFO:__main__:Shutdown complete. Goodbye!
```

## Example 6: Escrow Module Error (Partial Failure)

```
INFO:__main__:✓ Escrow modules imported successfully
INFO:__main__:Initializing escrow database...
ERROR:__main__:Escrow database initialization failed: Table 'escrow_transactions' doesn't exist
WARNING:__main__:Continuing without escrow functionality...

╔==========================================================╗
║                  M-PESA TELEGRAM BOT                   ║
╚==========================================================╝

📅 Startup Time: 2025-11-22 19:30:45

🔧 Configuration:
   • Environment:        production
   • M-Pesa Mode:        SANDBOX
   • Bot Token:          1234567890:ABCDEF...
   • Callback URL:       https://example.com/callback
   • Callback Server:    0.0.0.0:8000
   • Database:           localhost:3306/mpesa_bot
   • Log Level:          INFO

💰 Escrow System Status:
   • Status:             ERROR (Stats unavailable)

🚀 Starting services...

INFO:__main__:Setting up Telegram bot application...
INFO:__main__:Registering payment command handlers...
INFO:__main__:Registering callback query handlers...
INFO:__main__:✓ Telegram bot configured successfully
```

## Scheduled Task Execution Logs

### Auto-Release Task (Every 1 hour)
```
INFO:apscheduler.executors.default:Running job "Auto-release completed deliveries" (scheduled at 2025-11-22 20:00:00)
INFO:escrow_automation:Auto-release task started
INFO:escrow_automation:  - Released transaction #1234: 5,000 KES to seller
INFO:escrow_automation:  - Released transaction #1238: 8,500 KES to seller
INFO:escrow_automation:Auto-release task completed: 2 transactions released
INFO:apscheduler.executors.default:Job "Auto-release completed deliveries" executed successfully
```

### Fraud Detection Task (Daily at midnight)
```
INFO:apscheduler.executors.default:Running job "Fraud detection scan" (scheduled at 2025-11-23 00:00:00)
INFO:escrow_automation:Fraud detection task started
INFO:escrow_automation:  - Flagged user 123456789 for suspicious activity
INFO:escrow_automation:  - Frozen transaction #1240 pending review
INFO:escrow_automation:Fraud detection task completed: 1 user flagged, 1 transaction frozen
INFO:apscheduler.executors.default:Job "Fraud detection scan" executed successfully
```

## Expected Handler Count

### Without Escrow:
- **Total handlers**: ~10-12
  - 8 command handlers (start, help, pay, confirm, status, cancel, info, service)
  - 1 callback query handler
  - 2 message handlers

### With Escrow:
- **Total handlers**: ~28-30
  - 8 payment command handlers
  - 6 buyer command handlers
  - 7 seller command handlers
  - 9 admin command handlers
  - 1 combined callback query handler
  - 2 message handlers

## Summary

The integration provides:
- ✅ Graceful degradation (works without escrow)
- ✅ Clear status reporting in startup banner
- ✅ Comprehensive logging
- ✅ Automated background tasks
- ✅ Health monitoring
- ✅ Graceful shutdown with cleanup
- ✅ Backward compatibility
