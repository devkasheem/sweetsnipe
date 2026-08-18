"""
Reset database and create admin user
Run this script from the web/ directory
"""
import os
import sys

# Backup old database if it exists
if os.path.exists("sweetsnipe.db"):
    import shutil
    shutil.move("sweetsnipe.db", "sweetsnipe.db.backup")
    print("Old database backed up to sweetsnipe.db.backup")

# Recreate database with correct schema
from backend.database import Base, engine, SessionLocal, User
Base.metadata.create_all(bind=engine)
print("Database recreated with correct schema")

# Create admin user
from backend.auth import get_password_hash
import uuid

db = SessionLocal()

admin = User(
    id=str(uuid.uuid4()),
    email="admin@sweetsnipe.local",
    hashed_password=get_password_hash("Admin@123456"),
    credits=100.0,
    is_admin=True,
    is_active=True
)
db.add(admin)
db.commit()
db.close()

print("SUCCESS: Admin user created!")
print("Email: admin@sweetsnipe.local")
print("Password: Admin@123456")
print("")
print("IMPORTANT: Change this password after first login!")
