"""
Email Service for sending verification and password reset emails
Supports Mailgun API and SMTP fallback
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

import requests
from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Email service for sending verification and password reset emails"""

    def __init__(self):
        self.service = settings.EMAIL_SERVICE.lower()
        self.from_email = settings.EMAIL_FROM
        self.from_name = settings.EMAIL_FROM_NAME

    def send_verification_email(self, to_email: str, verification_token: str) -> bool:
        """Send email verification link to new user"""
        try:
            verification_url = (
                f"{settings.CORS_ORIGINS[0]}/verify-email?token={verification_token}"
            )

            subject = "Verify Your Email - Envoyou SEC Dashboard"
            html_content = f"""
            <div
            style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #2563eb;">Welcome to Envoyou SEC Dashboard</h2>
                <p>Please verify your email address to complete your registration.</p>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_url}"
                       style="background-color:
                       #2563eb; color: white; padding: 12px 24px;
                              text-decoration:
                              none; border-radius: 6px; display: inline-block;">
                        Verify Email Address
                    </a>
                </div>

            <p>If the button doesn't work, copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #666;">{verification_url}</p>

                <p>This link will expire in 24 hours.</p>

                <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
                <p style="color: #666; font-size: 12px;">
                    If you didn't create an account, please ignore this email.
                </p>
            </div>
            """

            return self._send_email(to_email, subject, html_content)

        except Exception as e:
            logger.error(f"Failed to send verification email to {to_email}: {str(e)}")
            return False

    def send_password_reset_email(self, to_email: str, reset_token: str) -> bool:
        """Send password reset link to user"""
        try:
            reset_url = f"{settings.CORS_ORIGINS[0]}/reset-password?token={reset_token}"

            subject = "Reset Your Password - Envoyou SEC Dashboard"
            html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2563eb;">Password Reset Request</h2>
<p>We received a request to reset your password for your Envoyou SEC Dashboard account.</p>

    <div style="text-align: center; margin: 30px 0;">
        <a href="{reset_url}"
            style="background-color: #dc2626; color: white; padding: 12px 24px;
                    text-decoration: none; border-radius: 6px; display: inline-block;">
            Reset Password
        </a>
    </div>

        <p>If the button doesn't work, copy and paste this link into your browser:</p>
        <p style="word-break: break-all; color: #666;">{reset_url}</p>

                <p>This link will expire in 1 hour.</p>

                <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
                <p style="color: #666; font-size: 12px;">
                    If you didn't request a password reset, please ignore this email.
                    Your password will remain unchanged.
                </p>
            </div>
            """

            return self._send_email(to_email, subject, html_content)

        except Exception as e:
            logger.error(f"Failed to send password reset email to {to_email}: {str(e)}")
            return False

    def _send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """Send email using configured service"""
        try:
            if self.service == "mailgun":
                return self._send_via_mailgun(to_email, subject, html_content)
            elif self.service == "smtp":
                return self._send_via_smtp(to_email, subject, html_content)
            else:
                logger.error(f"Unsupported email service: {self.service}")
                return False

        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False

    def _send_via_mailgun(self, to_email: str, subject: str, html_content: str) -> bool:
        """Send email via Mailgun API"""
        try:
            if not settings.MAILGUN_API_KEY or not settings.MAILGUN_DOMAIN:
                logger.error("Mailgun API key or domain not configured")
                return False

            url = (
                f"{settings.MAILGUN_API_BASE_URL}/v3/{settings.MAILGUN_DOMAIN}/messages"
            )

            data = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": to_email,
                "subject": subject,
                "html": html_content,
            }

            response = requests.post(
                url, auth=("api", settings.MAILGUN_API_KEY), data=data, timeout=30
            )

            if response.status_code == 200:
                logger.info(f"Email sent successfully to {to_email}")
                return True
            else:
                logger.error(
                    f"Mailgun API error: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Mailgun send error: {str(e)}")
            return False

    def _send_via_smtp(self, to_email: str, subject: str, html_content: str) -> bool:
        """Send email via SMTP (fallback)"""
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            if not all(
                [
                    settings.MAILGUN_SMTP_SERVER,
                    settings.MAILGUN_SMTP_USERNAME,
                    settings.MAILGUN_SMTP_PASSWORD,
                ]
            ):
                logger.error("SMTP configuration incomplete")
                return False

            msg = MIMEMultipart()
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email
            msg["Subject"] = subject

            msg.attach(MIMEText(html_content, "html"))

            server = smtplib.SMTP(
                settings.MAILGUN_SMTP_SERVER, settings.MAILGUN_SMTP_PORT
            )

            if settings.MAILGUN_SMTP_USE_TLS:
                server.starttls()

            server.login(settings.MAILGUN_SMTP_USERNAME, settings.MAILGUN_SMTP_PASSWORD)

            server.send_message(msg)
            server.quit()

            logger.info(f"Email sent via SMTP to {to_email}")
            return True

        except Exception as e:
            logger.error(f"SMTP send error: {str(e)}")
            return False
