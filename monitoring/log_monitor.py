#!/usr/bin/env python3
"""
ENVOYOU SEC API - Log Monitoring Service
Monitors application logs and sends alerts for critical issues
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LogMonitor:
    """Monitor application logs and send alerts"""

    def __init__(self):
        self.api_base_url = os.getenv('API_BASE_URL', 'https://api.envoyou.com')
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.monitor_interval = int(os.getenv('MONITOR_INTERVAL', '60'))
        self.alert_webhook_url = os.getenv('ALERT_WEBHOOK_URL')

        # Patterns to monitor
        self.error_patterns = [
            r'ERROR.*',
            r'CRITICAL.*',
            r'Exception.*',
            r'Traceback.*',
            r'500 Internal Server Error',
            r'502 Bad Gateway',
            r'503 Service Unavailable',
            r'Database connection failed',
            r'Redis connection failed',
        ]

        self.warning_patterns = [
            r'WARNING.*',
            r'429 Too Many Requests',
            r'Rate limit exceeded',
            r'Timeout',
        ]

        # Alert tracking
        self.last_alert_time = {}
        self.alert_cooldown = 300  # 5 minutes between similar alerts

        # HTTP session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def check_logs_via_api(self) -> Dict:
        """Check application logs via API endpoints"""
        try:
            # Check health endpoint for basic status
            health_response = self.session.get(
                f"{self.api_base_url}/health",
                timeout=10
            )

            if health_response.status_code != 200:
                return {
                    'status': 'error',
                    'message': f'Health check failed: {health_response.status_code}',
                    'details': health_response.text
                }

            # Check detailed health for more insights
            detailed_health = self.session.get(
                f"{self.api_base_url}/health/detailed",
                timeout=10
            )

            if detailed_health.status_code == 200:
                health_data = detailed_health.json()
                return {
                    'status': 'healthy' if health_data.get('status') == 'healthy' else 'warning',
                    'message': 'Application is responding',
                    'details': health_data
                }
            else:
                return {
                    'status': 'warning',
                    'message': 'Basic health OK but detailed check failed',
                    'details': f'Detailed health: {detailed_health.status_code}'
                }

        except requests.exceptions.RequestException as e:
            return {
                'status': 'error',
                'message': f'API connection failed: {str(e)}',
                'details': str(e)
            }

    def analyze_log_patterns(self, log_data: Dict) -> List[Dict]:
        """Analyze log data for patterns that need alerting"""
        alerts = []

        # Check for error conditions in health data
        if log_data.get('status') == 'error':
            alert_key = 'api_unhealthy'
            if self._should_alert(alert_key):
                alerts.append({
                    'level': 'CRITICAL',
                    'message': f'API Health Check Failed: {log_data.get("message", "Unknown error")}',
                    'details': log_data.get('details', ''),
                    'timestamp': datetime.utcnow().isoformat()
                })

        elif log_data.get('status') == 'warning':
            alert_key = 'api_warning'
            if self._should_alert(alert_key):
                alerts.append({
                    'level': 'WARNING',
                    'message': f'API Health Warning: {log_data.get("message", "Unknown warning")}',
                    'details': log_data.get('details', ''),
                    'timestamp': datetime.utcnow().isoformat()
                })

        return alerts

    def _should_alert(self, alert_key: str) -> bool:
        """Check if we should send an alert (cooldown logic)"""
        now = datetime.utcnow()
        last_alert = self.last_alert_time.get(alert_key)

        if last_alert is None or (now - last_alert).seconds > self.alert_cooldown:
            self.last_alert_time[alert_key] = now
            return True

        return False

    def send_alert(self, alert: Dict):
        """Send alert to configured webhook"""
        if not self.alert_webhook_url:
            logger.warning("No alert webhook configured, skipping alert")
            return

        try:
            payload = {
                'service': 'envoyou-sec-api-log-monitor',
                'alert': alert,
                'environment': os.getenv('RENDER_ENVIRONMENT', 'unknown'),
                'service_id': os.getenv('RENDER_SERVICE_ID', 'unknown')
            }

            response = self.session.post(
                self.alert_webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            if response.status_code == 200:
                logger.info(f"Alert sent successfully: {alert['level']} - {alert['message']}")
            else:
                logger.error(f"Failed to send alert: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"Error sending alert: {str(e)}")

    def run_monitoring_loop(self):
        """Main monitoring loop"""
        logger.info(f"Starting log monitoring for {self.api_base_url}")
        logger.info(f"Monitor interval: {self.monitor_interval} seconds")
        logger.info(f"Alert webhook: {'configured' if self.alert_webhook_url else 'not configured'}")

        while True:
            try:
                # Check application status
                log_data = self.check_logs_via_api()
                logger.info(f"Health check result: {log_data['status']}")

                # Analyze for alerts
                alerts = self.analyze_log_patterns(log_data)

                # Send alerts
                for alert in alerts:
                    logger.warning(f"Sending alert: {alert['level']} - {alert['message']}")
                    self.send_alert(alert)

                # Wait for next check
                time.sleep(self.monitor_interval)

            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Monitoring error: {str(e)}")
                time.sleep(self.monitor_interval)

if __name__ == "__main__":
    monitor = LogMonitor()
    monitor.run_monitoring_loop()