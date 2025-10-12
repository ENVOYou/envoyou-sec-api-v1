# ENVOYOU SEC API - Monitoring & Observability

Comprehensive monitoring setup for production deployment with log monitoring, metrics collection, and health checking.

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Log Monitor   │    │ Metrics Collector│    │ Health Checker │
│                 │    │                  │    │                 │
│ • Error logs    │    │ • Prometheus     │    │ • API health    │
│ • Alert webhook │    │ • Response times │    │ • Dependencies  │
│ • Cooldown      │    │ • Pushgateway    │    │ • SSL certs     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌────────────────────┐
                    │   Alert Systems    │
                    │                    │
                    │ • Slack/Discord    │
                    │ • Email alerts     │
                    │ • PagerDuty        │
                    └────────────────────┘
```

## Services

### 1. Log Monitor (`log_monitor.py`)
Monitors application logs and sends alerts for critical issues.

**Features:**
- Health check monitoring via API endpoints
- Error pattern detection
- Alert cooldown to prevent spam
- Webhook integration for alerts

**Environment Variables:**
```bash
API_BASE_URL=https://api.envoyou.com
LOG_LEVEL=INFO
MONITOR_INTERVAL=60
ALERT_WEBHOOK_URL=https://hooks.slack.com/...
```

### 2. Metrics Collector (`metrics_collector.py`)
Collects and forwards application metrics to monitoring systems.

**Features:**
- Prometheus metrics collection
- Custom application metrics
- Response time monitoring
- Pushgateway integration

**Environment Variables:**
```bash
API_BASE_URL=https://api.envoyou.com
METRICS_INTERVAL=30
PROMETHEUS_PUSHGATEWAY_URL=http://pushgateway:9091
SAVE_METRICS_LOCALLY=false
```

### 3. Health Checker (`health_checker.py`)
Comprehensive health monitoring with external dependency checks.

**Features:**
- API health verification
- Database connectivity checks
- External service monitoring (Cloudflare, Neon, Upstash)
- SSL certificate validation
- Email and webhook alerts

**Environment Variables:**
```bash
API_BASE_URL=https://api.envoyou.com
HEALTH_CHECK_INTERVAL=30
ALERT_WEBHOOK_URL=https://hooks.slack.com/...

# Email alerts (optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-password
ALERT_EMAIL_FROM=alerts@envoyou.com
ALERT_EMAIL_TO=admin@envoyou.com
```

## Deployment

### Render Configuration

Use `render-monitoring.yaml` for complete monitoring setup:

```bash
# Deploy all services
render deploy render-monitoring.yaml

# Or deploy individual services
render deploy -f render-monitoring.yaml envoyou-sec-api
render deploy -f render-monitoring.yaml envoyou-log-monitor
render deploy -f render-monitoring.yaml envoyou-metrics-collector
render deploy -f render-monitoring.yaml envoyou-health-checker
```

### Environment Groups

- **Production**: All monitoring services active
- **Staging**: API + Log Monitor + Health Checker only

## Alert Configuration

### Webhook Alerts (Recommended)

Set up webhooks in your preferred platform:

**Slack:**
1. Create webhook: https://api.slack.com/apps → Create app → Incoming Webhooks
2. Set `ALERT_WEBHOOK_URL` to the webhook URL

**Discord:**
1. Server Settings → Integrations → Webhooks
2. Set `ALERT_WEBHOOK_URL` to the webhook URL

### Email Alerts

Configure SMTP settings for email notifications:

```bash
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-alerts@gmail.com
SMTP_PASSWORD=app-password
ALERT_EMAIL_FROM=alerts@envoyou.com
ALERT_EMAIL_TO=admin@envoyou.com,dev@envoyou.com
```

## Metrics & Monitoring

### Prometheus Integration

The API exposes metrics at `/metrics` endpoint. Configure Prometheus:

```yaml
scrape_configs:
  - job_name: 'envoyou-sec-api'
    static_configs:
      - targets: ['your-render-service:10000']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

### Grafana Dashboards

Import the provided dashboard or create custom ones for:

- API Response Times
- Error Rates
- Health Status
- Database Connections
- External Service Status

## Health Check Endpoints

### Basic Health
```
GET /health
```
Returns basic service health status.

### Detailed Health
```
GET /health/detailed
```
Returns comprehensive health with dependency checks.

### Debug Information
```
GET /debug/db
```
Database connectivity and configuration info.

## Alert Types

### Critical Alerts 🚨
- API unresponsive (500+ consecutive failures)
- Database connection lost
- SSL certificate expiring (< 7 days)

### Warning Alerts ⚠️
- High response times (> 5 seconds)
- External service degradation
- SSL certificate expiring (< 30 days)

### Info Alerts ℹ️
- Service recovery
- Configuration changes
- Maintenance notifications

## Troubleshooting

### Common Issues

**Alerts not sending:**
- Check `ALERT_WEBHOOK_URL` is correctly set
- Verify webhook URL is accessible
- Check Render logs for authentication errors

**Metrics not collecting:**
- Ensure `/metrics` endpoint is accessible
- Check `PROMETHEUS_PUSHGATEWAY_URL` if using pushgateway
- Verify API is responding to health checks

**Health checks failing:**
- Check `API_BASE_URL` is correct
- Verify API service is running
- Check network connectivity between services

### Debug Mode

Enable debug logging:

```bash
LOG_LEVEL=DEBUG
SAVE_METRICS_LOCALLY=true
```

## Security Considerations

- All monitoring services run in isolated containers
- API keys and credentials are environment variables only
- No sensitive data is logged or exposed in metrics
- Webhook URLs should use HTTPS
- Email credentials should use app passwords, not main passwords

## Cost Optimization

- Adjust monitoring intervals based on needs:
  - Production: 30-60 seconds
  - Staging: 60-300 seconds
  - Development: Disabled

- Use webhook alerts instead of email for faster delivery
- Configure alert cooldown to prevent spam

## Maintenance

### Regular Tasks
- Monitor alert volumes and adjust thresholds
- Review and update alert rules quarterly
- Rotate webhook URLs annually
- Update SSL certificates before expiry

### Log Rotation
- Render automatically handles log rotation
- Access logs via Render dashboard
- Archive important logs for compliance

---

**For support:** Check Render service logs or contact the development team.
