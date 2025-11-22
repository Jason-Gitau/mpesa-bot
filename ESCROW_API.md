# Escrow System API Documentation

## Table of Contents
- [Overview](#overview)
- [Database Schema](#database-schema)
- [API Endpoints](#api-endpoints)
- [Transaction State Machine](#transaction-state-machine)
- [Integration Guide](#integration-guide)
- [Webhook Setup](#webhook-setup)
- [Testing Guide](#testing-guide)
- [Error Handling](#error-handling)
- [Security](#security)

---

## Overview

### Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Telegram  │◄────►│   Bot Core   │◄────►│   M-Pesa    │
│    User     │      │   (Python)   │      │  Daraja API │
└─────────────┘      └──────┬───────┘      └─────────────┘
                            │
                    ┌───────▼────────┐
                    │  Escrow Engine │
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
                    │   PostgreSQL   │
                    │   (Supabase)   │
                    └────────────────┘
```

### Technology Stack

- **Backend:** Python 3.11+
- **Framework:** python-telegram-bot, FastAPI
- **Database:** PostgreSQL (via Supabase)
- **Payment:** M-Pesa Daraja API
- **ORM:** AsyncPG
- **Async:** asyncio, aiohttp

### Core Components

1. **Escrow Manager** - Transaction lifecycle management
2. **Payment Processor** - M-Pesa integration
3. **Dispute Handler** - Conflict resolution
4. **Notification Service** - User alerts
5. **Admin Dashboard** - Manual intervention

---

## Database Schema

### ER Diagram

```
┌────────────────────┐
│       users        │
├────────────────────┤
│ id (PK)            │◄──┐
│ chat_id (UNIQUE)   │   │
│ phone_number       │   │
│ is_verified        │   │
│ verification_date  │   │
│ rating             │   │
│ total_sales        │   │
│ total_purchases    │   │
│ created_at         │   │
│ last_active        │   │
└────────────────────┘   │
                         │
                         │ seller_id (FK)
                         │
┌────────────────────┐   │
│   escrow_txns      │   │
├────────────────────┤   │
│ id (PK)            │   │
│ escrow_id (UNIQUE) │   │
│ buyer_chat_id (FK) │───┘
│ seller_id (FK)     │───┐
│ amount             │   │
│ escrow_fee         │   │
│ status             │   │
│ item_description   │   │
│ created_at         │   │
│ paid_at            │   │
│ shipped_at         │   │
│ delivered_at       │   │
│ completed_at       │   │
│ refunded_at        │   │
│ ship_by_deadline   │   │
│ auto_release_date  │   │
│ tracking_number    │   │
│ mpesa_receipt      │   │
│ mpesa_txn_id       │   │
└────────────────────┘   │
          │              │
          │              │
          ▼              │
┌────────────────────┐   │
│     disputes       │   │
├────────────────────┤   │
│ id (PK)            │   │
│ escrow_id (FK)     │   │
│ filed_by (FK)      │   │
│ reason             │   │
│ status             │   │
│ resolution         │   │
│ admin_id (FK)      │   │
│ filed_at           │   │
│ resolved_at        │   │
└────────────────────┘   │
          │              │
          │              │
          ▼              │
┌────────────────────┐   │
│  dispute_evidence  │   │
├────────────────────┤   │
│ id (PK)            │   │
│ dispute_id (FK)    │   │
│ uploaded_by (FK)   │   │
│ evidence_type      │   │
│ file_url           │   │
│ description        │   │
│ uploaded_at        │   │
└────────────────────┘   │
                         │
┌────────────────────┐   │
│      ratings       │   │
├────────────────────┤   │
│ id (PK)            │   │
│ escrow_id (FK)     │   │
│ rater_id (FK)      │   │
│ rated_user_id (FK) │───┘
│ stars (1-5)        │
│ comment            │
│ created_at         │
└────────────────────┘

┌────────────────────┐
│   notifications    │
├────────────────────┤
│ id (PK)            │
│ user_chat_id (FK)  │
│ type               │
│ message            │
│ escrow_id (FK)     │
│ sent_at            │
│ read_at            │
└────────────────────┘
```

### Table Definitions

#### `users` Table

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT UNIQUE NOT NULL,
    phone_number VARCHAR(15),
    is_verified BOOLEAN DEFAULT FALSE,
    verification_date TIMESTAMP,
    rating DECIMAL(3, 2) DEFAULT 5.00,
    total_sales INTEGER DEFAULT 0,
    total_purchases INTEGER DEFAULT 0,
    total_amount_sold DECIMAL(12, 2) DEFAULT 0.00,
    total_amount_bought DECIMAL(12, 2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_suspended BOOLEAN DEFAULT FALSE,
    suspension_reason TEXT,

    CONSTRAINT positive_rating CHECK (rating >= 0 AND rating <= 5),
    CONSTRAINT positive_totals CHECK (
        total_sales >= 0 AND
        total_purchases >= 0 AND
        total_amount_sold >= 0 AND
        total_amount_bought >= 0
    )
);

CREATE INDEX idx_users_chat_id ON users(chat_id);
CREATE INDEX idx_users_phone ON users(phone_number);
CREATE INDEX idx_users_verified ON users(is_verified);
```

#### `escrow_transactions` Table

```sql
CREATE TABLE escrow_transactions (
    id SERIAL PRIMARY KEY,
    escrow_id VARCHAR(50) UNIQUE NOT NULL,
    buyer_chat_id BIGINT NOT NULL,
    seller_id BIGINT NOT NULL,

    -- Financial details
    amount DECIMAL(10, 2) NOT NULL,
    escrow_fee DECIMAL(10, 2) NOT NULL,
    total_paid DECIMAL(10, 2) NOT NULL,

    -- Transaction status
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- Statuses: pending, paid, shipped, delivered, completed, disputed,
    --           refunded, cancelled

    -- Item details
    item_description TEXT NOT NULL,
    item_category VARCHAR(50),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    paid_at TIMESTAMP,
    shipped_at TIMESTAMP,
    delivered_at TIMESTAMP,
    completed_at TIMESTAMP,
    refunded_at TIMESTAMP,
    cancelled_at TIMESTAMP,

    -- Deadlines
    ship_by_deadline TIMESTAMP,
    auto_release_date TIMESTAMP,

    -- Shipping details
    tracking_number VARCHAR(100),
    shipping_method VARCHAR(50),

    -- M-Pesa details
    mpesa_receipt VARCHAR(100),
    mpesa_transaction_id VARCHAR(100),
    checkout_request_id VARCHAR(100) UNIQUE,

    -- Additional metadata
    buyer_notes TEXT,
    seller_notes TEXT,
    admin_notes TEXT,

    CONSTRAINT positive_amounts CHECK (
        amount > 0 AND
        escrow_fee >= 0 AND
        total_paid > 0
    ),
    CONSTRAINT valid_status CHECK (status IN (
        'pending', 'paid', 'shipped', 'delivered',
        'completed', 'disputed', 'refunded', 'cancelled'
    )),

    FOREIGN KEY (buyer_chat_id) REFERENCES users(chat_id),
    FOREIGN KEY (seller_id) REFERENCES users(chat_id)
);

CREATE INDEX idx_escrow_id ON escrow_transactions(escrow_id);
CREATE INDEX idx_buyer_id ON escrow_transactions(buyer_chat_id);
CREATE INDEX idx_seller_id ON escrow_transactions(seller_id);
CREATE INDEX idx_status ON escrow_transactions(status);
CREATE INDEX idx_created_at ON escrow_transactions(created_at DESC);
CREATE INDEX idx_checkout_request ON escrow_transactions(checkout_request_id);
```

#### `disputes` Table

```sql
CREATE TABLE disputes (
    id SERIAL PRIMARY KEY,
    dispute_id VARCHAR(50) UNIQUE NOT NULL,
    escrow_id VARCHAR(50) NOT NULL,
    filed_by BIGINT NOT NULL,

    -- Dispute details
    reason TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,
    -- Categories: not_received, not_as_described, damaged,
    --             defective, other

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    -- Statuses: open, under_review, resolved, closed

    -- Resolution
    resolution TEXT,
    resolved_in_favor_of VARCHAR(10),
    -- Values: buyer, seller, split

    refund_amount DECIMAL(10, 2) DEFAULT 0.00,

    -- Admin handling
    admin_id BIGINT,
    priority VARCHAR(10) DEFAULT 'normal',
    -- Priorities: low, normal, high, urgent

    -- Timestamps
    filed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP,
    resolved_at TIMESTAMP,
    closed_at TIMESTAMP,

    -- Deadlines
    seller_response_deadline TIMESTAMP,

    CONSTRAINT valid_status CHECK (status IN (
        'open', 'under_review', 'resolved', 'closed'
    )),
    CONSTRAINT valid_resolution CHECK (
        resolved_in_favor_of IS NULL OR
        resolved_in_favor_of IN ('buyer', 'seller', 'split')
    ),

    FOREIGN KEY (escrow_id) REFERENCES escrow_transactions(escrow_id),
    FOREIGN KEY (filed_by) REFERENCES users(chat_id),
    FOREIGN KEY (admin_id) REFERENCES users(chat_id)
);

CREATE INDEX idx_dispute_id ON disputes(dispute_id);
CREATE INDEX idx_dispute_escrow ON disputes(escrow_id);
CREATE INDEX idx_dispute_status ON disputes(status);
CREATE INDEX idx_dispute_filed_at ON disputes(filed_at DESC);
```

#### `dispute_evidence` Table

```sql
CREATE TABLE dispute_evidence (
    id SERIAL PRIMARY KEY,
    dispute_id VARCHAR(50) NOT NULL,
    uploaded_by BIGINT NOT NULL,

    evidence_type VARCHAR(20) NOT NULL,
    -- Types: photo, video, document, screenshot

    file_url TEXT NOT NULL,
    file_name VARCHAR(255),
    file_size INTEGER,

    description TEXT,

    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_evidence_type CHECK (evidence_type IN (
        'photo', 'video', 'document', 'screenshot', 'other'
    )),

    FOREIGN KEY (dispute_id) REFERENCES disputes(dispute_id),
    FOREIGN KEY (uploaded_by) REFERENCES users(chat_id)
);

CREATE INDEX idx_evidence_dispute ON dispute_evidence(dispute_id);
```

#### `ratings` Table

```sql
CREATE TABLE ratings (
    id SERIAL PRIMARY KEY,
    escrow_id VARCHAR(50) NOT NULL,
    rater_id BIGINT NOT NULL,
    rated_user_id BIGINT NOT NULL,

    stars INTEGER NOT NULL,
    comment TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_stars CHECK (stars >= 1 AND stars <= 5),
    CONSTRAINT different_users CHECK (rater_id != rated_user_id),

    FOREIGN KEY (escrow_id) REFERENCES escrow_transactions(escrow_id),
    FOREIGN KEY (rater_id) REFERENCES users(chat_id),
    FOREIGN KEY (rated_user_id) REFERENCES users(chat_id),

    UNIQUE(escrow_id, rater_id)
);

CREATE INDEX idx_ratings_rated_user ON ratings(rated_user_id);
CREATE INDEX idx_ratings_escrow ON ratings(escrow_id);
```

#### `notifications` Table

```sql
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_chat_id BIGINT NOT NULL,

    type VARCHAR(30) NOT NULL,
    -- Types: payment_received, order_shipped, delivery_confirmed,
    --        dispute_filed, dispute_resolved, payment_released, etc.

    title VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,

    escrow_id VARCHAR(50),

    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP,

    priority VARCHAR(10) DEFAULT 'normal',

    FOREIGN KEY (user_chat_id) REFERENCES users(chat_id),
    FOREIGN KEY (escrow_id) REFERENCES escrow_transactions(escrow_id)
);

CREATE INDEX idx_notifications_user ON notifications(user_chat_id);
CREATE INDEX idx_notifications_unread ON notifications(user_chat_id, read_at)
    WHERE read_at IS NULL;
```

---

## API Endpoints

### Escrow Transaction Endpoints

#### Create Escrow Transaction

**Telegram Command:**
```
/buy <item_description> <amount> <seller_username>
```

**Internal API:**
```python
async def create_escrow_transaction(
    buyer_chat_id: int,
    seller_username: str,
    item_description: str,
    amount: float,
    category: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new escrow transaction.

    Args:
        buyer_chat_id: Telegram chat ID of buyer
        seller_username: Seller's Telegram username
        item_description: Description of item/service
        amount: Transaction amount in KES
        category: Optional item category

    Returns:
        {
            "escrow_id": "ESC-20251122-00123",
            "amount": 50000.00,
            "escrow_fee": 500.00,
            "total_paid": 50500.00,
            "seller": {
                "username": "@johnseller",
                "is_verified": True,
                "rating": 4.8,
                "total_sales": 156
            },
            "ship_by_deadline": "2025-11-24T18:00:00",
            "status": "pending"
        }

    Raises:
        ValueError: If amount is invalid
        UserNotFoundError: If seller doesn't exist
        SellerSuspendedError: If seller is suspended
    """
```

**SQL:**
```sql
-- Generate escrow ID
SELECT CONCAT('ESC-', TO_CHAR(NOW(), 'YYYYMMDD'), '-',
              LPAD(NEXTVAL('escrow_seq')::TEXT, 5, '0'));

-- Insert transaction
INSERT INTO escrow_transactions (
    escrow_id, buyer_chat_id, seller_id, amount,
    escrow_fee, total_paid, item_description,
    item_category, ship_by_deadline, status
) VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8,
    NOW() + INTERVAL '2 days', 'pending'
) RETURNING *;
```

#### Process Payment

**Internal API:**
```python
async def process_escrow_payment(
    escrow_id: str,
    phone_number: str
) -> Dict[str, Any]:
    """
    Initiate M-Pesa STK Push for escrow payment.

    Args:
        escrow_id: Unique escrow transaction ID
        phone_number: Buyer's M-Pesa phone number

    Returns:
        {
            "checkout_request_id": "ws_CO_12345...",
            "merchant_request_id": "29115-34620561-1",
            "response_code": "0",
            "response_description": "Success. Request accepted",
            "customer_message": "Please enter PIN"
        }
    """
```

**M-Pesa STK Push Request:**
```json
{
    "BusinessShortCode": "174379",
    "Password": "base64_encoded_password",
    "Timestamp": "20251122143045",
    "TransactionType": "CustomerPayBillOnline",
    "Amount": "50500",
    "PartyA": "254712345678",
    "PartyB": "174379",
    "PhoneNumber": "254712345678",
    "CallBackURL": "https://yourdomain.com/mpesa-callback",
    "AccountReference": "ESC-20251122-00123",
    "TransactionDesc": "Escrow payment for iPhone"
}
```

#### M-Pesa Callback Handler

**FastAPI Endpoint:**
```python
@app.post('/mpesa-callback')
async def mpesa_callback(request: Request):
    """
    Handle M-Pesa payment callback.

    Processes payment confirmation and updates escrow status.
    """
    data = await request.json()

    result_code = data['Body']['stkCallback']['ResultCode']
    checkout_request_id = data['Body']['stkCallback']['CheckoutRequestID']

    if result_code == 0:  # Success
        callback_metadata = data['Body']['stkCallback']['CallbackMetadata']['Item']

        amount = next(item['Value'] for item in callback_metadata
                     if item['Name'] == 'Amount')
        mpesa_receipt = next(item['Value'] for item in callback_metadata
                            if item['Name'] == 'MpesaReceiptNumber')
        transaction_date = next(item['Value'] for item in callback_metadata
                               if item['Name'] == 'TransactionDate')

        await update_escrow_payment_status(
            checkout_request_id=checkout_request_id,
            status='paid',
            mpesa_receipt=mpesa_receipt,
            paid_at=transaction_date
        )

        # Notify buyer and seller
        await notify_payment_success(checkout_request_id)

    else:  # Failed
        await update_escrow_payment_status(
            checkout_request_id=checkout_request_id,
            status='failed'
        )

        await notify_payment_failed(checkout_request_id)

    return {"ResultCode": 0, "ResultDesc": "Accepted"}
```

**SQL Update:**
```sql
UPDATE escrow_transactions
SET status = 'paid',
    mpesa_receipt = $1,
    mpesa_transaction_id = $2,
    paid_at = $3,
    auto_release_date = NOW() + INTERVAL '7 days'
WHERE checkout_request_id = $4
RETURNING *;

-- Notify seller
INSERT INTO notifications (user_chat_id, type, title, message, escrow_id)
VALUES (
    $1,
    'payment_received',
    'New Order Received!',
    'Payment of KES {amount} held in escrow. Ship by {deadline}.',
    $2
);
```

#### Mark as Shipped

**Telegram Command:**
```
/mark_shipped <escrow_id> <tracking_number>
```

**Internal API:**
```python
async def mark_order_shipped(
    escrow_id: str,
    seller_chat_id: int,
    tracking_number: Optional[str] = None,
    shipping_method: Optional[str] = None
) -> Dict[str, Any]:
    """
    Mark escrow order as shipped.

    Args:
        escrow_id: Unique escrow transaction ID
        seller_chat_id: Seller's chat ID (for verification)
        tracking_number: Optional tracking number
        shipping_method: Optional shipping method

    Returns:
        {
            "escrow_id": "ESC-20251122-00123",
            "status": "shipped",
            "shipped_at": "2025-11-22T14:30:45",
            "auto_release_date": "2025-11-29T14:30:45",
            "tracking_number": "EMS-KE-1234567"
        }

    Raises:
        PermissionError: If caller is not the seller
        InvalidStatusError: If order not in 'paid' status
    """
```

**SQL:**
```sql
UPDATE escrow_transactions
SET status = 'shipped',
    shipped_at = NOW(),
    tracking_number = $1,
    shipping_method = $2,
    auto_release_date = NOW() + INTERVAL '7 days'
WHERE escrow_id = $3
  AND seller_id = $4
  AND status = 'paid'
RETURNING *;
```

#### Confirm Delivery

**Telegram Command:**
```
/confirm_delivery <escrow_id>
```

**Internal API:**
```python
async def confirm_delivery(
    escrow_id: str,
    buyer_chat_id: int
) -> Dict[str, Any]:
    """
    Buyer confirms successful delivery.

    Triggers payment release to seller.

    Args:
        escrow_id: Unique escrow transaction ID
        buyer_chat_id: Buyer's chat ID (for verification)

    Returns:
        {
            "escrow_id": "ESC-20251122-00123",
            "status": "delivered",
            "delivered_at": "2025-11-25T16:20:30",
            "payment_release_scheduled": "2025-11-26T16:20:30"
        }
    """
```

**SQL:**
```sql
UPDATE escrow_transactions
SET status = 'delivered',
    delivered_at = NOW()
WHERE escrow_id = $1
  AND buyer_chat_id = $2
  AND status = 'shipped'
RETURNING *;

-- Schedule payment release (processed by background job)
-- Payment released within 24 hours
```

#### Release Payment to Seller

**Background Job (triggered by delivery confirmation or auto-release):**
```python
async def release_payment_to_seller(escrow_id: str) -> Dict[str, Any]:
    """
    Release escrowed funds to seller via M-Pesa B2C.

    Args:
        escrow_id: Unique escrow transaction ID

    Returns:
        {
            "escrow_id": "ESC-20251122-00123",
            "amount": 50000.00,
            "escrow_fee": 500.00,
            "net_payment": 49500.00,
            "mpesa_transaction_id": "MPX1234567",
            "status": "completed"
        }
    """
```

**M-Pesa B2C Request:**
```json
{
    "InitiatorName": "apitest",
    "SecurityCredential": "encrypted_password",
    "CommandID": "BusinessPayment",
    "Amount": "49500",
    "PartyA": "174379",
    "PartyB": "254712345678",
    "Remarks": "Payment release - ESC-20251122-00123",
    "QueueTimeOutURL": "https://yourdomain.com/b2c-timeout",
    "ResultURL": "https://yourdomain.com/b2c-callback",
    "Occasion": "Escrow Payment Release"
}
```

**SQL:**
```sql
-- Update transaction
UPDATE escrow_transactions
SET status = 'completed',
    completed_at = NOW()
WHERE escrow_id = $1
RETURNING *;

-- Update seller stats
UPDATE users
SET total_sales = total_sales + 1,
    total_amount_sold = total_amount_sold + $1,
    last_active = NOW()
WHERE chat_id = $2;

-- Update buyer stats
UPDATE users
SET total_purchases = total_purchases + 1,
    total_amount_bought = total_amount_bought + $1,
    last_active = NOW()
WHERE chat_id = $3;
```

### Dispute Endpoints

#### File Dispute

**Telegram Command:**
```
/dispute <escrow_id> <reason>
```

**Internal API:**
```python
async def file_dispute(
    escrow_id: str,
    filed_by: int,
    reason: str,
    category: str
) -> Dict[str, Any]:
    """
    File a dispute for an escrow transaction.

    Args:
        escrow_id: Unique escrow transaction ID
        filed_by: Chat ID of user filing dispute
        reason: Detailed reason for dispute
        category: Dispute category

    Returns:
        {
            "dispute_id": "DIS-20251122-00045",
            "escrow_id": "ESC-20251122-00123",
            "status": "open",
            "seller_response_deadline": "2025-11-24T14:30:00"
        }
    """
```

**SQL:**
```sql
-- Create dispute
INSERT INTO disputes (
    dispute_id, escrow_id, filed_by, reason,
    category, status, seller_response_deadline
) VALUES (
    CONCAT('DIS-', TO_CHAR(NOW(), 'YYYYMMDD'), '-',
           LPAD(NEXTVAL('dispute_seq')::TEXT, 5, '0')),
    $1, $2, $3, $4, 'open',
    NOW() + INTERVAL '48 hours'
) RETURNING *;

-- Update escrow status
UPDATE escrow_transactions
SET status = 'disputed'
WHERE escrow_id = $1;

-- Notify seller
INSERT INTO notifications (user_chat_id, type, title, message, escrow_id)
VALUES (
    $1,
    'dispute_filed',
    'Dispute Filed on Your Order',
    'Buyer filed dispute. You have 48 hours to respond.',
    $2
);
```

#### Upload Dispute Evidence

**Telegram Command:**
```
/attach_evidence <escrow_id>
[Then send photo/video/document]
```

**Internal API:**
```python
async def upload_dispute_evidence(
    dispute_id: str,
    uploaded_by: int,
    file_url: str,
    evidence_type: str,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Upload evidence for a dispute.

    Args:
        dispute_id: Unique dispute ID
        uploaded_by: Chat ID of uploader
        file_url: URL of uploaded file
        evidence_type: Type of evidence
        description: Optional description

    Returns:
        {
            "evidence_id": 123,
            "dispute_id": "DIS-20251122-00045",
            "file_url": "https://...",
            "uploaded_at": "2025-11-22T14:30:00"
        }
    """
```

#### Resolve Dispute

**Admin Internal API:**
```python
async def resolve_dispute(
    dispute_id: str,
    admin_id: int,
    resolved_in_favor_of: str,  # 'buyer', 'seller', or 'split'
    resolution: str,
    refund_amount: Optional[float] = None
) -> Dict[str, Any]:
    """
    Resolve a dispute (admin only).

    Args:
        dispute_id: Unique dispute ID
        admin_id: Chat ID of admin resolving
        resolved_in_favor_of: Winner of dispute
        resolution: Explanation of decision
        refund_amount: Amount to refund (if applicable)

    Returns:
        {
            "dispute_id": "DIS-20251122-00045",
            "escrow_id": "ESC-20251122-00123",
            "status": "resolved",
            "resolved_in_favor_of": "buyer",
            "refund_amount": 50000.00
        }
    """
```

**SQL:**
```sql
-- Update dispute
UPDATE disputes
SET status = 'resolved',
    resolved_in_favor_of = $1,
    resolution = $2,
    refund_amount = $3,
    admin_id = $4,
    resolved_at = NOW()
WHERE dispute_id = $5
RETURNING *;

-- If buyer wins, process refund
-- If seller wins, release payment
-- If split, partial refund + partial release
```

---

## Transaction State Machine

### State Diagram

```
                    ┌──────────┐
                    │ PENDING  │ (Created, awaiting payment)
                    └─────┬────┘
                          │
                    [Buyer pays]
                          │
                          ▼
                    ┌──────────┐
              ┌─────┤   PAID   │ (Payment held in escrow)
              │     └─────┬────┘
              │           │
    [Deadline passes]  [Seller ships]
    [No shipping]         │
              │           ▼
              │     ┌──────────┐
              │     │ SHIPPED  │ (Item in transit)
              │     └─────┬────┘
              │           │
              │     ┌─────┴──────┐
              │     │            │
              │  [Buyer      [7 days pass]
              │   confirms]   [No dispute]
              │     │            │
              │     ▼            ▼
              │  ┌──────────┐   │
              │  │DELIVERED │───┘
              │  └─────┬────┘
              │        │
              │  [24hrs later]
              │        │
              │        ▼
              │  ┌──────────┐
              └─►│COMPLETED │ (Payment released to seller)
                 └──────────┘

                     OR

                    ┌──────────┐
             ┌──────┤   PAID   │
             │      └─────┬────┘
             │            │
        [Buyer         [Buyer files
         cancels]       dispute]
             │            │
             ▼            ▼
        ┌──────────┐  ┌──────────┐
        │CANCELLED │  │ DISPUTED │
        └─────┬────┘  └─────┬────┘
              │             │
              │       [Admin resolves]
              │             │
              │       ┌─────┴──────┐
              │       │            │
              │   [Buyer wins] [Seller wins]
              │       │            │
              ▼       ▼            ▼
        ┌──────────┐           [Continue to
        │ REFUNDED │            COMPLETED]
        └──────────┘
```

### Valid State Transitions

```python
STATE_TRANSITIONS = {
    'pending': ['paid', 'cancelled'],
    'paid': ['shipped', 'cancelled', 'disputed', 'refunded'],
    'shipped': ['delivered', 'disputed'],
    'delivered': ['completed', 'disputed'],
    'disputed': ['refunded', 'completed'],  # Based on resolution
    'completed': [],  # Final state
    'refunded': [],   # Final state
    'cancelled': []   # Final state
}
```

### State Validation

```python
async def validate_state_transition(
    current_status: str,
    new_status: str,
    escrow_id: str
) -> bool:
    """
    Validate if a state transition is allowed.

    Args:
        current_status: Current transaction status
        new_status: Desired new status
        escrow_id: Transaction ID (for logging)

    Returns:
        True if transition is valid, False otherwise

    Raises:
        InvalidStateTransitionError: If transition not allowed
    """
    if new_status not in STATE_TRANSITIONS.get(current_status, []):
        raise InvalidStateTransitionError(
            f"Cannot transition from {current_status} to {new_status} "
            f"for escrow {escrow_id}"
        )
    return True
```

---

## Integration Guide

### Setup

**1. Install Dependencies:**
```bash
pip install python-telegram-bot fastapi uvicorn asyncpg python-dotenv
```

**2. Configure Environment:**
```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token

# M-Pesa
MPESA_CONSUMER_KEY=your_consumer_key
MPESA_CONSUMER_SECRET=your_consumer_secret
MPESA_SHORTCODE=174379
MPESA_PASSKEY=your_passkey

# Database
SUPABASE_DB_URL=postgresql://user:pass@host:5432/dbname

# Escrow Settings
ESCROW_FEE_PERCENT=1.0
VERIFIED_SELLER_FEE_PERCENT=1.0
UNVERIFIED_SELLER_FEE_PERCENT=2.0
AUTO_RELEASE_DAYS=7
SHIP_DEADLINE_DAYS=2
```

**3. Initialize Database:**
```bash
python -c "from database import Database; import asyncio; asyncio.run(Database().init_database())"
```

### Basic Integration Example

```python
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from escrow_manager import EscrowManager
from mpesa_service import MpesaService
from database import Database

# Initialize services
db = Database()
mpesa = MpesaService()
escrow = EscrowManager(db, mpesa)

async def buy_command(update: Update, context: CallbackContext):
    """Handle /buy command."""
    try:
        # Parse command: /buy <item> <amount> <seller>
        args = context.args
        item_desc = ' '.join(args[:-2])
        amount = float(args[-2])
        seller_username = args[-1]

        buyer_chat_id = update.message.chat_id

        # Create escrow transaction
        transaction = await escrow.create_transaction(
            buyer_chat_id=buyer_chat_id,
            seller_username=seller_username,
            item_description=item_desc,
            amount=amount
        )

        # Send confirmation with inline keyboard
        await update.message.reply_text(
            f"Order Summary:\n"
            f"Item: {item_desc}\n"
            f"Price: KES {amount:,.2f}\n"
            f"Escrow Fee: KES {transaction['escrow_fee']:,.2f}\n"
            f"Total: KES {transaction['total_paid']:,.2f}\n\n"
            f"Seller: {seller_username} "
            f"({'✓ Verified' if transaction['seller']['is_verified'] else 'Unverified'})\n"
            f"Rating: {transaction['seller']['rating']}⭐\n\n"
            f"Escrow ID: {transaction['escrow_id']}",
            reply_markup=get_payment_keyboard(transaction['escrow_id'])
        )

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def confirm_payment_callback(update: Update, context: CallbackContext):
    """Handle payment confirmation button press."""
    query = update.callback_query
    escrow_id = query.data.split(':')[1]

    # Get transaction details
    transaction = await escrow.get_transaction(escrow_id)
    buyer_chat_id = query.from_user.id

    # Get buyer's phone number
    user = await db.get_user_by_chat_id(buyer_chat_id)

    if not user or not user['phone_number']:
        await query.answer("Please set your phone number first using /set_phone")
        return

    # Initiate M-Pesa payment
    result = await mpesa.initiate_stk_push(
        phone_number=user['phone_number'],
        amount=transaction['total_paid'],
        account_reference=escrow_id,
        transaction_desc=f"Escrow payment: {transaction['item_description'][:50]}"
    )

    if result['ResponseCode'] == '0':
        # Update transaction with checkout request ID
        await escrow.update_checkout_request(
            escrow_id=escrow_id,
            checkout_request_id=result['CheckoutRequestID']
        )

        await query.edit_message_text(
            f"Payment request sent to {user['phone_number']}\n"
            f"Please enter your M-Pesa PIN to complete payment.\n\n"
            f"Escrow ID: {escrow_id}"
        )
    else:
        await query.answer(f"Payment failed: {result.get('errorMessage', 'Unknown error')}")

# Add handlers
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler('buy', buy_command))
app.add_handler(CallbackQueryHandler(confirm_payment_callback, pattern='^pay:'))
```

---

## Webhook Setup

### M-Pesa Callback Endpoint

**FastAPI Implementation:**

```python
from fastapi import FastAPI, Request, HTTPException
from datetime import datetime
import asyncio

app = FastAPI()

@app.post('/mpesa-callback')
async def mpesa_callback(request: Request):
    """
    Handle M-Pesa STK Push callback.

    Called by Safaricom when payment completes.
    """
    try:
        data = await request.json()

        # Extract callback data
        stk_callback = data['Body']['stkCallback']
        result_code = stk_callback['ResultCode']
        result_desc = stk_callback['ResultDesc']
        checkout_request_id = stk_callback['CheckoutRequestID']

        if result_code == 0:  # Success
            # Extract payment details
            metadata = stk_callback['CallbackMetadata']['Item']

            amount = next(
                (item['Value'] for item in metadata if item['Name'] == 'Amount'),
                None
            )
            mpesa_receipt = next(
                (item['Value'] for item in metadata if item['Name'] == 'MpesaReceiptNumber'),
                None
            )
            transaction_date_str = next(
                (str(item['Value']) for item in metadata if item['Name'] == 'TransactionDate'),
                None
            )
            phone_number = next(
                (str(item['Value']) for item in metadata if item['Name'] == 'PhoneNumber'),
                None
            )

            # Parse transaction date (format: 20251122143045)
            transaction_date = datetime.strptime(transaction_date_str, '%Y%m%d%H%M%S')

            # Update escrow transaction
            await escrow.confirm_payment(
                checkout_request_id=checkout_request_id,
                mpesa_receipt=mpesa_receipt,
                amount=amount,
                paid_at=transaction_date
            )

            # Send notifications
            transaction = await escrow.get_transaction_by_checkout(checkout_request_id)
            await notify_payment_success(transaction)

        else:  # Payment failed
            await escrow.mark_payment_failed(
                checkout_request_id=checkout_request_id,
                reason=result_desc
            )

            transaction = await escrow.get_transaction_by_checkout(checkout_request_id)
            await notify_payment_failed(transaction)

        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    except Exception as e:
        logger.error(f"Callback processing error: {e}")
        return {"ResultCode": 1, "ResultDesc": "Rejected"}


@app.post('/b2c-callback')
async def b2c_callback(request: Request):
    """
    Handle M-Pesa B2C callback (payment release to seller).

    Called by Safaricom when B2C payment completes.
    """
    try:
        data = await request.json()

        result = data['Result']
        result_code = result['ResultCode']
        result_desc = result['ResultDesc']

        # Extract conversation ID (contains escrow_id)
        conversation_id = result['ConversationID']

        if result_code == 0:  # Success
            result_parameters = result['ResultParameters']['ResultParameter']

            transaction_id = next(
                (item['Value'] for item in result_parameters
                 if item['Key'] == 'TransactionID'),
                None
            )

            # Mark escrow as completed
            escrow_id = extract_escrow_id_from_conversation(conversation_id)
            await escrow.mark_completed(escrow_id, transaction_id)

            # Notify seller
            transaction = await escrow.get_transaction(escrow_id)
            await notify_payment_released(transaction)

        else:  # Payment release failed
            # Retry logic or manual intervention needed
            logger.error(f"B2C payment failed: {result_desc}")
            await notify_admin_b2c_failed(conversation_id, result_desc)

        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    except Exception as e:
        logger.error(f"B2C callback error: {e}")
        return {"ResultCode": 1, "ResultDesc": "Rejected"}


@app.post('/b2c-timeout')
async def b2c_timeout(request: Request):
    """
    Handle M-Pesa B2C timeout.

    Called if B2C request times out.
    """
    data = await request.json()
    logger.warning(f"B2C timeout: {data}")

    # Implement retry logic
    await schedule_b2c_retry(data)

    return {"ResultCode": 0, "ResultDesc": "Accepted"}
```

### Ngrok Setup (Development)

```bash
# Install ngrok
brew install ngrok  # macOS
# or download from https://ngrok.com/

# Start ngrok
ngrok http 8000

# Update M-Pesa callback URL in .env
CALLBACK_URL=https://abc123.ngrok.io/mpesa-callback
B2C_CALLBACK_URL=https://abc123.ngrok.io/b2c-callback
```

### Production Deployment

**Using Reverse Proxy (Nginx):**

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location /mpesa-callback {
        proxy_pass http://localhost:8000/mpesa-callback;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /b2c-callback {
        proxy_pass http://localhost:8000/b2c-callback;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Testing Guide

### Unit Tests

```python
import pytest
from escrow_manager import EscrowManager
from database import Database

@pytest.mark.asyncio
async def test_create_escrow_transaction():
    """Test escrow transaction creation."""
    db = Database(TEST_DB_URL)
    escrow = EscrowManager(db, mock_mpesa)

    transaction = await escrow.create_transaction(
        buyer_chat_id=123456789,
        seller_username='@testseller',
        item_description='Test Product',
        amount=1000.00
    )

    assert transaction['escrow_id'].startswith('ESC-')
    assert transaction['amount'] == 1000.00
    assert transaction['escrow_fee'] == 10.00  # 1%
    assert transaction['total_paid'] == 1010.00
    assert transaction['status'] == 'pending'

@pytest.mark.asyncio
async def test_state_transition_validation():
    """Test transaction state transitions."""
    escrow = EscrowManager(mock_db, mock_mpesa)

    # Valid transition
    assert await escrow.validate_transition('paid', 'shipped') == True

    # Invalid transition
    with pytest.raises(InvalidStateTransitionError):
        await escrow.validate_transition('pending', 'completed')

@pytest.mark.asyncio
async def test_auto_refund_no_shipping():
    """Test automatic refund if seller doesn't ship."""
    escrow = EscrowManager(mock_db, mock_mpesa)

    # Create transaction with past ship deadline
    transaction_id = await create_test_transaction(
        ship_by_deadline=datetime.now() - timedelta(days=1)
    )

    # Run auto-refund job
    await escrow.process_overdue_shipments()

    # Verify refund processed
    transaction = await escrow.get_transaction(transaction_id)
    assert transaction['status'] == 'refunded'
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_full_escrow_flow():
    """Test complete escrow flow from purchase to completion."""

    # 1. Create transaction
    transaction = await escrow.create_transaction(
        buyer_chat_id=BUYER_ID,
        seller_username='@seller',
        item_description='iPhone 13 Pro',
        amount=95000.00
    )
    escrow_id = transaction['escrow_id']

    # 2. Process payment
    payment = await escrow.process_payment(
        escrow_id=escrow_id,
        phone_number='254712345678'
    )
    assert payment['ResponseCode'] == '0'

    # 3. Simulate M-Pesa callback (payment success)
    await escrow.confirm_payment(
        checkout_request_id=payment['CheckoutRequestID'],
        mpesa_receipt='NLJ7RT61SV',
        amount=95950.00
    )

    # 4. Seller ships
    await escrow.mark_shipped(
        escrow_id=escrow_id,
        seller_chat_id=SELLER_ID,
        tracking_number='EMS-KE-123456'
    )

    # 5. Buyer confirms delivery
    await escrow.confirm_delivery(
        escrow_id=escrow_id,
        buyer_chat_id=BUYER_ID
    )

    # 6. Payment released (background job)
    await escrow.release_payment(escrow_id)

    # Verify final state
    transaction = await escrow.get_transaction(escrow_id)
    assert transaction['status'] == 'completed'
    assert transaction['completed_at'] is not None
```

### Mock M-Pesa for Testing

```python
class MockMpesaService:
    """Mock M-Pesa service for testing."""

    async def initiate_stk_push(self, phone_number, amount, **kwargs):
        """Mock STK push."""
        return {
            'ResponseCode': '0',
            'ResponseDescription': 'Success',
            'CheckoutRequestID': f'ws_CO_TEST_{int(time.time())}',
            'MerchantRequestID': f'TEST_{int(time.time())}'
        }

    async def send_b2c_payment(self, phone_number, amount, **kwargs):
        """Mock B2C payment."""
        return {
            'ResponseCode': '0',
            'ConversationID': f'AG_TEST_{int(time.time())}',
            'OriginatorConversationID': f'TEST_{int(time.time())}'
        }
```

---

## Error Handling

### Error Types

```python
class EscrowError(Exception):
    """Base exception for escrow system."""
    pass

class InvalidStateTransitionError(EscrowError):
    """Raised when invalid state transition attempted."""
    pass

class PermissionError(EscrowError):
    """Raised when user lacks permission for action."""
    pass

class TransactionNotFoundError(EscrowError):
    """Raised when transaction doesn't exist."""
    pass

class UserNotFoundError(EscrowError):
    """Raised when user doesn't exist."""
    pass

class PaymentError(EscrowError):
    """Raised when payment processing fails."""
    pass

class DisputeError(EscrowError):
    """Raised when dispute operation fails."""
    pass
```

### Error Response Format

```python
{
    "error": {
        "code": "INVALID_STATE_TRANSITION",
        "message": "Cannot transition from paid to completed",
        "details": {
            "current_state": "paid",
            "attempted_state": "completed",
            "escrow_id": "ESC-20251122-00123"
        }
    }
}
```

---

## Security

### Authentication

- All API calls must authenticate user via Telegram chat_id
- Verify user permissions before state changes
- Admin actions require admin role verification

### Data Encryption

- Database: TLS/SSL connections
- API: HTTPS only
- Sensitive data: Encrypted at rest

### Rate Limiting

```python
from functools import wraps
import time

# Rate limit decorator
def rate_limit(max_per_minute=30):
    def decorator(func):
        calls = {}

        @wraps(func)
        async def wrapper(user_id, *args, **kwargs):
            now = time.time()
            minute = int(now / 60)
            key = (user_id, minute)

            if key in calls:
                calls[key] += 1
                if calls[key] > max_per_minute:
                    raise RateLimitExceededError(
                        f"Rate limit exceeded: {max_per_minute}/minute"
                    )
            else:
                calls[key] = 1

            # Cleanup old entries
            calls_copy = dict(calls)
            for k in calls_copy:
                if k[1] < minute - 5:
                    del calls[k]

            return await func(user_id, *args, **kwargs)

        return wrapper
    return decorator

@rate_limit(max_per_minute=10)
async def create_escrow_transaction(user_id, *args):
    # Implementation
    pass
```

### Input Validation

```python
def validate_amount(amount: float) -> float:
    """Validate transaction amount."""
    if not isinstance(amount, (int, float)):
        raise ValueError("Amount must be a number")

    if amount < 100:
        raise ValueError("Minimum amount is KES 100")

    if amount > 500000:
        raise ValueError("Maximum amount is KES 500,000")

    return round(float(amount), 2)

def validate_phone_number(phone: str) -> str:
    """Validate Kenyan phone number."""
    import re

    # Remove spaces and dashes
    phone = re.sub(r'[\s-]', '', phone)

    # Must be Kenyan number (254...)
    if not re.match(r'^254\d{9}$', phone):
        raise ValueError(
            "Invalid phone number. Use format: 254XXXXXXXXX"
        )

    return phone
```

---

**API Version:** 2.0
**Last Updated:** November 22, 2025
**Contact:** developers@mpesa-bot.com
