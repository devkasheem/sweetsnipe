"""
Email verification service for user account security.
Implements email confirmation flow for new registrations.
"""
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional
import os

from sqlalchemy import Column, String, DateTime, Boolean
from backend.database import Base, engine


class EmailVerification(Base):
    """Email verification token storage"""
    __tablename__ = "email_verifications"

    email = Column(String, primary_key=True)
    token = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    verified = Column(Boolean, default=False)


# Create table
Base.metadata.create_all(bind=engine)


class EmailService:
    """Email service for verification and notifications"""

    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("FROM_EMAIL", self.smtp_user)
        self.base_url = os.getenv("BASE_URL", "http://localhost:8000")

    def generate_verification_token(self) -> str:
        """Generate a secure verification token"""
        return secrets.token_urlsafe(32)

    async def send_verification_email(self, email: str, token: str):
        """Send verification email to user"""
        if not self.smtp_user or not self.smtp_password:
            print("⚠️  SMTP not configured, skipping email verification")
            return

        verification_url = f"{self.base_url}/api/auth/verify-email?token={token}"

        subject = "Verify Your Sweetsnipe Account"
        html_body = f"""
        <html>
        <body>
            <h2>Welcome to Sweetsnipe!</h2>
            <p>Thank you for registering. Please verify your email address by clicking the link below:</p>
            <p><a href="{verification_url}">Verify Email Address</a></p>
            <p>This link will expire in 24 hours.</p>
            <p>If you didn't create an account, please ignore this email.</p>
            <br>
            <p>Best regards,<br>The Sweetsnipe Team</p>
        </body>
        </html>
        """

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = email

            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            print(f"✓ Verification email sent to {email}")
        except Exception as e:
            print(f"❌ Failed to send email: {e}")

    async def send_password_reset_email(self, email: str, token: str):
        """Send password reset email"""
        if not self.smtp_user or not self.smtp_password:
            print("⚠️  SMTP not configured, skipping password reset email")
            return

        reset_url = f"{self.base_url}/reset-password?token={token}"

        subject = "Reset Your Sweetsnipe Password"
        html_body = f"""
        <html>
        <body>
            <h2>Password Reset Request</h2>
            <p>We received a request to reset your password. Click the link below to set a new password:</p>
            <p><a href="{reset_url}">Reset Password</a></p>
            <p>This link will expire in 1 hour.</p>
            <p>If you didn't request this, please ignore this email.</p>
            <br>
            <p>Best regards,<br>The Sweetsnipe Team</p>
        </body>
        </html>
        """

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = email

            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            print(f"✓ Password reset email sent to {email}")
        except Exception as e:
            print(f"❌ Failed to send email: {e}")


# Global instance
email_service = EmailService()
