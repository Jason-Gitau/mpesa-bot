# Complete Escrow System User Guide

## Table of Contents
- [What is the Escrow System](#what-is-the-escrow-system)
- [How It Works](#how-it-works)
- [Buyer Guide](#buyer-guide)
- [Seller Guide](#seller-guide)
- [Timeline](#timeline)
- [Dispute Process](#dispute-process)
- [Fees and Charges](#fees-and-charges)
- [FAQs](#frequently-asked-questions)
- [Security Best Practices](#security-best-practices)
- [Example Scenarios](#example-scenarios)

---

## What is the Escrow System

### Overview
The M-Pesa Escrow System is a secure payment protection service that holds buyer payments safely until sellers fulfill their obligations. Think of it as a trusted middleman that ensures both buyers and sellers get what they agreed upon.

### How It Prevents Fraud

**For Buyers:**
- Your money is held securely until you receive your item/service
- Automatic refunds if sellers don't deliver
- Dispute resolution if items don't match descriptions
- Full payment protection for verified sellers

**For Sellers:**
- Guaranteed payment once you deliver as promised
- Protection against false buyer claims
- Verified transaction records for your business
- Fast payment release (24-72 hours after delivery confirmation)

**Key Protection Features:**
1. **Payment Holding**: Funds are locked in escrow, not released to seller immediately
2. **Delivery Confirmation**: Buyers must confirm receipt before seller gets paid
3. **Automated Refunds**: If sellers don't ship within agreed time, automatic refund
4. **Dispute Mediation**: Admin team reviews evidence from both parties
5. **Transaction History**: Complete audit trail for all transactions

---

## How It Works

### The Escrow Flow (Step-by-Step)

```
Step 1: BUYER INITIATES PURCHASE
Buyer sends /buy command with product details
System creates escrow transaction

Step 2: BUYER PAYS
M-Pesa STK Push sent to buyer's phone
Buyer enters PIN to authorize payment
Funds locked in ESCROW (not sent to seller yet)

Step 3: SELLER NOTIFIED
Seller receives notification of confirmed payment
Payment shown as "HELD IN ESCROW"
Seller prepares and ships item

Step 4: SELLER SHIPS
Seller marks order as shipped using /mark_shipped
Buyer receives shipping notification
Tracking information shared (if available)

Step 5: BUYER RECEIVES
Buyer receives item/service
Buyer inspects item for quality and accuracy

Step 6: BUYER CONFIRMS OR DISPUTES
Option A: Satisfied - Buyer sends /confirm_delivery
Option B: Issue - Buyer sends /dispute with reason

Step 7: PAYMENT RELEASED OR DISPUTE HANDLED
If confirmed: Payment released to seller within 24 hours
If disputed: Admin reviews and makes final decision
```

### Visual Flow Diagram

```
BUYER                    ESCROW SYSTEM              SELLER
  |                             |                      |
  |--[/buy <details>]-------->  |                      |
  |                             |                      |
  |<--[M-Pesa STK Push]------   |                      |
  |                             |                      |
  |--[Enter PIN]------------->  |                      |
  |                             |                      |
  |<--[Payment Confirmed]----   |                      |
  |                             |                      |
  |                       [FUNDS HELD IN ESCROW]       |
  |                             |                      |
  |                             |--[Order #12345]----->|
  |                             |   [KES 5,000 HELD]   |
  |                             |                      |
  |                             |<--[/mark_shipped]----|
  |                             |    [Tracking: X123]  |
  |                             |                      |
  |<--[Shipped! Tracking:X123]--|                      |
  |                             |                      |
  |--[Item Received OK]-------> |                      |
  |                             |                      |
  |--[/confirm_delivery]------> |                      |
  |                             |                      |
  |                       [Release Payment]            |
  |                             |                      |
  |                             |--[KES 5,000]-------->|
  |                             |                      |
  |<--[Thank you!]------------- |--[Funds Received]--->|
```

---

## Buyer Guide

### How to Make Safe Purchases

#### 1. Starting a Purchase

**Command Format:**
```
/buy <item_description> <amount> <seller_username>
```

**Example:**
```
/buy iPhone 13 Pro 256GB 85000 @johnseller
```

**What Happens:**
- System creates escrow transaction ID (e.g., ESC-20251122-00123)
- You receive purchase summary for review
- Seller details shown (verification status, ratings, transactions)

#### 2. Reviewing Purchase Details

Before paying, verify:
- [ ] Item description is accurate
- [ ] Price is correct
- [ ] Seller is verified (look for ✓ badge)
- [ ] Seller has good ratings (aim for 4+ stars)
- [ ] Delivery timeline is acceptable

**Confirmation Prompt:**
```
Order Summary:
Item: iPhone 13 Pro 256GB
Price: KES 85,000
Seller: @johnseller ✓ (4.8⭐, 156 sales)
Escrow Fee: KES 850 (1%)
Total: KES 85,850

Expected Delivery: 3-5 business days
Escrow Protection: 7 days

[Confirm & Pay] [Cancel]
```

#### 3. Making Payment

**Process:**
1. Click [Confirm & Pay]
2. Receive M-Pesa STK push on your phone
3. Enter your M-Pesa PIN
4. Wait for confirmation (5-30 seconds)

**Payment Confirmation:**
```
Payment Successful!

Transaction ID: ESC-20251122-00123
Amount Paid: KES 85,850
Status: HELD IN ESCROW
M-Pesa Receipt: NLJ7RT61SV

Your money is safely held in escrow.
Seller will be notified to ship your item.

You will receive updates at each step.
```

#### 4. Tracking Your Order

**Check Order Status:**
```
/status ESC-20251122-00123
```

**Status Response:**
```
Order Status: SHIPPED
Escrow ID: ESC-20251122-00123

Item: iPhone 13 Pro 256GB
Amount: KES 85,000
Seller: @johnseller ✓

Timeline:
✓ Payment Received: Nov 22, 10:30 AM
✓ Seller Confirmed: Nov 22, 10:35 AM
✓ Item Shipped: Nov 22, 2:45 PM
⏳ Awaiting Delivery

Tracking: EMS-KE-1234567
Estimated Delivery: Nov 24, 2025

Auto-confirm in: 5 days (if no action taken)
```

#### 5. Receiving Your Item

**When Item Arrives:**

1. **Inspect Carefully:**
   - Check packaging for damage
   - Verify item matches description
   - Test functionality (for electronics)
   - Check for missing parts/accessories
   - Compare with seller's photos

2. **If Everything is Good:**
   ```
   /confirm_delivery ESC-20251122-00123
   ```

3. **Optional: Leave Rating:**
   ```
   /rate_seller @johnseller 5 Great seller! Fast shipping!
   ```

**Confirmation Message:**
```
Delivery Confirmed!

Thank you for confirming delivery.
Payment of KES 85,000 will be released to seller within 24 hours.

Rate your experience:
/rate_seller @johnseller <1-5 stars> <optional comment>
```

#### 6. If There's a Problem

**Minor Issues (Try to Resolve):**
```
/contact_seller ESC-20251122-00123
```
- Sends direct message to seller
- Seller has 48 hours to respond
- Document conversation

**Major Issues (File Dispute):**
```
/dispute ESC-20251122-00123 <reason>
```

**Example:**
```
/dispute ESC-20251122-00123 Item received is damaged. Screen has cracks. Photos attached.
```

**What to Include in Dispute:**
- Clear description of problem
- Photos/videos as evidence
- Original listing screenshots
- Communication with seller

---

## Seller Guide

### How to Receive Payments Safely

#### 1. Getting Verified

**Why Verify?**
- Buyers trust verified sellers (35% higher conversion)
- Higher escrow limits (unverified: max KES 10,000/transaction)
- Faster payment release (24hrs vs 72hrs)
- Lower escrow fees (1% vs 2%)

**Verification Process:**
```
/verify_seller
```

**Requirements:**
- Valid Kenyan ID or Passport
- Business registration (for businesses)
- M-Pesa till/paybill number
- Address verification
- Phone number verification

**Verification Time:** 1-3 business days

#### 2. Receiving Order Notifications

**Order Alert:**
```
NEW ORDER! 🎉

Escrow ID: ESC-20251122-00123
Item: iPhone 13 Pro 256GB
Amount: KES 85,000 (HELD IN ESCROW)
Buyer: @sarahbuyer

Payment Confirmed: Nov 22, 10:30 AM
Ship By: Nov 24, 6:00 PM (2 days)

Buyer Details:
Name: Sarah K.
Phone: 254712******
Location: Nairobi, Westlands

[Confirm Order] [Cancel Order]
```

**Actions:**
```
/confirm_order ESC-20251122-00123
```

#### 3. Shipping the Item

**Before Shipping:**
- Package securely
- Take photos of item and packaging
- Get tracking number (recommended)
- Keep shipping receipt

**Mark as Shipped:**
```
/mark_shipped ESC-20251122-00123 <tracking_number>
```

**Example:**
```
/mark_shipped ESC-20251122-00123 EMS-KE-1234567
```

**Shipping Confirmation:**
```
Order Marked as Shipped!

Escrow ID: ESC-20251122-00123
Tracking: EMS-KE-1234567

Buyer has been notified.
Delivery window: 7 days

Payment will be released when:
- Buyer confirms delivery, OR
- 7 days pass without dispute
```

#### 4. Getting Paid

**Payment Release Timeline:**

**Option 1: Buyer Confirms (Fastest)**
- Buyer confirms delivery
- Payment released within 24 hours

**Option 2: Auto-Release (Standard)**
- No confirmation from buyer
- No dispute filed
- Auto-release after 7 days from shipping

**Option 3: After Dispute Resolution**
- Dispute resolved in your favor
- Payment released within 24 hours of decision

**Payment Notification:**
```
Payment Released! 💰

Escrow ID: ESC-20251122-00123
Amount: KES 85,000
Fee: KES 850 (1%)
Net Payment: KES 84,150

M-Pesa Transaction: MPX7RT61SV
Sent to: 254712345678

Buyer Rating: ⭐⭐⭐⭐⭐
Comment: "Great seller! Fast shipping!"

Your Stats:
Total Sales: 157
Average Rating: 4.8⭐
Success Rate: 98.7%
```

#### 5. Handling Disputes

**If Buyer Files Dispute:**
```
DISPUTE FILED ⚠️

Escrow ID: ESC-20251122-00123
Amount: KES 85,000 (PAYMENT ON HOLD)

Buyer Claim:
"Item received is damaged. Screen has cracks."

Evidence Submitted:
- 3 photos
- Unboxing video

You have 48 hours to respond.
/respond_dispute ESC-20251122-00123
```

**How to Respond:**
```
/respond_dispute ESC-20251122-00123 <your_explanation>
```

**Example:**
```
/respond_dispute ESC-20251122-00123 Item was in perfect condition when shipped. See attached photos from pre-shipping inspection. Package was well-protected. Damage likely occurred during shipping. Tracking shows package was mishandled by courier.
```

**Attach Evidence:**
```
/attach_evidence ESC-20251122-00123
```
- Photos of item before shipping
- Packaging photos
- Shipping receipt
- Tracking information
- Communication with buyer

**Dispute Resolution Timeline:**
- Admin reviews within 24-48 hours
- May request additional information
- Decision is final and binding
- Payment released or refunded based on evidence

---

## Timeline

### Escrow Transaction Timeline

#### Payment Phase
- **Payment Initiation:** Instant
- **M-Pesa Confirmation:** 5-30 seconds
- **Escrow Lock:** Immediate after payment

#### Shipping Phase
- **Seller Ship Window:** 2-5 days (specified in listing)
- **Late Shipping:** Automatic buyer refund if exceeded

#### Delivery Phase
- **Standard Delivery:** 3-7 days from shipping
- **Express Delivery:** 1-3 days (premium listings)

#### Release Phase
- **Buyer Confirms:** Payment released in 24 hours
- **Auto-Release:** 7 days after marking shipped (if no dispute)
- **Dispute Resolution:** 2-5 business days

### Complete Transaction Example

```
Day 0 - Nov 22, 10:30 AM
✓ Buyer places order and pays
✓ Funds locked in escrow

Day 0 - Nov 22, 2:45 PM
✓ Seller ships item
✓ Tracking number: EMS-KE-1234567

Day 2 - Nov 24, 4:20 PM
✓ Item delivered to buyer
✓ Buyer confirms delivery

Day 3 - Nov 25, 10:00 AM
✓ Payment released to seller
✓ Transaction complete

Total time: 3 days
```

### Refund Timeline

**Scenario 1: Seller Doesn't Ship**
- Ship deadline: 2 days
- Auto-refund: Immediately after deadline
- Funds return: 1-2 hours to M-Pesa

**Scenario 2: Buyer Files Dispute**
- Dispute filed: Any time before auto-release
- Investigation: 2-5 business days
- Refund processed: Within 24 hours of decision
- Funds return: 1-2 hours to M-Pesa

**Scenario 3: Buyer Cancels Before Shipping**
- Cancel window: Before seller ships
- Refund fee: 1% processing fee
- Funds return: 1-2 hours to M-Pesa

---

## Dispute Process

### When to File a Dispute

**Valid Dispute Reasons:**

1. **Item Not Received**
   - Tracking shows delivered but you didn't receive
   - Package stolen/missing
   - Wrong address (seller's error)

2. **Item Not as Described**
   - Different item received
   - Wrong color/size/model
   - Counterfeit/fake product
   - Missing accessories

3. **Item Damaged/Defective**
   - Damage from poor packaging
   - Defective/broken item
   - Not working as advertised

4. **Seller Non-Performance**
   - Seller won't communicate
   - Seller won't ship
   - Seller shipped wrong item

### How to File a Dispute

**Step 1: Document Everything**
- Take clear photos/videos
- Screenshot conversations
- Save shipping documents
- Note timeline of events

**Step 2: Try to Resolve with Seller**
```
/contact_seller ESC-20251122-00123
```
- Explain issue clearly
- Request resolution (refund/replacement)
- Give 48 hours for response

**Step 3: File Formal Dispute**
```
/dispute ESC-20251122-00123 <reason>
```

**Example:**
```
/dispute ESC-20251122-00123 Item received is iPhone 12, not iPhone 13 Pro as advertised. IMEI check confirms it's iPhone 12. Seller won't respond to messages. Photos attached.
```

**Step 4: Upload Evidence**
```
/attach_evidence ESC-20251122-00123
```
Upload:
- Photos of received item
- Original listing screenshots
- IMEI check results
- Packaging photos
- Conversation screenshots

### Dispute Resolution Process

```
Day 1: Dispute Filed
↓
Escrow payment frozen
Seller notified (48hrs to respond)

Day 2-3: Seller Responds
↓
Seller uploads counter-evidence
Admin reviews both sides

Day 3-5: Admin Investigation
↓
Admin may request:
- Additional photos
- Video calls
- Third-party inspection
- Shipping company investigation

Day 5-7: Decision Made
↓
Admin rules in favor of buyer OR seller
Decision explanation provided
Payment released or refunded

Day 7-8: Appeal (Optional)
↓
Either party can appeal within 24hrs
Requires new evidence
Final decision by senior admin
```

### Dispute Outcomes

**Buyer Wins:**
- Full refund to M-Pesa (minus processing fee if applicable)
- Seller rating impacted
- Seller may be suspended (repeat offenses)
- Return shipping cost determined case-by-case

**Seller Wins:**
- Payment released normally
- Buyer rating impacted
- Frivolous dispute fee charged to buyer (if malicious)

**Partial Resolution:**
- Partial refund agreed
- Buyer keeps item
- Both parties agree to split

### Dispute Evidence Best Practices

**Strong Evidence (Likely to Win):**
- Clear, well-lit photos
- Unboxing videos (timestamped)
- Third-party verification (IMEI, serial numbers)
- Tracking information
- Timestamped conversations

**Weak Evidence (Less Likely to Win):**
- Blurry photos
- No proof of receipt
- Vague descriptions
- No attempt to contact seller
- Claims without documentation

---

## Fees and Charges

### Escrow Fee Structure

#### For Buyers

**Standard Escrow Fee: 1%**
- Charged on transaction amount
- Covers payment protection
- Non-refundable (even if transaction cancelled)
- Minimum: KES 20
- Maximum: KES 1,000 per transaction

**Example Calculation:**
```
Item Price: KES 50,000
Escrow Fee: KES 500 (1%)
Total Charge: KES 50,500
```

**Cancellation Fees:**
- Cancel before seller ships: KES 50 or 1% (whichever is higher)
- Cancel after shipping: Full escrow fee + restocking fee (if seller charges)

#### For Sellers

**Transaction Fees:**

Verified Sellers:
- Escrow fee: 1%
- M-Pesa transfer fee: Standard rates
- Net: ~98% of sale price

Unverified Sellers:
- Escrow fee: 2%
- M-Pesa transfer fee: Standard rates
- Net: ~97% of sale price

**Example for Verified Seller:**
```
Sale Amount: KES 50,000
Escrow Fee: KES 500 (1%)
M-Pesa Fee: KES 50
Net Payment: KES 49,450
```

**Example for Unverified Seller:**
```
Sale Amount: KES 50,000
Escrow Fee: KES 1,000 (2%)
M-Pesa Fee: KES 50
Net Payment: KES 48,950
```

### M-Pesa Transaction Limits

**Per Transaction:**
- Minimum: KES 100
- Maximum (verified sellers): KES 500,000
- Maximum (unverified sellers): KES 10,000

**Daily Limits:**
- Buyers: KES 500,000
- Sellers (verified): KES 2,000,000
- Sellers (unverified): KES 50,000

### Additional Charges

**Dispute Fees:**
- Filing dispute: FREE
- Frivolous dispute penalty: KES 500 (if dispute deemed malicious)

**Express Services:**
- Priority dispute resolution (24hrs): KES 1,000
- Express payment release (6hrs): KES 500

**Premium Features:**
- Seller verification: KES 500 (one-time)
- Premium listing placement: KES 100-500/listing
- Extended escrow protection (30 days): +0.5% fee

---

## Frequently Asked Questions

### For Buyers

**Q: How long is my money held in escrow?**
A: Your payment is held until you confirm delivery or 7 days after seller ships (whichever comes first). If you don't take action, payment auto-releases after 7 days.

**Q: Can I cancel after paying?**
A: Yes, you can cancel before the seller ships. A 1% cancellation fee applies (minimum KES 50). Once shipped, cancellation requires seller agreement or valid dispute.

**Q: What if the seller never ships?**
A: If seller doesn't ship within the agreed timeline (usually 2-5 days), you automatically get a full refund minus processing fees.

**Q: Is there a money-back guarantee?**
A: Yes! If item is not as described or not received, you get a full refund after dispute resolution. Our protection covers 99.2% of legitimate buyer claims.

**Q: Can I track my escrow status?**
A: Yes! Use `/status <escrow_id>` anytime to see current status, timeline, and next steps.

**Q: What if I receive wrong item?**
A: File a dispute immediately with photos. Don't use or damage the item. Keep all packaging. Admin will review and typically resolves in buyer's favor with evidence.

### For Sellers

**Q: When do I get paid?**
A: Payment releases within 24 hours after buyer confirms delivery, or automatically 7 days after you mark as shipped (if no dispute).

**Q: What if buyer doesn't confirm delivery?**
A: No problem! Payment auto-releases after 7 days from shipping date if no dispute is filed.

**Q: Can buyer scam me with false disputes?**
A: Our system detects fraudulent disputes. Frivolous disputes result in penalties for buyers. Strong evidence (pre-shipping photos, tracking) protects you.

**Q: What are benefits of verification?**
A: Lower fees (1% vs 2%), higher transaction limits (KES 500k vs 10k), faster payment release (24hrs vs 72hrs), verified badge increases sales by ~35%.

**Q: Can I offer my own return policy?**
A: Yes! You can specify return terms in listings. Escrow extends automatically for returns.

### General Questions

**Q: Is the escrow system secure?**
A: Yes! We use bank-grade encryption, comply with M-Pesa security standards, and maintain PCI-DSS compliance. Funds are held in regulated escrow accounts.

**Q: What happens if there's a dispute?**
A: Admin team reviews evidence from both parties within 2-5 business days. Decisions are based on documentation, tracking, and policies. Both parties can appeal within 24 hours.

**Q: Are there transaction limits?**
A: Yes. Verified sellers: up to KES 500,000/transaction. Unverified: KES 10,000/transaction. Daily limits also apply.

**Q: Can I use escrow for services?**
A: Yes! Escrow works for services too. Service providers mark as "delivered" when work is complete. Buyers confirm satisfaction.

**Q: What if M-Pesa payment fails?**
A: Transaction is cancelled and no escrow created. No fees charged. You can retry immediately.

**Q: Do you store my M-Pesa PIN?**
A: NEVER! We never see your PIN. M-Pesa handles authentication directly on Safaricom's secure servers.

---

## Security Best Practices

### For Buyers: Protect Yourself

#### Before Buying

1. **Verify Seller:**
   - Check verification badge ✓
   - Read ratings and reviews
   - Look for transaction history
   - Minimum 4+ stars recommended

2. **Research the Item:**
   - Compare prices across platforms
   - If deal seems too good to be true, it probably is
   - Check market value
   - Verify seller actually has item

3. **Communication:**
   - Ask questions before buying
   - Request additional photos
   - Confirm availability
   - Clarify delivery timeline

#### During Transaction

1. **Payment Security:**
   - Only pay through escrow system
   - Never send M-Pesa directly to seller
   - Don't share your PIN with anyone
   - Screenshot payment confirmation

2. **Documentation:**
   - Save all messages
   - Screenshot listing details
   - Note agreed terms
   - Keep escrow ID handy

3. **Red Flags:**
   - Seller asks for direct payment
   - Pressure to cancel escrow
   - Requests for personal information
   - Communication outside platform

#### After Receiving

1. **Inspection:**
   - Video record unboxing
   - Check for authenticity
   - Test functionality
   - Verify serial numbers

2. **Don't Confirm Until:**
   - Item fully inspected
   - Everything matches description
   - No defects found
   - You're completely satisfied

### For Sellers: Protect Your Business

#### Listing Creation

1. **Accurate Descriptions:**
   - Be honest and detailed
   - Include all specifications
   - Mention any defects
   - Use your own photos

2. **Clear Policies:**
   - State shipping timeline
   - Specify return policy
   - Mention warranty (if any)
   - Set buyer expectations

3. **Pricing:**
   - Price competitively
   - Include all costs
   - No hidden fees
   - Be transparent

#### Processing Orders

1. **Shipping Protection:**
   - Take pre-shipping photos
   - Package securely
   - Get tracking numbers
   - Keep receipts

2. **Communication:**
   - Respond quickly
   - Provide updates
   - Be professional
   - Keep records

3. **Documentation:**
   - Photo every item
   - Screenshot conversations
   - Save shipping proof
   - Maintain records

#### Handling Problems

1. **Customer Service:**
   - Address issues quickly
   - Be willing to resolve
   - Offer solutions
   - Stay professional

2. **Dispute Prevention:**
   - Set clear expectations
   - Update buyers regularly
   - Ship on time
   - Package well

### General Security Rules

**DO:**
- ✓ Use strong, unique passwords
- ✓ Enable two-factor authentication
- ✓ Keep app updated
- ✓ Verify URLs before clicking
- ✓ Report suspicious activity
- ✓ Trust verified sellers
- ✓ Read terms and conditions

**DON'T:**
- ✗ Share your M-Pesa PIN
- ✗ Click suspicious links
- ✗ Communicate off-platform
- ✗ Send direct payments
- ✗ Share personal ID documents in chat
- ✗ Rush into transactions
- ✗ Ignore red flags

### Recognizing Scams

**Common Scam Tactics:**

1. **Payment Reversal Scam:**
   - Scammer pays, you ship
   - They claim unauthorized transaction
   - Your escrow protection prevents this

2. **Overpayment Scam:**
   - Buyer "accidentally" overpays
   - Asks for refund of difference
   - Original payment bounces
   - Escrow prevents this

3. **Phishing:**
   - Fake "M-Pesa" or "Bot" messages
   - Links to fake websites
   - Requests for PIN/password
   - Always verify sender

4. **Off-Platform:**
   - Request to communicate via WhatsApp/email
   - Direct payment to "save fees"
   - Promise of "better deal"
   - You lose escrow protection

**If You Suspect Fraud:**
```
/report_user <username> <reason>
```

Admin investigates within 24 hours. Accounts suspended pending review.

### Data Privacy

**We Never:**
- Share your M-Pesa PIN (we don't have it)
- Sell your data to third parties
- Share transaction details with anyone except involved parties
- Request sensitive info via chat

**We Do:**
- Encrypt all communications
- Store data securely
- Comply with data protection laws
- Let you delete your account anytime

---

## Example Scenarios

### Scenario 1: Successful Purchase

**Characters:**
- Sarah (Buyer) - Wants to buy a laptop
- John (Seller) - Verified seller with 4.9⭐ rating

**Timeline:**

**Day 1 - Monday, 10:00 AM**
```
Sarah: /buy Dell XPS 13 i7 16GB 95000 @johnseller

Bot: Order Summary:
Item: Dell XPS 13 i7 16GB
Price: KES 95,000
Seller: @johnseller ✓ (4.9⭐, 203 sales)
Escrow Fee: KES 950
Total: KES 95,950

[Confirm & Pay] [Cancel]

Sarah: [Clicks Confirm & Pay]

Bot: Please enter M-Pesa PIN on your phone...
```

**Day 1 - Monday, 10:02 AM**
```
Bot → Sarah: Payment Successful! ✓
Escrow ID: ESC-20251122-00456
Amount: KES 95,000 (HELD IN ESCROW)
M-Pesa Receipt: NLJ8RT71SV

Bot → John: NEW ORDER! 🎉
Escrow ID: ESC-20251122-00456
Item: Dell XPS 13 i7 16GB
Amount: KES 95,000 (HELD)
Ship by: Nov 23, 6:00 PM
```

**Day 1 - Monday, 3:30 PM**
```
John: /mark_shipped ESC-20251122-00456 SKYNET-789456

Bot → Sarah: Your order has shipped! 📦
Tracking: SKYNET-789456
Estimated delivery: 2-3 days
Track: https://skynet.co.ke/track/789456
```

**Day 3 - Wednesday, 2:15 PM**
```
Sarah receives package, opens it, tests laptop

Sarah: /confirm_delivery ESC-20251122-00456

Bot → Sarah: Delivery confirmed! Thank you!
Rate your experience: /rate_seller @johnseller <1-5>

Sarah: /rate_seller @johnseller 5 Excellent seller! Laptop perfect, fast shipping!

Bot → Sarah: Thank you for your rating!
```

**Day 4 - Thursday, 10:00 AM**
```
Bot → John: Payment Released! 💰
Escrow ID: ESC-20251122-00456
Amount: KES 95,000
Fee: KES 950
Net: KES 94,050
M-Pesa: MPX8RT71SV

Buyer Rating: ⭐⭐⭐⭐⭐
"Excellent seller! Laptop perfect, fast shipping!"
```

**Outcome:** Happy buyer, paid seller, 5-star transaction ✓

---

### Scenario 2: Dispute - Item Not as Described

**Characters:**
- Mike (Buyer) - Ordered iPhone 13 Pro
- Alex (Seller) - Sent iPhone 12 instead

**Timeline:**

**Day 1 - Payment & Shipping**
```
Mike orders iPhone 13 Pro 256GB for KES 95,000
Payment held in escrow
Alex ships immediately
```

**Day 3 - Delivery**
```
Mike receives package
Opens box - it's iPhone 12, not 13 Pro
Checks IMEI - confirms iPhone 12
```

**Day 3 - 4:30 PM**
```
Mike: /contact_seller ESC-20251122-00789

Mike → Alex: Hi, I received iPhone 12, not iPhone 13 Pro as ordered.
The IMEI check confirms it's iPhone 12. Please explain?

[No response from Alex for 2 hours]
```

**Day 3 - 6:45 PM**
```
Mike: /dispute ESC-20251122-00789 Received iPhone 12 instead of
iPhone 13 Pro as advertised. IMEI check attached. Seller not responding.

Mike: /attach_evidence ESC-20251122-00789
[Uploads: unboxing video, IMEI screenshot, original listing screenshot]

Bot → Mike: Dispute Filed ✓
Escrow ID: ESC-20251122-00789
Payment frozen. Admin will review within 48 hours.

Bot → Alex: DISPUTE FILED ⚠️
Buyer claims item not as described.
You have 48 hours to respond.
```

**Day 4 - Admin Review**
```
Admin reviews:
- Original listing: Clearly states "iPhone 13 Pro"
- Evidence: IMEI confirms iPhone 12
- Unboxing video: Shows wrong model
- Seller response: None provided

Admin Decision: Buyer wins dispute
```

**Day 5 - Resolution**
```
Bot → Mike: Dispute Resolved in Your Favor ✓
Full refund: KES 95,000
Return shipping: Pre-paid label sent
M-Pesa refund: 1-2 hours

Please return item to:
[Return address]
Use label: RTN-20251122-00789

Bot → Alex: Dispute Lost ⚠️
Reason: Item not as described (clear evidence)
No payment released
Item to be returned at your cost
Warning issued to your account

Your Stats:
Rating: 4.6⭐ → 4.2⭐
Success Rate: 98% → 96%
Status: Under Review
```

**Outcome:** Buyer protected, refund issued, seller penalized ✓

---

### Scenario 3: Auto-Release (No Confirmation)

**Characters:**
- Grace (Buyer) - Busy professional, forgets to confirm
- David (Seller) - Ships on time

**Timeline:**

**Nov 15 - Order & Payment**
```
Grace orders office chair for KES 15,000
Payment held in escrow
David ships next day with tracking
```

**Nov 18 - Delivery**
```
Chair delivered successfully
Grace signs for delivery
Gets busy, forgets to confirm on platform
```

**Nov 19-24 - Waiting Period**
```
Day 19: Bot → Grace: Reminder: Confirm delivery of ESC-20251115-00234
Day 21: Bot → Grace: Reminder: Auto-release in 3 days if no action taken
Day 24: Bot → Grace: Final reminder: Auto-release tomorrow
```

**Nov 25 - Auto-Release (7 days after shipping)**
```
Bot → Grace: Order ESC-20251115-00234 auto-confirmed
Your silence = satisfaction. Hope you enjoyed your purchase!
Rate seller: /rate_seller @davidseller <1-5>

Bot → David: Payment Released! 💰 (Auto-release)
Amount: KES 15,000
Net: KES 14,850
M-Pesa: MPX9RT81SV

Note: Buyer did not explicitly confirm.
No rating received.
```

**Outcome:** Seller gets paid automatically, transaction complete ✓

---

### Scenario 4: Refund - Seller Never Ships

**Characters:**
- Tom (Buyer) - Ordered shoes
- BadSeller (Seller) - Takes payment, doesn't ship

**Timeline:**

**Nov 20 - Order**
```
Tom orders Nike Air Max for KES 12,000
Payment held in escrow
Ship deadline: Nov 22, 6:00 PM (2 days)
```

**Nov 21**
```
Bot → BadSeller: Reminder: Ship ESC-20251120-00567 by tomorrow 6 PM
Bot → BadSeller: Ship now: /mark_shipped ESC-20251120-00567 <tracking>

[BadSeller takes no action]
```

**Nov 22 - 6:00 PM - Deadline Passes**
```
Bot → Tom: Seller Failed to Ship ⚠️
Your order ESC-20251120-00567 was not shipped on time.

AUTOMATIC REFUND PROCESSING:
Amount: KES 12,000
Escrow fee: KES 120 (refunded)
Total refund: KES 12,120

M-Pesa refund: 1-2 hours

Bot → BadSeller: Order Cancelled - Failed to Ship
Payment forfeited
Warning issued
Impact on seller rating

Your Stats:
Success Rate: 87% → 82%
Account Status: SUSPENDED (pending review)
```

**Nov 22 - 7:15 PM**
```
Bot → Tom: Refund Successful ✓
M-Pesa Receipt: NLJ1RT91SV
Amount: KES 12,120

Sorry for the inconvenience!
Here's KES 500 credit for your next purchase.
```

**Outcome:** Buyer fully refunded, bad seller penalized ✓

---

### Scenario 5: Partial Resolution Agreement

**Characters:**
- Lisa (Buyer) - Ordered dress
- Maria (Seller) - Item has minor defect

**Timeline:**

**Nov 10 - Order & Delivery**
```
Lisa orders designer dress for KES 8,500
Delivered Nov 13
Dress has small stain not shown in photos
```

**Nov 13 - Issue Discovered**
```
Lisa: /contact_seller ESC-20251110-00345

Lisa → Maria: Hi, dress has a small stain on the back that wasn't
mentioned. Can you offer a partial refund? Otherwise I'll need to return.

Maria → Lisa: Oh no! I'm so sorry, I didn't notice that.
Since you like the dress, how about 20% refund (KES 1,700)?
Stain might come out with dry cleaning?

Lisa → Maria: Could you do 25% (KES 2,125)? That would cover
dry cleaning and the inconvenience.

Maria → Lisa: That's fair. Let's do 25%. How do we arrange that?
```

**Nov 13 - Resolution Request**
```
Maria: /partial_release ESC-20251110-00345 75

Bot: Partial Release Request
Seller offers: 75% (KES 6,375) to seller
Buyer gets: 25% refund (KES 2,125)

Buyer must accept: /accept_partial ESC-20251110-00345

Lisa: /accept_partial ESC-20251110-00345

Bot: Partial Resolution Accepted ✓
Seller receives: KES 6,375 (minus fees)
Buyer refund: KES 2,125

Both parties satisfied!
```

**Nov 13 - Completion**
```
Bot → Lisa: Refund processed: KES 2,125
M-Pesa Receipt: NLJ2RT01SV
Please rate seller: /rate_seller @mariaseller <1-5>

Lisa: /rate_seller @mariaseller 4 Minor issue but seller was fair
and responsive. Good communication!

Bot → Maria: Payment released: KES 6,375
Net after fees: KES 6,312

Buyer rating: ⭐⭐⭐⭐
"Minor issue but seller was fair and responsive."
```

**Outcome:** Win-win solution, both parties happy ✓

---

## Getting Help

### Support Channels

**In-App Support:**
```
/help - General help
/support - Contact support team
/faq - Frequently asked questions
```

**Response Times:**
- General queries: Within 2 hours
- Disputes: Within 24 hours
- Urgent issues: Within 30 minutes

**Contact Information:**
- Email: escrow-support@mpesa-bot.com
- Phone: +254-700-ESCROW (+254-700-372769)
- Hours: 24/7 for urgent issues

### Escalation Process

1. Try `/contact_seller` first
2. File `/dispute` if no resolution
3. Provide evidence
4. Wait for admin review
5. Appeal if needed: `/appeal <escrow_id> <reason>`

### Community Resources

- User Guide: This document
- Video Tutorials: /tutorials
- Community Forum: https://community.mpesa-bot.com
- Blog: https://blog.mpesa-bot.com

---

**Last Updated:** November 22, 2025
**Version:** 2.0
**Questions?** Contact support@mpesa-bot.com
