"""
Database migration script for Sweetsnipe
Applies schema updates and creates indexes for production optimization
"""
import sys
import os

# Add parent directory to paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.backend.database import engine, Base, SessionLocal
from sqlalchemy import text

def run_migrations():
    """Run database migrations"""
    print("Starting database migrations...")

    # Create all tables
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("✓ Tables created")

    # Add indexes if they don't exist
    db = SessionLocal()
    try:
        # Check if we're using PostgreSQL or SQLite
        db_url = str(engine.url)
        is_postgres = "postgresql" in db_url

        if is_postgres:
            print("Detected PostgreSQL - creating optimized indexes...")

            # User indexes
            try:
                db.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_user_email_active
                    ON users(email, is_active)
                """))
                print("✓ User indexes created")
            except Exception as e:
                print(f"Note: User indexes may already exist: {e}")

            # Job indexes
            try:
                db.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_job_user_status
                    ON jobs(user_id, status)
                """))
                db.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_job_status_created
                    ON jobs(status, created_at)
                """))
                print("✓ Job indexes created")
            except Exception as e:
                print(f"Note: Job indexes may already exist: {e}")

            # Worker indexes
            try:
                db.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_worker_job_id
                    ON workers(job_id)
                """))
                print("✓ Worker indexes created")
            except Exception as e:
                print(f"Note: Worker indexes may already exist: {e}")

            # Payment indexes
            try:
                db.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_payment_user_status
                    ON payments(user_id, status)
                """))
                db.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_payment_tx_hash
                    ON payments(tx_hash)
                """))
                print("✓ Payment indexes created")
            except Exception as e:
                print(f"Note: Payment indexes may already exist: {e}")

            db.commit()
            print("✓ All PostgreSQL optimizations applied")
        else:
            print("Detected SQLite - skipping advanced indexes (not needed for development)")

        print("\n✅ Database migration completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_migrations()
