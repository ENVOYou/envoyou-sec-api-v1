#!/usr/bin/env python3
"""
ENVOYOU SEC API - Health Checker Service
Comprehensive health monitoring with external dependency checks
"""

import json
import logging
import os
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class HealthChecker:
    """Comprehensive health checker for all system components"""

    def __init__(self):
        self.api_base_url = os.getenv("API_BASE_URL", "https://api.envoyou.com")
        self.check_interval = int(os.getenv("HEALTH_CHECK_INTERVAL", "30"))
        self.alert_webhook_url = os.getenv("ALERT_WEBHOOK_URL")

        # Email configuration (optional)
        self.smtp_server = os.getenv("SMTP_SERVER")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.alert_email_from = os.getenv("ALERT_EMAIL_FROM")
        self.alert_email_to = os.getenv("ALERT_EMAIL_TO")

        # Health check history
        self.last_status = {}
        self.consecutive_failures = {}
        self.max_consecutive_failures = 3

        # HTTP session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3, status_forcelist=[429, 500, 502, 503, 504], backoff_factor=1
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def check_api_health(self) -> Dict:
        """Check API health and responsiveness"""
        try:
            response = self.session.get(f"{self.api_base_url}/health", timeout=10)

            if response.status_code == 200:
                data = response.json()
                return {
                    "component": "api",
                    "status": "healthy",
                    "response_time": response.elapsed.total_seconds(),
                    "version": data.get("version"),
                    "environment": data.get("environment"),
                    "timestamp": data.get("timestamp"),
                }
            else:
                return {
                    "component": "api",
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}",
                    "response": response.text[:200],
                }

        except requests.exceptions.RequestException as e:
            return {"component": "api", "status": "unhealthy", "error": str(e)}

    def check_detailed_health(self) -> Dict:
        """Check detailed health with dependency verification"""
        try:
            response = self.session.get(
                f"{self.api_base_url}/health/detailed", timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "component": "detailed_health",
                    "status": (
                        "healthy" if data.get("status") == "healthy" else "degraded"
                    ),
                    "database": data.get("database", {}),
                    "redis": data.get("redis", {}),
                    "external_apis": data.get("external_apis", {}),
                    "response_time": response.elapsed.total_seconds(),
                }
            else:
                return {
                    "component": "detailed_health",
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}",
                }

        except requests.exceptions.RequestException as e:
            return {
                "component": "detailed_health",
                "status": "unhealthy",
                "error": str(e),
            }

    def check_external_dependencies(self) -> List[Dict]:
        """Check external dependencies like Cloudflare, databases"""
        results = []

        # Check Cloudflare status page
        try:
            cf_response = self.session.get(
                "https://www.cloudflarestatus.com/", timeout=10
            )
            results.append(
                {
                    "component": "cloudflare",
                    "status": (
                        "healthy" if cf_response.status_code == 200 else "unhealthy"
                    ),
                    "response_time": cf_response.elapsed.total_seconds(),
                }
            )
        except Exception as e:
            results.append(
                {"component": "cloudflare", "status": "unhealthy", "error": str(e)}
            )

        # Check Neon PostgreSQL status
        try:
            neon_response = self.session.get("https://status.neon.tech/", timeout=10)
            results.append(
                {
                    "component": "neon_postgresql",
                    "status": (
                        "healthy"
                        if neon_response.status_code in [200, 301]
                        else "unhealthy"
                    ),
                    "response_time": neon_response.elapsed.total_seconds(),
                }
            )
        except Exception as e:
            results.append(
                {"component": "neon_postgresql", "status": "unhealthy", "error": str(e)}
            )

        # Check Upstash Redis status
        try:
            upstash_response = self.session.get(
                "https://status.upstash.com/", timeout=10
            )
            results.append(
                {
                    "component": "upstash_redis",
                    "status": (
                        "healthy"
                        if upstash_response.status_code == 200
                        else "unhealthy"
                    ),
                    "response_time": upstash_response.elapsed.total_seconds(),
                }
            )
        except Exception as e:
            results.append(
                {"component": "upstash_redis", "status": "unhealthy", "error": str(e)}
            )

        return results

    def check_ssl_certificate(self) -> Dict:
        """Check SSL certificate validity"""
        try:
            response = self.session.get(self.api_base_url, timeout=10)
            cert_info = response.raw.connection.sock.getpeercert()

            if cert_info:
                import ssl
                from datetime import datetime

                expiry_date = datetime.strptime(
                    cert_info["notAfter"], "%b %d %H:%M:%S %Y %Z"
                )
                days_until_expiry = (expiry_date - datetime.utcnow()).days

                return {
                    "component": "ssl_certificate",
                    "status": (
                        "healthy"
                        if days_until_expiry > 30
                        else "warning" if days_until_expiry > 7 else "critical"
                    ),
                    "days_until_expiry": days_until_expiry,
                    "issuer": dict(cert_info["issuer"]),
                    "subject": dict(cert_info["subject"]),
                }
            else:
                return {
                    "component": "ssl_certificate",
                    "status": "unhealthy",
                    "error": "No certificate found",
                }

        except Exception as e:
            return {
                "component": "ssl_certificate",
                "status": "unhealthy",
                "error": str(e),
            }

    def analyze_health_results(self, results: List[Dict]) -> Dict:
        """Analyze all health check results and determine overall status"""
        overall_status = "healthy"
        issues = []
        warnings = []

        for result in results:
            component = result["component"]
            status = result["status"]

            # Track status changes
            previous_status = self.last_status.get(component)
            if previous_status != status:
                if status in ["unhealthy", "critical"]:
                    issues.append(f"{component}: {status}")
                    overall_status = "unhealthy"
                elif status == "warning":
                    warnings.append(f"{component}: {status}")
                    if overall_status == "healthy":
                        overall_status = "warning"

            self.last_status[component] = status

            # Track consecutive failures
            if status in ["unhealthy", "critical"]:
                self.consecutive_failures[component] = (
                    self.consecutive_failures.get(component, 0) + 1
                )
            else:
                self.consecutive_failures[component] = 0

        return {
            "overall_status": overall_status,
            "issues": issues,
            "warnings": warnings,
            "results": results,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def send_alert(self, alert_data: Dict):
        """Send alert via webhook or email"""
        if self.alert_webhook_url:
            self._send_webhook_alert(alert_data)
        elif self.smtp_server and self.alert_email_to:
            self._send_email_alert(alert_data)

    def _send_webhook_alert(self, alert_data: Dict):
        """Send alert via webhook"""
        try:
            payload = {
                "service": "envoyou-health-checker",
                "alert": alert_data,
                "environment": os.getenv("RENDER_ENVIRONMENT", "unknown"),
                "service_id": os.getenv("RENDER_SERVICE_ID", "unknown"),
                "timestamp": datetime.utcnow().isoformat(),
            }

            response = self.session.post(
                self.alert_webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            if response.status_code == 200:
                logger.info("Health alert sent via webhook")
            else:
                logger.error(f"Failed to send webhook alert: {response.status_code}")

        except Exception as e:
            logger.error(f"Error sending webhook alert: {str(e)}")

    def _send_email_alert(self, alert_data: Dict):
        """Send alert via email"""
        try:
            msg = MIMEMultipart()
            msg["From"] = self.alert_email_from
            msg["To"] = self.alert_email_to
            msg["Subject"] = (
                f"ENVOYOU Health Alert: {alert_data['overall_status'].upper()}"
            )

            body = f"""
ENVOYOU SEC API Health Alert

Status: {alert_data['overall_status'].upper()}
Timestamp: {alert_data['timestamp']}

Issues:
{chr(10).join('- ' + issue for issue in alert_data.get('issues', []))}

Warnings:
{chr(10).join('- ' + warning for warning in alert_data.get('warnings', []))}

Environment: {os.getenv('RENDER_ENVIRONMENT', 'unknown')}
Service: {os.getenv('RENDER_SERVICE_ID', 'unknown')}
"""

            msg.attach(MIMEText(body, "plain"))

            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            text = msg.as_string()
            server.sendmail(self.alert_email_from, self.alert_email_to, text)
            server.quit()

            logger.info("Health alert sent via email")

        except Exception as e:
            logger.error(f"Error sending email alert: {str(e)}")

    def run_health_checks(self):
        """Run comprehensive health checks"""
        logger.info(f"Starting health checks for {self.api_base_url}")

        while True:
            try:
                # Perform all health checks
                results = []

                results.append(self.check_api_health())
                results.append(self.check_detailed_health())
                results.extend(self.check_external_dependencies())
                results.append(self.check_ssl_certificate())

                # Analyze results
                analysis = self.analyze_health_results(results)

                # Log status
                status_emoji = {"healthy": "✅", "warning": "⚠️", "unhealthy": "❌"}.get(
                    analysis["overall_status"], "❓"
                )

                logger.info(
                    f"{status_emoji} Health Status: {analysis['overall_status'].upper()}"
                )

                if analysis["issues"]:
                    logger.warning(f"Issues: {', '.join(analysis['issues'])}")

                if analysis["warnings"]:
                    logger.info(f"Warnings: {', '.join(analysis['warnings'])}")

                # Send alerts for critical issues
                if (
                    analysis["overall_status"] in ["unhealthy", "warning"]
                    and analysis["issues"]
                ):
                    self.send_alert(analysis)

                # Wait for next check
                time.sleep(self.check_interval)

            except KeyboardInterrupt:
                logger.info("Health checker stopped by user")
                break
            except Exception as e:
                logger.error(f"Health check error: {str(e)}")
                time.sleep(self.check_interval)


if __name__ == "__main__":
    checker = HealthChecker()
    checker.run_health_checks()
