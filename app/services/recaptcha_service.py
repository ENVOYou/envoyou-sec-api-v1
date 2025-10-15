"""
reCAPTCHA verification service
Handles Google reCAPTCHA v3 token verification
"""

from typing import Any, Dict

import httpx
from fastapi import HTTPException, status

from app.core.config import settings


class RecaptchaService:
    """Service for verifying Google reCAPTCHA tokens"""

    RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"

    def __init__(self):
        self.secret_key = getattr(settings, "RECAPTCHA_SECRET_KEY", None)
        if not self.secret_key and not settings.SKIP_RECAPTCHA:
            raise ValueError("RECAPTCHA_SECRET_KEY not configured")

    async def verify_token(
        self, token: str, expected_action: str = "login"
    ) -> Dict[str, Any]:
        """
        Verify reCAPTCHA token with Google

        Args:
            token: The reCAPTCHA token from frontend
            expected_action: Expected action (default: "login")

        Returns:
            Dict containing verification result with score and success status

        Raises:
            HTTPException: If verification fails or token is invalid
        """
        if not token or not token.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="reCAPTCHA token is required",
            )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.RECAPTCHA_VERIFY_URL,
                    data={
                        "secret": self.secret_key,
                        "response": token.strip(),
                    },
                )

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Failed to verify reCAPTCHA token",
                    )

                result = response.json()

                # Check if verification was successful
                if not result.get("success", False):
                    error_codes = result.get("error-codes", [])
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"reCAPTCHA verification failed: {', '.join(error_codes)}"
                        ),
                    )

                # Check action (for v3)
                action = result.get("action")
                if action and action != expected_action:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"reCAPTCHA action mismatch: expected '{expected_action}', "
                            f"got '{action}'"
                        ),
                    )

                # Check score (for v3)
                score = result.get("score", 0.0)
                if score < 0.5:  # Threshold for suspicious activity
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            "reCAPTCHA verification failed: suspicious "
                            "activity detected"
                        ),
                    )

                return {
                    "success": True,
                    "score": score,
                    "action": action,
                    "challenge_ts": result.get("challenge_ts"),
                    "hostname": result.get("hostname"),
                }

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="reCAPTCHA verification timeout",
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"reCAPTCHA verification request failed: {str(e)}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"reCAPTCHA verification error: {str(e)}",
            )

    def is_recaptcha_enabled(self) -> bool:
        """Check if reCAPTCHA is properly configured"""
        return bool(self.secret_key and self.secret_key.strip())

    def get_min_score_threshold(self) -> float:
        """Get minimum score threshold for verification"""
        return getattr(settings, "RECAPTCHA_MIN_SCORE", 0.5)

    def is_testing_mode(self) -> bool:
        """Check if we're in testing mode (skip verification)"""
        return getattr(settings, "TESTING", False) or getattr(
            settings, "SKIP_RECAPTCHA", False
        )
