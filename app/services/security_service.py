"""
Enhanced Security Service
Advanced security features including intrusion detection, threat monitoring, and security hardening
"""

import hashlib
import hmac
import logging
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)


class SecurityService:
    """Enhanced security service for threat detection and monitoring"""

    def __init__(self):
        self.suspicious_patterns = {
            "sql_injection": [
                r"(\b(union|select|insert|update|delete|drop|create|alter)\b.*\b(select|from|where|and|or)\b)",
                r"(\bor\b\s+\d+\s*=\s*\d+)",
                r"(\';.*--)",
                r"(\bxp_cmdshell\b)",
                r"(\bexec\b.*\bmaster\b)",
            ],
            "xss": [
                r"(<script[^>]*>.*?</script>)",
                r"(javascript:)",
                r"(on\w+\s*=)",
                r"(<iframe[^>]*>)",
                r"(<object[^>]*>)",
            ],
            "path_traversal": [
                r"(\.\./)",
                r"(\.\.\\)",
                r"(%2e%2e%2f)",
                r"(%2e%2e/)",
            ],
            "command_injection": [
                r"(\|\||&&|;)",
                r"(\$\([^)]+\))",
                r"(\`[^\`]+\`)",
            ],
        }

        # Security monitoring
        self.failed_login_attempts = defaultdict(lambda: {"count": 0, "last_attempt": None, "blocked_until": None})
        self.suspicious_requests = deque(maxlen=1000)
        self.ip_blocklist = set()
        self.rate_limit_violations = defaultdict(int)

        # Security thresholds
        self.max_failed_logins = 5
        self.block_duration_minutes = 15
        self.max_rate_limit_violations = 10

    def analyze_request_for_threats(self, request: Request, user_id: Optional[str] = None) -> Dict[str, any]:
        """
        Analyze incoming request for security threats

        Args:
            request: FastAPI request object
            user_id: Optional user ID

        Returns:
            Threat analysis result
        """
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        path = str(request.url.path)
        query_params = str(request.url.query)
        method = request.method

        threats_detected = []
        risk_score = 0

        # Check for suspicious patterns in URL and query parameters
        url_content = f"{path}?{query_params}"
        for threat_type, patterns in self.suspicious_patterns.items():
            for pattern in patterns:
                if re.search(pattern, url_content, re.IGNORECASE):
                    threats_detected.append({
                        "type": threat_type,
                        "pattern": pattern,
                        "location": "url",
                        "severity": "high" if threat_type in ["sql_injection", "command_injection"] else "medium",
                    })
                    risk_score += 10 if threat_type in ["sql_injection", "command_injection"] else 5

        # Check user agent for suspicious patterns
        suspicious_uas = ["sqlmap", "nmap", "nikto", "dirbuster", "gobuster", "burpsuite"]
        for ua in suspicious_uas:
            if ua.lower() in user_agent.lower():
                threats_detected.append({
                    "type": "suspicious_user_agent",
                    "pattern": ua,
                    "location": "user_agent",
                    "severity": "high",
                })
                risk_score += 15

        # Check for unusual request patterns
        if self._is_unusual_request_pattern(method, path, client_ip):
            threats_detected.append({
                "type": "unusual_request_pattern",
                "pattern": f"{method} {path}",
                "location": "request_pattern",
                "severity": "low",
            })
            risk_score += 2

        # Check IP reputation (simplified)
        if client_ip in self.ip_blocklist:
            threats_detected.append({
                "type": "blocked_ip",
                "pattern": client_ip,
                "location": "ip_address",
                "severity": "critical",
            })
            risk_score += 50

        # Determine overall risk level
        risk_level = self._calculate_risk_level(risk_score)

        # Log suspicious activity
        if threats_detected:
            self._log_suspicious_activity(client_ip, user_id, threats_detected, risk_level)

            # Record suspicious request
            self.suspicious_requests.append({
                "timestamp": datetime.utcnow().isoformat(),
                "client_ip": client_ip,
                "user_id": user_id,
                "method": method,
                "path": path,
                "user_agent": user_agent,
                "threats": threats_detected,
                "risk_score": risk_score,
                "risk_level": risk_level,
            })

        return {
            "threats_detected": len(threats_detected) > 0,
            "threat_count": len(threats_detected),
            "risk_score": risk_score,
            "risk_level": risk_level,
            "threats": threats_detected,
            "client_ip": client_ip,
            "recommended_action": self._get_recommended_action(risk_level),
        }

    def record_failed_login(self, username: str, client_ip: str) -> Dict[str, any]:
        """
        Record a failed login attempt and check for brute force attacks

        Args:
            username: Username that failed login
            client_ip: Client IP address

        Returns:
            Login attempt analysis
        """
        key = f"{username}:{client_ip}"
        now = datetime.utcnow()

        attempt = self.failed_login_attempts[key]
        attempt["count"] += 1
        attempt["last_attempt"] = now

        # Check if account should be blocked
        if attempt["count"] >= self.max_failed_logins:
            attempt["blocked_until"] = now + timedelta(minutes=self.block_duration_minutes)

            logger.warning(
                f"Account blocked due to failed login attempts: {username} from {client_ip}"
            )

            return {
                "blocked": True,
                "blocked_until": attempt["blocked_until"].isoformat(),
                "remaining_attempts": 0,
                "reason": "too_many_failed_attempts",
            }

        remaining_attempts = self.max_failed_logins - attempt["count"]

        return {
            "blocked": False,
            "remaining_attempts": remaining_attempts,
            "total_attempts": attempt["count"],
            "warning": remaining_attempts <= 2,
        }

    def check_login_block(self, username: str, client_ip: str) -> bool:
        """
        Check if a login attempt should be blocked

        Args:
            username: Username attempting login
            client_ip: Client IP address

        Returns:
            True if login should be blocked
        """
        key = f"{username}:{client_ip}"
        attempt = self.failed_login_attempts[key]

        if attempt["blocked_until"] and datetime.utcnow() < attempt["blocked_until"]:
            return True

        return False

    def record_rate_limit_violation(self, client_ip: str, endpoint: str) -> Dict[str, any]:
        """
        Record a rate limit violation

        Args:
            client_ip: Client IP address
            endpoint: API endpoint

        Returns:
            Rate limit violation analysis
        """
        key = f"{client_ip}:{endpoint}"
        self.rate_limit_violations[key] += 1

        violation_count = self.rate_limit_violations[key]

        if violation_count >= self.max_rate_limit_violations:
            # Add IP to blocklist
            self.ip_blocklist.add(client_ip)
            logger.warning(f"IP blocked due to rate limit violations: {client_ip}")

            return {
                "ip_blocked": True,
                "violation_count": violation_count,
                "reason": "excessive_rate_limit_violations",
            }

        return {
            "ip_blocked": False,
            "violation_count": violation_count,
            "warning_threshold": self.max_rate_limit_violations,
        }

    def clear_failed_logins(self, username: str, client_ip: str):
        """Clear failed login attempts for successful login"""
        key = f"{username}:{client_ip}"
        if key in self.failed_login_attempts:
            del self.failed_login_attempts[key]

    def get_security_status(self) -> Dict[str, any]:
        """Get current security status and statistics"""
        now = datetime.utcnow()

        # Clean up expired blocks
        self._cleanup_expired_blocks()

        # Calculate statistics
        active_blocks = sum(
            1 for attempt in self.failed_login_attempts.values()
            if attempt["blocked_until"] and attempt["blocked_until"] > now
        )

        recent_suspicious = [
            req for req in self.suspicious_requests
            if (now - datetime.fromisoformat(req["timestamp"])).seconds < 3600  # Last hour
        ]

        return {
            "security_status": "active",
            "active_account_blocks": active_blocks,
            "blocked_ips": len(self.ip_blocklist),
            "recent_suspicious_requests": len(recent_suspicious),
            "total_suspicious_requests": len(self.suspicious_requests),
            "security_thresholds": {
                "max_failed_logins": self.max_failed_logins,
                "block_duration_minutes": self.block_duration_minutes,
                "max_rate_limit_violations": self.max_rate_limit_violations,
            },
            "recent_threats": recent_suspicious[-5:],  # Last 5 suspicious requests
        }

    def validate_password_strength(self, password: str) -> Dict[str, any]:
        """
        Validate password strength

        Args:
            password: Password to validate

        Returns:
            Password strength analysis
        """
        score = 0
        feedback = []

        # Length check
        if len(password) >= 12:
            score += 2
        elif len(password) >= 8:
            score += 1
        else:
            feedback.append("Password should be at least 8 characters long")

        # Character variety checks
        if re.search(r"[a-z]", password):
            score += 1
        else:
            feedback.append("Include lowercase letters")

        if re.search(r"[A-Z]", password):
            score += 1
        else:
            feedback.append("Include uppercase letters")

        if re.search(r"\d", password):
            score += 1
        else:
            feedback.append("Include numbers")

        if re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            score += 1
        else:
            feedback.append("Include special characters")

        # Common password check
        common_passwords = ["password", "123456", "qwerty", "admin", "letmein"]
        if password.lower() in common_passwords:
            score = 0
            feedback = ["This is a very common password"]

        # Determine strength level
        if score >= 5:
            strength = "strong"
        elif score >= 3:
            strength = "medium"
        else:
            strength = "weak"

        return {
            "strength": strength,
            "score": score,
            "max_score": 6,
            "feedback": feedback,
            "is_acceptable": strength in ["medium", "strong"],
        }

    def generate_security_report(self, hours: int = 24) -> Dict[str, any]:
        """
        Generate comprehensive security report

        Args:
            hours: Time period for report

        Returns:
            Security report data
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        # Filter recent suspicious requests
        recent_requests = [
            req for req in self.suspicious_requests
            if datetime.fromisoformat(req["timestamp"]) > cutoff_time
        ]

        # Analyze threats by type
        threat_types = defaultdict(int)
        risk_levels = defaultdict(int)
        client_ips = defaultdict(int)

        for req in recent_requests:
            for threat in req["threats"]:
                threat_types[threat["type"]] += 1
            risk_levels[req["risk_level"]] += 1
            client_ips[req["client_ip"]] += 1

        # Get most active malicious IPs
        top_malicious_ips = sorted(
            client_ips.items(), key=lambda x: x[1], reverse=True
        )[:10]

        return {
            "report_period_hours": hours,
            "total_suspicious_requests": len(recent_requests),
            "threat_breakdown": dict(threat_types),
            "risk_level_breakdown": dict(risk_levels),
            "top_malicious_ips": top_malicious_ips,
            "security_events": recent_requests[-20:],  # Last 20 events
            "recommendations": self._generate_security_recommendations(
                threat_types, risk_levels, top_malicious_ips
            ),
        }

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded headers (behind proxy/load balancer)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP in case of multiple
            return forwarded_for.split(",")[0].strip()

        # Check other proxy headers
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fallback to direct client
        if hasattr(request.client, 'host'):
            return request.client.host

        return "unknown"

    def _is_unusual_request_pattern(self, method: str, path: str, client_ip: str) -> bool:
        """Check if request pattern is unusual"""
        # This is a simplified check - in production you'd use ML/anomaly detection
        suspicious_paths = [
            "/wp-admin", "/admin", "/phpmyadmin", "/.env", "/.git",
            "/backup", "/config", "/database", "/dump"
        ]

        if any(suspicious_path in path.lower() for suspicious_path in suspicious_paths):
            return True

        # Check for unusual HTTP methods
        unusual_methods = ["TRACE", "TRACK", "CONNECT"]
        if method.upper() in unusual_methods:
            return True

        return False

    def _calculate_risk_level(self, risk_score: int) -> str:
        """Calculate risk level from score"""
        if risk_score >= 50:
            return "critical"
        elif risk_score >= 20:
            return "high"
        elif risk_score >= 10:
            return "medium"
        elif risk_score >= 5:
            return "low"
        else:
            return "none"

    def _get_recommended_action(self, risk_level: str) -> str:
        """Get recommended action based on risk level"""
        actions = {
            "critical": "Block request and alert security team",
            "high": "Block request and log incident",
            "medium": "Log request and monitor user",
            "low": "Log request for analysis",
            "none": "Allow request",
        }
        return actions.get(risk_level, "Allow request")

    def _log_suspicious_activity(
        self, client_ip: str, user_id: Optional[str], threats: List[Dict], risk_level: str
    ):
        """Log suspicious activity"""
        logger.warning(
            f"Suspicious activity detected: IP={client_ip}, User={user_id}, "
            f"Risk={risk_level}, Threats={len(threats)}"
        )

        # In production, you might send alerts to security team
        if risk_level in ["critical", "high"]:
            # Send alert (email, Slack, etc.)
            pass

    def _cleanup_expired_blocks(self):
        """Clean up expired account blocks"""
        now = datetime.utcnow()
        expired_keys = [
            key for key, attempt in self.failed_login_attempts.items()
            if attempt["blocked_until"] and attempt["blocked_until"] <= now
        ]

        for key in expired_keys:
            del self.failed_login_attempts[key]

    def _generate_security_recommendations(
        self, threat_types: Dict, risk_levels: Dict, top_ips: List
    ) -> List[str]:
        """Generate security recommendations based on threat analysis"""
        recommendations = []

        # SQL injection recommendations
        if threat_types.get("sql_injection", 0) > 0:
            recommendations.append(
                "Implement prepared statements and input sanitization for all database queries"
            )

        # XSS recommendations
        if threat_types.get("xss", 0) > 0:
            recommendations.append(
                "Implement Content Security Policy (CSP) and input validation for all user inputs"
            )

        # High risk recommendations
        if risk_levels.get("critical", 0) > 0 or risk_levels.get("high", 0) > 0:
            recommendations.append(
                "Immediate security review required - critical/high risk threats detected"
            )

        # IP blocking recommendations
        if len(top_ips) > 0:
            recommendations.append(
                f"Consider blocking or rate-limiting top malicious IPs: {', '.join(ip for ip, _ in top_ips[:3])}"
            )

        # General recommendations
        if not recommendations:
            recommendations.append("Security posture is good - continue monitoring")

        recommendations.append("Regular security audits and penetration testing recommended")
        recommendations.append("Keep security signatures and threat intelligence updated")

        return recommendations


# Global security service instance
security_service = SecurityService()