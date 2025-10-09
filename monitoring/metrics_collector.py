#!/usr/bin/env python3
"""
ENVOYOU SEC API - Metrics Collector Service
Collects and forwards metrics to monitoring systems
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, Optional

import requests
from prometheus_client import CollectorRegistry, Gauge, Counter, Histogram, push_to_gateway
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MetricsCollector:
    """Collect and forward application metrics"""

    def __init__(self):
        self.api_base_url = os.getenv('API_BASE_URL', 'https://api.envoyou.com')
        self.metrics_interval = int(os.getenv('METRICS_INTERVAL', '30'))
        self.pushgateway_url = os.getenv('PROMETHEUS_PUSHGATEWAY_URL')

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

        # Prometheus registry for custom metrics
        self.registry = CollectorRegistry()

        # Custom metrics
        self.api_response_time = Histogram(
            'envoyou_api_response_time_seconds',
            'API endpoint response time',
            ['endpoint', 'method', 'status'],
            registry=self.registry
        )

        self.api_requests_total = Counter(
            'envoyou_api_requests_total',
            'Total API requests',
            ['endpoint', 'method', 'status'],
            registry=self.registry
        )

        self.health_status = Gauge(
            'envoyou_health_status',
            'Application health status (1=healthy, 0=unhealthy)',
            registry=self.registry
        )

        self.database_connections = Gauge(
            'envoyou_database_connections_active',
            'Number of active database connections',
            registry=self.registry
        )

        self.redis_connections = Gauge(
            'envoyou_redis_connections_active',
            'Redis connection status (1=connected, 0=disconnected)',
            registry=self.registry
        )

    def collect_api_metrics(self) -> Dict:
        """Collect metrics from API endpoints"""
        metrics = {}

        try:
            # Get Prometheus metrics from /metrics endpoint
            metrics_response = self.session.get(
                f"{self.api_base_url}/metrics",
                timeout=10
            )

            if metrics_response.status_code == 200:
                metrics['prometheus_raw'] = metrics_response.text
                logger.debug("Successfully collected Prometheus metrics")
            else:
                logger.warning(f"Failed to get metrics: {metrics_response.status_code}")

            # Get detailed health status
            health_response = self.session.get(
                f"{self.api_base_url}/health/detailed",
                timeout=10
            )

            if health_response.status_code == 200:
                health_data = health_response.json()
                metrics['health_status'] = health_data

                # Update health gauge
                self.health_status.set(1 if health_data.get('status') == 'healthy' else 0)

                # Update database connections if available
                if 'database' in health_data:
                    db_status = health_data['database']
                    if 'connections' in db_status:
                        self.database_connections.set(db_status['connections'])

                # Update Redis status if available
                if 'redis' in health_data:
                    redis_status = health_data['redis']
                    self.redis_connections.set(1 if redis_status.get('status') == 'connected' else 0)

                logger.debug("Successfully collected health metrics")
            else:
                logger.warning(f"Failed to get health status: {health_response.status_code}")
                self.health_status.set(0)

        except requests.exceptions.RequestException as e:
            logger.error(f"Error collecting metrics: {str(e)}")
            self.health_status.set(0)

        return metrics

    def test_api_endpoints(self):
        """Test key API endpoints and collect response time metrics"""
        endpoints_to_test = [
            ('GET', '/health'),
            ('GET', '/v1/auth/permissions'),  # This will fail auth but we measure response time
        ]

        for method, endpoint in endpoints_to_test:
            try:
                start_time = time.time()
                response = self.session.request(
                    method=method,
                    url=f"{self.api_base_url}{endpoint}",
                    timeout=10
                )
                response_time = time.time() - start_time

                # Record metrics
                self.api_response_time.labels(
                    endpoint=endpoint,
                    method=method,
                    status=str(response.status_code)
                ).observe(response_time)

                self.api_requests_total.labels(
                    endpoint=endpoint,
                    method=method,
                    status=str(response.status_code)
                ).inc()

                logger.debug(f"Endpoint {method} {endpoint}: {response.status_code} in {response_time:.3f}s")

            except requests.exceptions.RequestException as e:
                logger.warning(f"Failed to test endpoint {method} {endpoint}: {str(e)}")

                # Record failed request
                self.api_requests_total.labels(
                    endpoint=endpoint,
                    method=method,
                    status='error'
                ).inc()

    def push_metrics_to_gateway(self):
        """Push metrics to Prometheus Pushgateway if configured"""
        if not self.pushgateway_url:
            return

        try:
            push_to_gateway(
                self.pushgateway_url,
                job='envoyou-metrics-collector',
                registry=self.registry
            )
            logger.debug("Successfully pushed metrics to gateway")
        except Exception as e:
            logger.error(f"Failed to push metrics to gateway: {str(e)}")

    def save_metrics_locally(self, metrics: Dict):
        """Save metrics to local file for debugging"""
        try:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"metrics_{timestamp}.json"

            with open(f"/tmp/{filename}", 'w') as f:
                json.dump(metrics, f, indent=2, default=str)

            logger.debug(f"Saved metrics to /tmp/{filename}")
        except Exception as e:
            logger.warning(f"Failed to save metrics locally: {str(e)}")

    def run_collection_loop(self):
        """Main metrics collection loop"""
        logger.info(f"Starting metrics collection for {self.api_base_url}")
        logger.info(f"Collection interval: {self.metrics_interval} seconds")
        logger.info(f"Pushgateway: {'configured' if self.pushgateway_url else 'not configured'}")

        while True:
            try:
                # Collect metrics
                metrics = self.collect_api_metrics()

                # Test endpoints for response time metrics
                self.test_api_endpoints()

                # Push to gateway if configured
                self.push_metrics_to_gateway()

                # Save locally for debugging (optional)
                if os.getenv('SAVE_METRICS_LOCALLY', 'false').lower() == 'true':
                    self.save_metrics_locally(metrics)

                logger.info("Metrics collection cycle completed")

                # Wait for next collection
                time.sleep(self.metrics_interval)

            except KeyboardInterrupt:
                logger.info("Metrics collection stopped by user")
                break
            except Exception as e:
                logger.error(f"Metrics collection error: {str(e)}")
                time.sleep(self.metrics_interval)

if __name__ == "__main__":
    collector = MetricsCollector()
    collector.run_collection_loop()