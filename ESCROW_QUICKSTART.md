# Escrow System Quick Start Guide

**Get started with secure M-Pesa escrow payments in 5 minutes!**

---

## Table of Contents
- [For Buyers: Your First Purchase](#for-buyers-your-first-purchase)
- [For Sellers: Get Verified & Start Selling](#for-sellers-get-verified--start-selling)
- [For Admins: Managing Disputes](#for-admins-managing-disputes)

---

## For Buyers: Your First Purchase

### Step 1: Start the Bot (30 seconds)

1. **Open Telegram** and search for `@MPesaEscrowBot`
2. **Click START** or send `/start`

You'll see:
```
Welcome to M-Pesa Secure Escrow! 🛡️

Your money is protected until you receive your item.

Quick Commands:
/buy - Make a purchase
/status - Check order status
/help - Get help

Let's get you set up! →
```

### Step 2: Set Your Phone Number (30 seconds)

Send this command (replace with your M-Pesa number):
```
/set_phone 254712345678
```

Bot responds:
```
✓ Phone number saved: 254712345678

This is your M-Pesa payment number.
We'll never share it or store your PIN.

You're ready to shop! Try /buy
```

### Step 3: Make Your First Purchase (2 minutes)

**Find a Seller:**
Browse seller listings or get a seller's username.

**Send Buy Command:**
```
/buy iPhone 13 Pro 256GB 95000 @johnseller
```

**Format:**
```
/buy <item description> <price> <seller username>
```

**You'll see:**
```
📦 Order Summary

Item: iPhone 13 Pro 256GB
Price: KES 95,000
Seller: @johnseller ✓
  └─ Rating: 4.8⭐ (203 sales)
  └─ Verified: YES ✓
  └─ Member since: Jan 2024

Escrow Fee: KES 950 (1%)
Total: KES 95,950

Ship by: Nov 24, 6:00 PM
Your protection: 7 days

[✅ Pay Now] [❌ Cancel]
```

### Step 4: Complete Payment (1 minute)

1. **Click [✅ Pay Now]**

2. **M-Pesa prompt appears on your phone:**
   - Enter your M-Pesa PIN
   - Confirm payment

3. **Payment confirmed!**
```
✓ Payment Successful!

Escrow ID: ESC-20251122-00456
Amount: KES 95,000 (HELD SAFELY)
M-Pesa Receipt: NLJ7RT61SV

🔒 Your money is protected in escrow.
💰 Seller will only be paid after you confirm delivery.

Seller has been notified to ship your item.
Expected shipping: Within 2 days

Track your order: /status ESC-20251122-00456
```

**That's it! Your payment is secure!** 🎉

### Step 5: When Item Arrives (30 seconds)

**After you receive the item:**

1. **Inspect everything carefully**
2. **If all good, confirm delivery:**
```
/confirm_delivery ESC-20251122-00456
```

3. **Done!**
```
✓ Delivery Confirmed!

Payment of KES 95,000 will be released to seller within 24 hours.

Rate your experience:
/rate @johnseller 5 Great seller! Fast shipping!

Thank you for using Escrow Protection! 🎉
```

### What If Something's Wrong?

**Problem with your order?**
```
/dispute ESC-20251122-00456 Item is damaged, screen cracked
```

Then upload photos:
```
/attach_evidence ESC-20251122-00456
[Send photos/videos]
```

Our team reviews within 24-48 hours and protects your money!

---

## For Sellers: Get Verified & Start Selling

### Why Get Verified?

**Benefits:**
- ✓ **Lower fees:** 1% instead of 2%
- ✓ **Higher limits:** KES 500,000 vs KES 10,000
- ✓ **Faster payments:** 24 hours vs 72 hours
- ✓ **Verified badge:** Increases sales by 35%
- ✓ **Customer trust:** Buyers prefer verified sellers

### Step 1: Start Verification (2 minutes)

**Send Command:**
```
/verify_seller
```

**Follow the prompts:**
```
🏅 Seller Verification Process

To become a verified seller, provide:

1. Full Name
2. Kenyan ID or Passport Number
3. M-Pesa Number (for receiving payments)
4. Business Name (optional)
5. Business Registration (if applicable)

Reply with your information:
Format:
/verify <name> | <id> | <phone> | <business_name>

Example:
/verify John Kamau | 12345678 | 254712345678 | John's Electronics
```

**Submit Your Info:**
```
/verify John Kamau | 12345678 | 254712345678 | John's Electronics
```

**Upload Documents:**
```
📸 Please upload a clear photo of:
1. Your ID (front and back)
2. Business registration (if applicable)

Send photos now →
```

Send your photos, then:
```
✓ Documents Received!

Verification Timeline:
- Review: 1-3 business days
- Notification: Via Telegram
- Status: /verification_status

We'll notify you when approved! ⏳
```

### Step 2: Wait for Approval (1-3 days)

**Check status anytime:**
```
/verification_status
```

**When approved:**
```
🎉 VERIFIED SELLER!

Status: APPROVED ✓
Date: Nov 22, 2025

Your Benefits:
- Escrow Fee: 1% (was 2%)
- Transaction Limit: KES 500,000 (was 10,000)
- Payment Release: 24 hours (was 72 hours)
- Profile Badge: ✓ Verified Seller

Start selling: Create your first listing!
/create_listing
```

### Step 3: Receive Your First Order (30 seconds)

**When buyer orders from you:**
```
🎉 NEW ORDER!

Escrow ID: ESC-20251122-00789
Item: iPhone 13 Pro 256GB
Amount: KES 95,000 (HELD IN ESCROW)
Buyer: @sarahbuyer

Payment Confirmed: ✓
Ship By: Nov 24, 6:00 PM (2 days)

📍 Shipping Details:
Name: Sarah Kamau
Phone: 254712******
Location: Nairobi, Westlands

[✅ Confirm Order] [❌ Cancel]
```

**Click [✅ Confirm Order]:**
```
✓ Order Confirmed!

Action Required:
1. Package item securely
2. Take photos (for your protection)
3. Ship within 2 days
4. Mark as shipped: /mark_shipped ESC-20251122-00789

IMPORTANT:
- Payment is held safely in escrow
- You'll be paid after buyer confirms delivery
- Take pre-shipping photos to protect yourself
```

### Step 4: Ship the Item (1 minute)

**After shipping:**
```
/mark_shipped ESC-20251122-00789 EMS-KE-123456
```

**Confirmation:**
```
✓ Order Marked as Shipped!

Escrow ID: ESC-20251122-00789
Tracking: EMS-KE-123456
Shipped: Nov 22, 2:45 PM

Buyer has been notified.
Expected delivery: 3-5 business days

💰 Payment Schedule:
- Buyer confirms: Payment within 24 hours
- No confirmation: Auto-release in 7 days
- Dispute filed: Hold pending resolution

Track order: /status ESC-20251122-00789
```

### Step 5: Get Paid! (24 hours after delivery)

**When buyer confirms delivery:**
```
💰 PAYMENT RELEASED!

Escrow ID: ESC-20251122-00789
Sale Amount: KES 95,000
Escrow Fee: KES 950 (1%)
M-Pesa Fee: KES 50
Net Payment: KES 94,000

M-Pesa Transaction: MPX7RT61SV
Sent to: 254712345678

Buyer Rating: ⭐⭐⭐⭐⭐
Comment: "Excellent seller! Fast shipping, great product!"

📊 Your Stats:
Total Sales: 204 (+1)
Average Rating: 4.8⭐
Success Rate: 98.5%

Thanks for being a great seller! 🎉
```

### Unverified Sellers (No Verification Needed)

**Can start immediately but with limits:**
- Maximum: KES 10,000 per transaction
- Fee: 2% (instead of 1%)
- Payment release: 72 hours (instead of 24)
- No verified badge

**Start selling unverified:**
```
/create_listing
```

---

## For Admins: Managing Disputes

### Step 1: Access Admin Panel (10 seconds)

**Admin Commands:**
```
/admin - Access admin dashboard
/disputes - View all active disputes
/stats - View system statistics
```

**Admin Dashboard:**
```
🛡️ ESCROW ADMIN PANEL

📊 Overview:
- Active Transactions: 247
- Pending Disputes: 12
- Total Volume Today: KES 4,234,500

🚨 Urgent Items:
- Disputes over 24hrs: 3
- Failed payments: 5
- Suspicious activity: 1

[View Disputes] [View Stats] [User Management]
```

### Step 2: Review Disputes (2-5 minutes per dispute)

**View Active Disputes:**
```
/disputes
```

**Dispute List:**
```
🚨 ACTIVE DISPUTES (12)

1. DIS-20251122-00045 [HIGH PRIORITY]
   Escrow: ESC-20251120-00234
   Filed: 2 days ago
   Amount: KES 45,000
   Reason: Item not as described
   Status: Awaiting admin review

2. DIS-20251122-00046 [NORMAL]
   Escrow: ESC-20251121-00567
   Filed: 1 day ago
   Amount: KES 12,000
   Reason: Item damaged
   Status: Seller responded

[View Details] [Resolve] [Next Page]
```

**View Dispute Details:**
```
/dispute_details DIS-20251122-00045
```

**Detailed View:**
```
📋 DISPUTE DETAILS

Dispute ID: DIS-20251122-00045
Escrow ID: ESC-20251120-00234
Status: Under Review
Priority: HIGH
Filed: Nov 20, 2025 (2 days ago)

💰 Transaction:
Amount: KES 45,000
Item: "Nike Air Jordan 1 Retro High"
Buyer: @mikeb (4.5⭐, 23 purchases)
Seller: @shoeseller (4.2⭐, 89 sales)

🚨 Buyer's Claim:
"Received counterfeit shoes, not authentic Nike.
Box is fake, no authentication tag, poor quality."

Evidence Uploaded: 6 items
- 4 photos (product, box, tag)
- 1 video (unboxing)
- 1 document (authentication check)

💬 Seller's Response:
"These are 100% authentic! Purchased from authorized
dealer. Buyer is trying to scam. See my purchase receipt."

Evidence Uploaded: 3 items
- 2 photos (receipt, original listing)
- 1 document (dealer invoice)

⏰ Timeline:
- Nov 18: Order placed & paid
- Nov 19: Seller shipped (EMS-KE-789)
- Nov 20: Delivered, dispute filed
- Nov 21: Seller responded
- Nov 22: Awaiting admin decision

[View Evidence] [Resolve Dispute] [Request More Info]
```

### Step 3: Review Evidence (5-10 minutes)

**View All Evidence:**
```
/view_evidence DIS-20251122-00045
```

**Evidence Viewer:**
```
📸 DISPUTE EVIDENCE

Buyer Evidence (6 items):

1. Photo: Product front view
   [Image shows: Shoes with visible quality issues]

2. Photo: Box and packaging
   [Image shows: Box with inconsistent branding]

3. Photo: Authentication tag comparison
   [Image shows: Tag vs authentic Nike tag]

4. Video: Unboxing (2:34)
   [Video shows: Package opening, item inspection]

5. Document: CheckCheck authentication
   [PDF shows: FAKE result from authentication app]

Seller Evidence (3 items):

1. Photo: Purchase receipt
   [Image shows: Receipt from "Nike Authorized Dealer"]

2. Photo: Original listing
   [Image shows: Stock photo from Nike website]

3. Document: Dealer invoice
   [PDF shows: Invoice for bulk purchase]

[Next] [Download All] [Back to Dispute]
```

### Step 4: Make Decision (2 minutes)

**Admin Analysis:**
```
🤔 Analysis Tools:

Image Search: [Run Google Reverse Image Search]
Authenticity: [Contact Nike Kenya for verification]
Seller History: [View past disputes and ratings]
Buyer History: [Check for dispute patterns]

Similar Cases: 3 found
└─ 2 resolved in favor of buyer
└─ 1 resolved in favor of seller
```

**Resolve Dispute:**
```
/resolve_dispute DIS-20251122-00045
```

**Resolution Options:**
```
🛡️ RESOLVE DISPUTE

Dispute ID: DIS-20251122-00045
Amount: KES 45,000

Choose Resolution:

1. [Buyer Wins - Full Refund]
   → Buyer gets: KES 45,000
   → Seller gets: KES 0
   → Buyer must return item

2. [Seller Wins - Payment Released]
   → Buyer gets: KES 0
   → Seller gets: KES 45,000
   → No return required

3. [Split Resolution - Partial]
   → Custom amounts
   → Partial refund + partial payment

4. [Need More Info]
   → Request additional evidence
   → Extend deadline

Enter choice (1-4):
```

**Admin Decision:**
```
1

Enter resolution explanation:
```

**Admin Writes:**
```
Based on CheckCheck authentication report showing "FAKE" and
comparison with authentic Nike tags, evidence supports buyer's
claim. Shoes appear to be counterfeit. Full refund approved.

Buyer must return item to seller at seller's expense.
Seller receives warning - counterfeit items prohibited.
```

**Confirm:**
```
✓ DISPUTE RESOLVED

Decision: Buyer Wins (Full Refund)
Reason: Counterfeit product

Actions Taken:
✓ Refund KES 45,000 to buyer
✓ Return label generated
✓ Seller warned (strike 1/3)
✓ Seller rating adjusted: 4.2 → 3.9
✓ Both parties notified

Notifications Sent:
→ Buyer: Refund approved, return instructions
→ Seller: Dispute lost, warning issued

[Close] [View Next Dispute]
```

### Step 5: Monitor Resolution (Ongoing)

**Track Resolution:**
```
/track_resolution DIS-20251122-00045
```

**Resolution Timeline:**
```
📦 RESOLUTION TRACKING

Dispute ID: DIS-20251122-00045
Status: Resolved → Return in Progress

Timeline:
✓ Nov 22, 10:30 AM - Dispute resolved
✓ Nov 22, 10:35 AM - Return label sent to buyer
✓ Nov 22, 2:15 PM - Buyer shipped return
⏳ Nov 24 (Est.) - Seller receives return
⏳ Nov 25 - Final refund processed

Return Tracking: RTN-789456
Status: In Transit

When seller confirms receipt of return:
→ Final refund processed to buyer
→ Case closed

[Mark Return Received] [View Details]
```

### Admin Quick Actions

**Suspend User:**
```
/suspend_user @badactor "Multiple counterfeit reports"
```

**Ban User:**
```
/ban_user @scammer "Confirmed fraud attempt"
```

**Adjust Rating:**
```
/adjust_rating @seller -0.5 "Dispute lost - quality issue"
```

**Issue Refund:**
```
/issue_refund ESC-20251120-00234 45000 "Admin decision - dispute DIS-20251122-00045"
```

**Release Payment:**
```
/release_payment ESC-20251120-00234 "Admin override - verified delivery"
```

### Admin Dashboard Stats

**View Statistics:**
```
/stats
```

**Stats Dashboard:**
```
📊 ESCROW SYSTEM STATISTICS

Today (Nov 22, 2025):
💰 Transaction Volume: KES 4,234,500
📦 Total Transactions: 247
✓ Completed: 198 (80.2%)
⏳ In Progress: 37 (15.0%)
🚨 Disputed: 12 (4.8%)

This Week:
💰 Volume: KES 28,456,000
📦 Transactions: 1,543
⭐ Avg Rating: 4.6
✓ Success Rate: 96.8%

Disputes:
🚨 Active: 12
⚖️ Resolved: 45
📈 Resolution Time: 2.3 days avg
👨‍⚖️ Buyer Wins: 62%
👨‍💼 Seller Wins: 31%
🤝 Split: 7%

Top Issues:
1. Item not as described (38%)
2. Damaged in shipping (24%)
3. Item not received (18%)
4. Quality issues (12%)
5. Other (8%)

[Detailed Report] [Export Data] [Alert Settings]
```

---

## Common Quick Commands

### Buyers
```
/buy <item> <amount> <seller>  - Make purchase
/status <escrow_id>            - Check order status
/confirm_delivery <escrow_id>  - Confirm receipt
/dispute <escrow_id> <reason>  - File dispute
/my_orders                     - View all orders
```

### Sellers
```
/verify_seller                      - Start verification
/mark_shipped <escrow_id> <tracking> - Mark as shipped
/my_sales                           - View all sales
/respond_dispute <dispute_id>       - Respond to dispute
/stats                              - View your statistics
```

### Admins
```
/admin                          - Admin panel
/disputes                       - View disputes
/resolve_dispute <dispute_id>   - Resolve dispute
/stats                          - System statistics
/suspend_user <username>        - Suspend user
```

---

## Tips for Success

### For Buyers
1. ✓ Always check seller ratings and verification
2. ✓ Read item descriptions carefully
3. ✓ Ask questions before buying
4. ✓ Inspect items thoroughly on arrival
5. ✓ Confirm delivery promptly if satisfied
6. ✓ Document issues with photos/videos

### For Sellers
1. ✓ Get verified for better benefits
2. ✓ Describe items accurately
3. ✓ Take photos before shipping
4. ✓ Ship promptly (within deadline)
5. ✓ Use tracking when possible
6. ✓ Respond to buyer messages quickly

### For Admins
1. ✓ Review evidence thoroughly
2. ✓ Be impartial and fair
3. ✓ Document decisions clearly
4. ✓ Respond to disputes within 48 hours
5. ✓ Look for patterns in user behavior
6. ✓ Update policies based on trends

---

## Need Help?

**Support:**
```
/help - Get help
/support - Contact support team
/faq - Frequently asked questions
```

**Emergency:**
- For urgent issues: `/urgent <issue>`
- Email: support@mpesa-escrow.com
- Phone: +254-700-ESCROW

---

**You're ready to use the Escrow System! 🎉**

Start with:
- **Buyers:** `/buy`
- **Sellers:** `/verify_seller`
- **Admins:** `/admin`

---

**Last Updated:** November 22, 2025
**Version:** 2.0
