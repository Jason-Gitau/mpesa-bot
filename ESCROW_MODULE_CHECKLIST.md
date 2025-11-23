# Escrow Module Implementation Checklist

This checklist guides you through implementing the escrow modules that the integrated main.py expects.

## Prerequisites

- [x] main.py updated with escrow integration
- [x] APScheduler added to requirements.txt
- [ ] Install APScheduler: `pip install APScheduler==3.10.4`
- [ ] Database schema designed
- [ ] Database tables created

## Module 1: escrow_database.py

Database layer for escrow operations.

### Functions to Implement

- [ ] `async def init_escrow_database(config, database)`
  - Initialize escrow database connection
  - Create necessary tables if not exist
  - Return database connection object
  - Handle connection errors gracefully

- [ ] `async def close_escrow_database(escrow_db)`
  - Close all escrow database connections
  - Cleanup resources
  - Log closure status

### Database Tables Needed

- [ ] `escrow_transactions`
  - transaction_id (PRIMARY KEY)
  - buyer_telegram_id
  - seller_telegram_id
  - amount
  - status (pending/shipped/completed/disputed/refunded/cancelled)
  - item_description
  - created_at
  - updated_at
  - shipped_at
  - completed_at
  - dispute_reason
  - frozen (BOOLEAN)

- [ ] `escrow_sellers`
  - seller_id (PRIMARY KEY)
  - telegram_id
  - name
  - phone_number
  - mpesa_number
  - verification_status (pending/verified/suspended)
  - rating (DECIMAL)
  - total_sales
  - total_disputes
  - balance
  - created_at
  - verified_at
  - suspended_at

- [ ] `escrow_disputes`
  - dispute_id (PRIMARY KEY)
  - transaction_id (FOREIGN KEY)
  - opened_by (buyer/seller)
  - reason
  - status (pending/investigating/resolved)
  - resolution
  - created_at
  - resolved_at
  - resolved_by (admin_telegram_id)

- [ ] `escrow_notifications`
  - notification_id (PRIMARY KEY)
  - user_telegram_id
  - transaction_id
  - notification_type (reminder/update/alert)
  - message
  - sent_at
  - read (BOOLEAN)

- [ ] `escrow_auto_release_log`
  - log_id (PRIMARY KEY)
  - transaction_id
  - attempted_at
  - status (success/failed)
  - error_message

## Module 2: escrow_service.py

Core business logic for escrow operations.

### Functions to Implement

- [ ] `async def get_escrow_statistics(escrow_db)`
  - Return dict with:
    - active_transactions (count)
    - total_held (sum of pending amounts)
    - pending_disputes (count)
  - Handle database errors

- [ ] `async def get_old_frozen_transactions(escrow_db, days)`
  - Query transactions frozen for more than X days
  - Return count
  - Used for health checks

- [ ] `async def create_escrow_transaction(escrow_db, buyer_id, seller_id, amount, description)`
  - Create new escrow transaction
  - Validate seller exists and is verified
  - Return transaction object

- [ ] `async def get_transaction_by_id(escrow_db, transaction_id)`
  - Fetch transaction details
  - Return transaction object or None

- [ ] `async def update_transaction_status(escrow_db, transaction_id, new_status)`
  - Update transaction status
  - Log status change
  - Return success boolean

- [ ] `async def freeze_transaction(escrow_db, transaction_id)`
  - Set frozen flag to True
  - Log freeze action
  - Return success boolean

- [ ] `async def unfreeze_transaction(escrow_db, transaction_id)`
  - Set frozen flag to False
  - Log unfreeze action
  - Return success boolean

## Module 3: escrow_automation.py

Background automation tasks.

### Functions to Implement

- [ ] `async def auto_release_task(bot, escrow_db)`
  - Query transactions with status='shipped' and delivery confirmed >24h ago
  - Release funds to seller
  - Update transaction status to 'completed'
  - Notify buyer and seller
  - Log successes and failures

- [ ] `async def auto_refund_task(bot, escrow_db)`
  - Query expired/cancelled transactions
  - Process refunds to buyers
  - Update transaction status to 'refunded'
  - Notify buyer and seller
  - Log refund actions

- [ ] `async def send_reminder_notifications(bot, escrow_db)`
  - Query transactions needing reminders:
    - Pending payment >6 hours
    - Shipped but not confirmed >3 days
    - Disputed >7 days without resolution
  - Send reminder messages via bot
  - Log notifications sent

- [ ] `async def fraud_detection_task(bot, escrow_db)`
  - Detect suspicious patterns:
    - Users with >3 disputes
    - Sellers with <2.0 rating
    - Multiple cancelled orders
  - Flag users/transactions
  - Notify admins
  - Log fraud alerts

- [ ] `async def update_seller_ratings(escrow_db)`
  - Calculate average rating for each seller
  - Update seller_rating in database
  - Consider completed transactions only
  - Log rating updates

- [ ] `async def get_failed_auto_releases(escrow_db)`
  - Query auto_release_log for failed attempts in last 24h
  - Return count
  - Used for health checks

- [ ] `async def complete_pending_releases(escrow_db)`
  - Called during shutdown
  - Process any pending auto-releases immediately
  - Ensure no releases are lost during shutdown
  - Return count of completed releases

## Module 4: escrow_handlers_buyer.py

Buyer command handlers.

### Command Handlers to Implement

- [ ] `async def buy_handler(update, context)`
  - Format: `/buy <seller_id> <amount> <description>`
  - Validate seller exists and is verified
  - Create escrow transaction
  - Generate M-Pesa payment request
  - Show confirmation with inline buttons
  - Store transaction_id in context

- [ ] `async def my_purchases_handler(update, context)`
  - Query all transactions for buyer
  - Display list with status
  - Add inline buttons for actions (track, confirm, dispute)
  - Paginate if many transactions

- [ ] `async def confirm_delivery_handler(update, context)`
  - Format: `/confirm_delivery <transaction_id>`
  - Validate transaction belongs to buyer
  - Update status to 'confirmed'
  - Trigger auto-release (or wait for scheduled task)
  - Prompt for seller rating
  - Notify seller

- [ ] `async def dispute_handler(update, context)`
  - Format: `/dispute <transaction_id> <reason>`
  - Validate transaction belongs to buyer
  - Create dispute record
  - Update transaction status to 'disputed'
  - Freeze transaction
  - Notify seller and admins

- [ ] `async def track_handler(update, context)`
  - Format: `/track <transaction_id>`
  - Fetch transaction details
  - Display current status, timestamps
  - Show tracking information
  - Provide next steps

- [ ] `async def cancel_order_handler(update, context)`
  - Format: `/cancel_order <transaction_id>`
  - Validate transaction is in 'pending' status
  - Update status to 'cancelled'
  - Process refund
  - Notify seller

### Callback Handlers to Implement

- [ ] `async def confirm_escrow_payment_callback(update, context)`
  - Handle button: "Confirm Payment"
  - Process M-Pesa payment
  - Update transaction status
  - Send confirmation message

- [ ] `async def cancel_escrow_payment_callback(update, context)`
  - Handle button: "Cancel Payment"
  - Cancel transaction
  - Send cancellation message

- [ ] `async def confirm_delivery_callback(update, context)`
  - Handle button: "Confirm Delivery"
  - Same as confirm_delivery_handler
  - Show rating buttons

- [ ] `async def dispute_transaction_callback(update, context)`
  - Handle button: "Dispute"
  - Prompt for dispute reason
  - Create dispute

- [ ] `async def rate_seller_callback(update, context)`
  - Handle button: "Rate Seller"
  - Show rating buttons (1-5 stars)
  - Save rating
  - Update seller average rating

## Module 5: escrow_handlers_seller.py

Seller command handlers.

### Command Handlers to Implement

- [ ] `async def register_seller_handler(update, context)`
  - Format: `/register_seller <name> <phone> <mpesa_number>`
  - Validate phone/mpesa format
  - Create seller record
  - Set status to 'pending'
  - Notify admins for verification
  - Provide seller_id

- [ ] `async def my_sales_handler(update, context)`
  - Query all transactions for seller
  - Display list with status
  - Add inline buttons for actions (mark shipped, request release)
  - Show total sales, balance

- [ ] `async def mark_shipped_handler(update, context)`
  - Format: `/mark_shipped <transaction_id> <tracking_number>`
  - Validate transaction belongs to seller
  - Update status to 'shipped'
  - Store tracking number
  - Notify buyer
  - Provide delivery confirmation reminder

- [ ] `async def request_release_handler(update, context)`
  - Format: `/request_release <transaction_id>`
  - Validate transaction status (should be 'shipped' + confirmed)
  - Send notification to buyer
  - Remind buyer to confirm delivery
  - Cannot force release (admin only)

- [ ] `async def seller_stats_handler(update, context)`
  - Display seller statistics:
    - Total sales
    - Average rating
    - Total transactions
    - Pending releases
    - Current balance
    - Dispute count
  - Show verification status

- [ ] `async def withdraw_handler(update, context)`
  - Format: `/withdraw <amount>`
  - Check seller balance
  - Validate amount <= balance
  - Process withdrawal to mpesa_number
  - Update balance
  - Send confirmation

- [ ] `async def seller_help_handler(update, context)`
  - Display comprehensive seller guide
  - Explain escrow process
  - List available commands
  - Provide best practices
  - Show support contact

## Module 6: escrow_handlers_admin.py

Admin command handlers.

### Command Handlers to Implement

- [ ] `async def verify_seller_handler(update, context)`
  - Format: `/verify_seller <seller_id>`
  - Check admin permissions
  - Update seller status to 'verified'
  - Notify seller
  - Log verification

- [ ] `async def suspend_seller_handler(update, context)`
  - Format: `/suspend_seller <seller_id> <reason>`
  - Check admin permissions
  - Update seller status to 'suspended'
  - Freeze all seller's active transactions
  - Notify seller
  - Log suspension

- [ ] `async def resolve_dispute_handler(update, context)`
  - Format: `/resolve_dispute <dispute_id> <resolution> <action>`
  - action: refund/release/partial
  - Check admin permissions
  - Update dispute status to 'resolved'
  - Execute action (refund or release)
  - Notify buyer and seller
  - Log resolution

- [ ] `async def escrow_dashboard_handler(update, context)`
  - Check admin permissions
  - Display comprehensive dashboard:
    - Active transactions
    - Total held amount
    - Pending disputes
    - Pending seller verifications
    - Recent transactions
    - System health metrics

- [ ] `async def disputed_transactions_handler(update, context)`
  - Check admin permissions
  - List all disputed transactions
  - Show dispute details
  - Provide resolution buttons
  - Paginate results

- [ ] `async def suspicious_users_handler(update, context)`
  - Check admin permissions
  - Query flagged users from fraud detection
  - Display suspicious activity
  - Provide action buttons (freeze, suspend, investigate)

- [ ] `async def freeze_transaction_handler(update, context)`
  - Format: `/freeze_transaction <transaction_id> <reason>`
  - Check admin permissions
  - Set frozen flag
  - Notify buyer and seller
  - Log freeze action

- [ ] `async def manual_refund_handler(update, context)`
  - Format: `/manual_refund <transaction_id> <amount>`
  - Check admin permissions
  - Process refund to buyer
  - Update transaction status
  - Notify buyer
  - Log refund

- [ ] `async def manual_release_handler(update, context)`
  - Format: `/manual_release <transaction_id> <amount>`
  - Check admin permissions
  - Release funds to seller
  - Update transaction status
  - Notify seller
  - Log release

## Additional Considerations

### Security

- [ ] Implement admin permission checks
  - Store admin telegram_ids in config or database
  - Validate user is admin before executing admin commands

- [ ] Input validation
  - Sanitize all user inputs
  - Validate amounts (positive, reasonable limits)
  - Validate phone numbers (Kenyan format)
  - Validate transaction IDs (exist, belong to user)

- [ ] Rate limiting
  - Prevent spam of commands
  - Limit transactions per user per day
  - Detect suspicious patterns

### Error Handling

- [ ] Database connection errors
  - Retry logic
  - Fallback messages

- [ ] M-Pesa API errors
  - Handle payment failures
  - Refund on errors
  - Log all API calls

- [ ] Transaction state errors
  - Validate state transitions
  - Prevent invalid operations

### Logging

- [ ] Transaction logs
  - Log all state changes
  - Log all payments/refunds
  - Timestamp all actions

- [ ] User action logs
  - Log buyer/seller actions
  - Log admin actions
  - Audit trail

- [ ] Error logs
  - Log all exceptions
  - Include context (user_id, transaction_id)

### Testing

- [ ] Unit tests for each function
- [ ] Integration tests for workflows
- [ ] Test escrow transaction lifecycle:
  - Create → Pay → Ship → Confirm → Release
- [ ] Test dispute workflow:
  - Create → Dispute → Resolve → Refund/Release
- [ ] Test admin functions
- [ ] Test automation tasks
- [ ] Test graceful degradation (missing modules)

## Deployment Checklist

- [ ] Install APScheduler
- [ ] Create database tables
- [ ] Configure admin telegram_ids
- [ ] Set escrow transaction limits
- [ ] Test in sandbox mode
- [ ] Monitor logs during initial rollout
- [ ] Set up alerting for:
  - High dispute counts
  - Auto-release failures
  - Old frozen transactions
  - Fraud detection alerts

## Success Criteria

- [ ] Bot starts with escrow enabled
- [ ] Buyers can initiate purchases
- [ ] Sellers can mark items shipped
- [ ] Auto-release works correctly
- [ ] Disputes can be opened and resolved
- [ ] Admin dashboard shows correct data
- [ ] Health checks report no issues
- [ ] Graceful shutdown completes pending releases
- [ ] No data loss during crashes
- [ ] All commands have proper error handling

## Documentation

- [ ] User guide for buyers
- [ ] User guide for sellers
- [ ] Admin manual
- [ ] API documentation
- [ ] Database schema documentation
- [ ] Deployment guide
- [ ] Troubleshooting guide

---

**Note**: This checklist assumes you have the M-Pesa integration already working from the existing payment bot. The escrow system builds on top of that infrastructure.

**Estimated Implementation Time**: 3-5 days for core functionality, 1-2 weeks for complete system with testing and documentation.
