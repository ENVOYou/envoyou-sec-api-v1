#!/bin/bash

# ENVOYOU SEC API - Monitoring Deployment Script
# Deploys the complete monitoring stack to Render

set -e

echo "🚀 ENVOYOU SEC API - Monitoring Deployment"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if render CLI is installed
if ! command -v render &> /dev/null; then
    echo -e "${RED}❌ Render CLI not found. Please install it first:${NC}"
    echo "   npm install -g render-cli"
    echo "   or visit: https://render.com/docs/cli"
    exit 1
fi

# Check if logged in to Render
if ! render whoami &> /dev/null; then
    echo -e "${RED}❌ Not logged in to Render. Please login first:${NC}"
    echo "   render login"
    exit 1
fi

echo -e "${BLUE}📋 Deployment Options:${NC}"
echo "1. Deploy all monitoring services (Production)"
echo "2. Deploy API only"
echo "3. Deploy monitoring services only"
echo "4. Deploy staging environment"
echo ""

read -p "Choose deployment option (1-4): " choice

case $choice in
    1)
        echo -e "${GREEN}🚀 Deploying complete monitoring stack (Production)...${NC}"
        render deploy render-monitoring.yaml --environment production
        ;;
    2)
        echo -e "${GREEN}🚀 Deploying API service only...${NC}"
        render deploy -f render-monitoring.yaml envoyou-sec-api
        ;;
    3)
        echo -e "${GREEN}🚀 Deploying monitoring services only...${NC}"
        render deploy -f render-monitoring.yaml envoyou-log-monitor
        render deploy -f render-monitoring.yaml envoyou-metrics-collector
        render deploy -f render-monitoring.yaml envoyou-health-checker
        ;;
    4)
        echo -e "${GREEN}🚀 Deploying staging environment...${NC}"
        render deploy render-monitoring.yaml --environment staging
        ;;
    *)
        echo -e "${RED}❌ Invalid option. Exiting.${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✅ Deployment initiated!${NC}"
echo ""
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo "1. Check Render dashboard for deployment status"
echo "2. Configure environment variables:"
echo "   - ALERT_WEBHOOK_URL (for Slack/Discord alerts)"
echo "   - PROMETHEUS_PUSHGATEWAY_URL (optional)"
echo "   - Email settings (optional)"
echo "3. Monitor logs in Render dashboard"
echo "4. Test health endpoints:"
echo "   - https://your-service.render.com/health"
echo "   - https://your-service.render.com/health/detailed"
echo ""

echo -e "${BLUE}🔗 Useful Links:${NC}"
echo "- Render Dashboard: https://dashboard.render.com"
echo "- Monitoring README: ./monitoring/README.md"
echo "- API Documentation: https://your-service.render.com/docs"
echo ""

echo -e "${GREEN}🎉 Happy monitoring!${NC}"
