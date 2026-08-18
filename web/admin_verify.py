#!/usr/bin/env python3
"""
Sweetsnipe Hosted - Admin Payment Verification Tool
Usage: python web/admin_verify.py <tx_hash> <user_email> <amount> <currency>
"""
import sys
from web.backend.database import SessionLocal, Payment, User
from web.backend.config import settings

def verify_payment(tx_hash, user_email, amount, currency="ETH"):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            print(f"ERROR: User {user_email} not found")
            return False
        
        existing = db.query(Payment).filter(Payment.tx_hash == tx_hash).first()
        if existing:
            print(f"ERROR: TX {tx_hash} already processed")
            return False
        
        payment = Payment(
            user_id=user.id,
            tx_hash=tx_hash,
            amount=amount,
            currency=currency,
            status="completed"
        )
        db.add(payment)
        
        user.credits += amount
        db.commit()
        
        print(f"SUCCESS: Added ${amount} credits to {user_email}")
        print(f"New balance: ${user.credits:.2f}")
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python web/admin_verify.py <tx_hash> <user_email> <amount> [currency]")
        print("Example: python web/admin_verify.py 0xabc123 user@example.com 5.0 ETH")
        sys.exit(1)
    
    tx_hash = sys.argv[1]
    user_email = sys.argv[2]
    amount = float(sys.argv[3])
    currency = sys.argv[4] if len(sys.argv) > 4 else "ETH"
    
    verify_payment(tx_hash, user_email, amount, currency)
