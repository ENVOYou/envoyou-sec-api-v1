# ENVOYOU SEC API

Climate Disclosure Rule Compliance Platform for US Public Companies

## Overview

ENVOYOU SEC API is a specialized backend platform designed to help US public companies comply with the SEC Climate Disclosure Rule. The platform provides forensic-grade traceability for GHG emissions calculation, data validation against EPA databases, and automated SEC-compliant report generation.

## Key Features

- **GHG Emissions Calculator**: Accurate Scope 1 and Scope 2 emissions calculation using latest EPA emission factors
- **EPA Cross-Validation**: Automatic comparison against EPA GHGRP database for data consistency
- **SEC-Compliant Reporting**: Automated 10-K climate disclosure report generation
- **Forensic Audit Trails**: Complete data lineage and audit logging for regulatory compliance
- **Multi-Entity Support**: Consolidation capabilities for subsidiaries and complex corporate structures
- **Role-Based Access**: Secure access control for CFOs, General Counsel, Finance Teams, and Auditors

## Technology Stack

- **Framework**: FastAPI with Python 3.11+
- **Database**: PostgreSQL with TimescaleDB extension
- **Cache**: Redis for EPA data caching
- **Authentication**: JWT tokens with role-based access control
- **Monitoring**: Prometheus metrics with Grafana dashboards
- **Deployment**: Docker containers with Kubernetes support

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- PostgreSQL 15+ with TimescaleDB extension
- Redis 7+

### Development Setup

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd envoyou-sec-api
   ```

2. **Copy environment configuration**

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start services with Docker Compose**

   ```bash
   docker-compose up -d
   ```

4. **Run database migrations**

   ```bash
   docker-compose exec api alembic upgrade head
   ```

5. **Access the application**
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health
   - Grafana Dashboard: http://localhost:3000 (admin/admin)
   - Prometheus Metrics: http://localhost:9090

### Local Development

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Set up database**

   ```bash
   # Start PostgreSQL and Redis
   docker-compose up -d db redis

   # Run migrations
   alembic upgrade head
   ```

3. **Start development server**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## API Documentation

### Authentication Endpoints

- `POST /v1/auth/login` - User authentication
- `POST /v1/auth/refresh` - Token refresh
- `GET /v1/auth/permissions` - User permissions

### Emissions Calculation

- `POST /v1/emissions/calculate` - Calculate emissions from input data
- `GET /v1/emissions/factors` - Retrieve EPA emission factors
- `GET /v1/emissions/calculation/{id}` - Get calculation with audit trail

### Data Validation

- `POST /v1/validation/validate` - Validate against EPA GHGRP
- `GET /v1/validation/report/{company_id}` - Get validation report

### Report Generation

- `POST /v1/reports/generate` - Generate SEC-compliant report
- `GET /v1/reports/{report_id}/download` - Download report

### Audit Trail

- `GET /v1/audit/trail/{entity_id}` - Get audit trail
- `GET /v1/audit/lineage/{calculation_id}` - Get data provenance

## Configuration

Key environment variables:

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:port/db
REDIS_URL=redis://host:port/db

# Security
SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256

# EPA API
EPA_API_BASE_URL=https://api.epa.gov
EPA_API_KEY=your-api-key
```

## Monitoring

The application includes comprehensive monitoring:

- **Prometheus Metrics**: Application performance and business metrics
- **Grafana Dashboards**: Visual monitoring and alerting
- **Health Checks**: Endpoint monitoring for uptime tracking
- **Audit Logging**: Complete request/response logging for compliance

## Security

- JWT-based authentication with role-based access control
- Data encryption at rest and in transit
- Rate limiting and DDoS protection
- Comprehensive audit logging
- Input validation and sanitization

## Compliance

The platform is designed for SEC Climate Disclosure Rule compliance:

- Forensic-grade audit trails for all calculations
- EPA emission factor integration with version tracking
- SEC-compliant report formatting
- Data retention policies for 7+ year compliance
- External auditor access controls

## Development

### Running Tests

```bash
pytest tests/ -v --cov=app
```

### Code Formatting

```bash
black app/
isort app/
flake8 app/
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## Deployment

### Production Deployment

1. **Build production image**

   ```bash
   docker build -t envoyou-sec-api:latest .
   ```

2. **Deploy with Kubernetes**

   ```bash
   kubectl apply -f k8s/
   ```

3. **Configure monitoring**
   - Set up Prometheus scraping
   - Configure Grafana dashboards
   - Set up alerting rules

## Support

For technical support and questions:

- Documentation: `/docs` endpoint
- Health Status: `/health` endpoint
- Monitoring: Grafana dashboards

## License

Proprietary - ENVOYOU SEC API Platform
