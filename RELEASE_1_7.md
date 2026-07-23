# Scooter Service Bot — Release 1.7 Release Notes

Release 1.7 introduces **Variant 5: Telegram Payments & Prepayment Integration**.

---

## 🌟 What's New in Release 1.7

### 1. 💳 Telegram Payments Integration
- Direct in-chat digital payments for repair quotes using the Telegram Payments API.
- Support for Yookassa, Sberbank, Tinkoff, Telegram Stars, and test payment tokens.
- Interactive `💳 Оплатить онлайн` button in client final offer notifications.

### 2. 🧾 Invoice Generation & PreCheckout Validation
- Dynamically constructs `LabeledPrice` line items based on catalog services or master estimate quotes.
- `PreCheckoutQuery` validation handler ensuring payload validity before charge execution.

### 3. 📝 Transaction History & Status Automation
- Successful payments automatically update ticket status:
  - `payment_status`: `UNPAID` ➔ `PAID`
  - `ticket_status`: `PRICE_OFFERED` ➔ `CLIENT_APPROVED`
- Payment details recorded in `payment_transactions` table (`telegram_payment_charge_id`, `amount`, `currency`).
- Real-time notification sent to client and master team chat (`masters_chat_id`).

---

## 📊 Database & Migration

- Added Alembic migration [0005_v17_telegram_payments.py](file:///home/mx/scooter-service-bot/alembic/versions/0005_v17_telegram_payments.py).
- New Enum `PaymentStatus`.
- New table `payment_transactions`.
- Added `payment_status` and `payment_id` columns to `tickets`.

---

## 🧪 Testing

- 31 unit and integration tests passing (`uv run pytest`):
  - `tests/test_payments_integration.py`
  - `tests/test_live_tracking_integration.py`
  - `tests/test_ticket_lifecycle_integration.py`
