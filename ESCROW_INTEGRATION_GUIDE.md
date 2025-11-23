# Escrow System Integration Guide

This guide explains how to integrate the escrow system modules into your M-Pesa bot.

## Overview

The escrow system consists of three main modules:

1. **escrow_service.py** - Core business logic and database operations
2. **escrow_handlers_admin.py** - Admin command handlers for Telegram bot
3. **escrow_automation.py** - Background automation tasks using APScheduler

## Installation

### 1. Install Dependencies

The required dependencies are already in `requirements.txt`. Install them:

```bash
pip install -r requirements.txt
```

Key dependencies:
- `APScheduler==3.10.4` - For background task scheduling
- `asyncpg` - For PostgreSQL async operations (via database.py)
- `python-telegram-bot==20.7` - For Telegram bot integration

### 2. Database Setup

The escrow system will automatically create the following tables when initialized:

- `escrow_sellers` - Seller accounts and verification
- `escrow_transactions` - Escrow payment transactions
- `escrow_disputes` - Dispute management
- `escrow_timeline` - Transaction event history
- `seller_ratings` - Buyer ratings for sellers
- `fraud_flags` - Suspicious activity tracking

**Note:** Tables are created automatically on first run. No manual SQL execution needed.

### 3. Configuration

Update your `.env` file with admin user IDs:

```env
# Admin Configuration (comma-separated Telegram user IDs)
ADMIN_CHAT_ID=123456789,987654321

# Existing M-Pesa and Telegram config...
TELEGRAM_BOT_TOKEN=your_token_here
SUPABASE_DB_URL=postgresql://user:pass@host:5432/database
```

## Integration Steps

### Step 1: Update main.py

Add the escrow system to your bot's main file:

```python
# main.py

from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from escrow_automation import start_automation, stop_automation
from escrow_handlers_admin import (
    verify_seller,
    suspend_seller,
    resolve_dispute,
    escrow_dashboard,
    disputed_transactions,
    suspicious_users,
    freeze_transaction,
    manual_refund,
    manual_release,
    system_health
)

async def post_init(application: Application) -> None:
    """Initialize services after bot starts."""
    # Start escrow automation
    await start_automation(application.bot)
    logger.info("Escrow automation started")

async def post_shutdown(application: Application) -> None:
    """Cleanup when bot shuts down."""
    # Stop escrow automation
    await stop_automation()
    logger.info("Escrow automation stopped")

def main():
    # Build application with lifecycle hooks
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Add admin command handlers
    application.add_handler(CommandHandler("verify_seller", verify_seller))
    application.add_handler(CommandHandler("suspend_seller", suspend_seller))
    application.add_handler(CommandHandler("resolve_dispute", resolve_dispute))
    application.add_handler(CommandHandler("escrow_dashboard", escrow_dashboard))
    application.add_handler(CommandHandler("disputed_transactions", disputed_transactions))
    application.add_handler(CommandHandler("suspicious_users", suspicious_users))
    application.add_handler(CommandHandler("freeze_transaction", freeze_transaction))
    application.add_handler(CommandHandler("manual_refund", manual_refund))
    application.add_handler(CommandHandler("manual_release", manual_release))
    application.add_handler(CommandHandler("system_health", system_health))

    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()
```

### Step 2: Initialize Database Tables

The tables will be created automatically when you first run the bot. The initialization happens in:

```python
from database import get_database
from escrow_service import get_escrow_service

# This is called automatically in escrow_automation.py
db = await get_database()
escrow_service = await get_escrow_service(db.pool)
# Tables are now created
```

### Step 3: Create User Handlers (Optional)

Create user-facing escrow commands in a new file `escrow_handlers_user.py`:

```python
# escrow_handlers_user.py

from telegram import Update
from telegram.ext import ContextTypes
from escrow_service import get_escrow_service
from database import get_database

async def create_escrow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User command to create an escrow transaction."""
    # Your implementation here
    pass

async def mark_shipped(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Seller marks order as shipped."""
    # Your implementation here
    pass

async def confirm_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Buyer confirms delivery."""
    # Your implementation here
    pass

async def raise_dispute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Buyer/seller raises a dispute."""
    # Your implementation here
    pass
```

## Admin Commands Reference

### Seller Management

#### Verify Seller
```
/verify_seller <seller_id>
```
Verifies a pending seller account, allowing them to accept escrow payments.

**Example:**
```
/verify_seller 123
```

#### Suspend Seller
```
/suspend_seller <seller_id> <reason>
```
Suspends a seller account with a reason.

**Example:**
```
/suspend_seller 123 Multiple fraud reports
```

### Dispute Resolution

#### Resolve Dispute
```
/resolve_dispute <transaction_id> <buyer/seller/split> <notes>
```
Resolves an active dispute.

**Decisions:**
- `buyer` - Full refund to buyer
- `seller` - Full release to seller
- `split` - Split funds 50/50

**Example:**
```
/resolve_dispute TXN123 buyer Product never received, proof provided
```

### System Monitoring

#### Escrow Dashboard
```
/escrow_dashboard
```
Shows comprehensive system overview:
- Financial stats (held, released, refunded)
- Transaction counts
- Seller statistics

#### Disputed Transactions
```
/disputed_transactions
```
Lists all active disputes requiring attention.

#### Suspicious Users
```
/suspicious_users
```
Shows flagged users and fraud alerts.

#### System Health
```
/system_health
```
Performs health check:
- Database connectivity
- Stuck transactions
- Old unresolved disputes
- Critical fraud flags

### Manual Actions

#### Freeze Transaction
```
/freeze_transaction <transaction_id>
```
Manually freezes a transaction (prevents auto-actions).

**Example:**
```
/freeze_transaction TXN123
```

#### Manual Refund
```
/manual_refund <transaction_id> [reason]
```
Forces immediate refund to buyer.

**Example:**
```
/manual_refund TXN123 Admin override
```

#### Manual Release
```
/manual_release <transaction_id>
```
Forces immediate release to seller.

**Example:**
```
/manual_release TXN123
```

## Automation Tasks

The automation system runs the following background tasks:

### 1. Auto-Release Payments
- **Schedule:** Every 1 hour
- **Action:** Releases payments for shipped orders after 7 days with no disputes
- **Notifications:** Sent to both buyer and seller

### 2. Auto-Refund Unshipped
- **Schedule:** Every 6 hours
- **Action:** Refunds buyers if seller doesn't ship within 3 days
- **Flags:** Marks seller for review

### 3. Reminder Notifications
- **Schedule:** Every 12 hours (9 AM, 9 PM)
- **Reminders:**
  - Buyers: Confirm delivery (days 5-6)
  - Sellers: Ship order (days 1-2)
  - Auto-release warnings (day 6)

### 4. Calculate Seller Ratings
- **Schedule:** Daily at midnight
- **Action:** Updates average ratings, success rates, dispute counts

### 5. Fraud Detection
- **Schedule:** Daily at 2 AM
- **Patterns Detected:**
  - Multiple disputes from same buyer (3+ in 30 days)
  - High seller dispute rate (>30%)
  - Repeated refunds (3+ in 14 days)

### 6. Cleanup Expired Transactions
- **Schedule:** Weekly on Sunday at 3 AM
- **Action:**
  - Archives transactions older than 90 days
  - Cleans resolved fraud flags (30+ days)
  - Generates monthly reports

## Testing

### 1. Test Database Connection

```bash
python -c "
import asyncio
from database import get_database
from escrow_service import get_escrow_service

async def test():
    db = await get_database()
    escrow = await get_escrow_service(db.pool)
    print('✓ Escrow service initialized')
    stats = await escrow.get_escrow_dashboard_stats()
    print(f'✓ Dashboard stats: {stats}')

asyncio.run(test())
"
```

### 2. Test Admin Commands

1. Start your bot
2. Send `/escrow_dashboard` to verify admin access
3. Check system health with `/system_health`

### 3. Test Automation

Check scheduler logs:
```
[INFO] Escrow automation started successfully
[INFO] Scheduled jobs: 6
[INFO] Starting auto-release payments task
[INFO] Found 0 transactions eligible for auto-release
```

## Monitoring

### Logs

All automation tasks log their activity:

```
2025-11-22 10:00:00 - INFO - Starting auto-release payments task
2025-11-22 10:00:01 - INFO - Found 5 transactions eligible for auto-release
2025-11-22 10:00:05 - INFO - Auto-released payment: TXN123
2025-11-22 10:00:10 - INFO - Auto-release task completed: 5 released, 0 failed in 10.23s
```

### Statistics

Get automation statistics:

```python
from escrow_automation import get_escrow_automation

automation = await get_escrow_automation(bot)
stats = automation.get_stats()
print(stats)
```

Output:
```python
{
    'is_running': True,
    'scheduled_jobs': 6,
    'stats': {
        'auto_releases': 25,
        'auto_refunds': 3,
        'reminders_sent': 47,
        'fraud_flags': 2,
        'last_run': {
            'auto_release': datetime(...),
            'auto_refund': datetime(...),
            ...
        }
    },
    'uptime': 86400.0  # seconds
}
```

## Troubleshooting

### Issue: Tables not created

**Solution:**
```python
from database import get_database
from escrow_service import get_escrow_service

db = await get_database()
escrow = await get_escrow_service(db.pool)
await escrow.init_escrow_tables()
```

### Issue: Automation not running

**Check:**
1. `post_init` is called in Application builder
2. Check logs for scheduler errors
3. Verify APScheduler is installed: `pip show APScheduler`

### Issue: Admin commands not working

**Check:**
1. User ID is in `ADMIN_CHAT_ID` environment variable
2. Admin decorator is applied to handlers
3. Handlers are registered in main.py

### Issue: Notifications not sent

**Check:**
1. Bot token is valid
2. Users have started the bot (can't send unsolicited messages)
3. Check Telegram API rate limits

## Security Considerations

1. **Admin Access:** Only users in `ADMIN_CHAT_ID` can use admin commands
2. **Input Validation:** All inputs are sanitized using `sanitize_input()`
3. **SQL Injection:** Using parameterized queries (asyncpg)
4. **Rate Limiting:** Consider adding rate limits to user commands
5. **Logging:** Sensitive data is not logged (phone numbers, amounts masked)

## Performance Optimization

1. **Database Indexes:** Already created on frequently queried columns
2. **Connection Pooling:** Uses asyncpg connection pool (2-10 connections)
3. **Batch Operations:** Automation tasks process in batches
4. **Async Operations:** All database operations are async/await

## Next Steps

1. **Implement User Handlers:** Create commands for buyers and sellers
2. **Add Payment Integration:** Connect escrow to M-Pesa payment flow
3. **Customize Notifications:** Adjust message templates
4. **Configure Schedules:** Modify automation task schedules if needed
5. **Add Analytics:** Implement detailed reporting and analytics

## Support

For issues or questions:
1. Check logs in `logs/app.log`
2. Review database queries in PostgreSQL logs
3. Test individual components in isolation
4. Check APScheduler documentation: https://apscheduler.readthedocs.io/

## License

This escrow system is part of the M-Pesa Bot project and follows the same license.
