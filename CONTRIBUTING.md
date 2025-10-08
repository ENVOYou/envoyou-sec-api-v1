# Contributing to ENVOYOU SEC API

Thank you for your interest in contributing to the ENVOYOU SEC API! This document provides guidelines and information for contributors.

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Contributing Guidelines](#contributing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Security](#security)

## Code of Conduct

This project adheres to a code of conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/envoyou-sec-api.git`
3. Create a feature branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Submit a pull request

## Development Setup

### Prerequisites
- Python 3.11+
- Docker and Docker Compose
- PostgreSQL 15+ with TimescaleDB
- Redis 7+

### Local Development
```bash
# Clone the repository
git clone https://github.com/yourusername/envoyou-sec-api.git
cd envoyou-sec-api

# Copy environment configuration
cp .env.example .env

# Start services
docker-compose up -d

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload
```

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_auth.py -v
```

## Contributing Guidelines

### Types of Contributions
- **Bug Reports**: Use the bug report template
- **Feature Requests**: Use the feature request template
- **Code Contributions**: Follow the pull request process
- **Documentation**: Improvements to README, API docs, etc.
- **Security**: Report security issues privately

### SEC Compliance Considerations
When contributing to this SEC compliance platform, please ensure:

1. **Audit Trail Integrity**: All changes maintain complete audit trails
2. **Data Validation**: EPA data validation rules are preserved
3. **Access Control**: Role-based permissions are maintained
4. **Data Retention**: 7+ year retention policies are followed
5. **Regulatory Alignment**: Changes align with SEC Climate Disclosure Rules

## Pull Request Process

1. **Create Feature Branch**: `git checkout -b feature/description`
2. **Make Changes**: Follow coding standards and add tests
3. **Test Thoroughly**: Ensure all tests pass
4. **Update Documentation**: Update relevant documentation
5. **Submit PR**: Use the pull request template
6. **Code Review**: Address reviewer feedback
7. **Merge**: Maintainer will merge after approval

### PR Requirements
- [ ] All tests pass
- [ ] Code coverage maintained (>90%)
- [ ] Documentation updated
- [ ] Security considerations addressed
- [ ] SEC compliance maintained

## Coding Standards

### Python Style
- Follow PEP 8
- Use Black for code formatting: `black app/`
- Use isort for import sorting: `isort app/`
- Use flake8 for linting: `flake8 app/`

### Code Organization
```
app/
├── api/v1/endpoints/     # API endpoints
├── core/                 # Core functionality
├── models/              # Database models
├── schemas/             # Pydantic schemas
├── services/            # Business logic
└── tests/               # Test files
```

### Naming Conventions
- **Files**: snake_case (e.g., `epa_service.py`)
- **Classes**: PascalCase (e.g., `EmissionFactor`)
- **Functions/Variables**: snake_case (e.g., `calculate_emissions`)
- **Constants**: UPPER_CASE (e.g., `EPA_API_BASE_URL`)

### Documentation
- Use docstrings for all functions and classes
- Include type hints
- Document complex business logic
- Update API documentation for endpoint changes

## Testing

### Test Structure
```
tests/
├── unit/                # Unit tests
├── integration/         # Integration tests
├── fixtures/            # Test fixtures
└── conftest.py         # Pytest configuration
```

### Test Requirements
- **Unit Tests**: Test individual functions/methods
- **Integration Tests**: Test API endpoints and database interactions
- **Security Tests**: Test authentication and authorization
- **Performance Tests**: Test under load conditions

### Test Data
- Use fixtures for test data
- Mock external API calls (EPA, etc.)
- Clean up test data after tests

## Security

### Security Guidelines
- **Authentication**: All endpoints require proper authentication
- **Authorization**: Implement role-based access control
- **Input Validation**: Validate all user inputs
- **SQL Injection**: Use parameterized queries
- **Secrets**: Never commit secrets to version control

### Reporting Security Issues
Please report security vulnerabilities privately to the maintainers. Do not create public issues for security problems.

### Security Testing
- Run security scans: `bandit -r app/`
- Test authentication flows
- Verify authorization controls
- Check for common vulnerabilities

## Database Changes

### Migrations
- Create migrations for schema changes: `alembic revision --autogenerate -m "description"`
- Test migrations on sample data
- Ensure backward compatibility when possible
- Document breaking changes

### Data Models
- Follow existing model patterns
- Include proper indexes for performance
- Add audit trail fields where appropriate
- Consider data retention requirements

## API Design

### RESTful Principles
- Use appropriate HTTP methods
- Follow consistent URL patterns
- Return appropriate status codes
- Include proper error messages

### Versioning
- All endpoints use `/v1/` prefix
- Maintain backward compatibility
- Document API changes

### Documentation
- Update OpenAPI/Swagger documentation
- Include request/response examples
- Document error responses

## Performance

### Guidelines
- Optimize database queries
- Use caching appropriately
- Monitor response times
- Consider pagination for large datasets

### Monitoring
- Add logging for important operations
- Include performance metrics
- Monitor EPA API integration

## Questions?

If you have questions about contributing, please:
1. Check existing issues and documentation
2. Create a discussion thread
3. Contact the maintainers

Thank you for contributing to ENVOYOU SEC API!
