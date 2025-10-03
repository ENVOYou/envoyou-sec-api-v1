#!/bin/bash

# ENVOYOU SEC API - Git Repository Setup Script
# This script initializes the Git repository and prepares for GitHub publishing

set -e

echo "🚀 Setting up Git repository for ENVOYOU SEC API..."

# Initialize Git repository if not already initialized
if [ ! -d ".git" ]; then
    echo "📁 Initializing Git repository..."
    git init
    echo "✅ Git repository initialized"
else
    echo "📁 Git repository already exists"
fi

# Create .gitignore if it doesn't exist
if [ ! -f ".gitignore" ]; then
    echo "📝 Creating .gitignore file..."
    cat > .gitignore << 'EOF'
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Environment variables
.env
.env.local
.env.production

# Database
*.db
*.sqlite
*.sqlite3

# Logs
logs/
*.log

# Storage
storage/
uploads/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Python
venv/
env/
.venv/
.pytest_cache/
.coverage
htmlcov/

# Docker
.dockerignore
EOF
    echo "✅ .gitignore created"
fi

# Add all files to Git
echo "📦 Adding files to Git..."
git add .

# Check if there are any changes to commit
if git diff --staged --quiet; then
    echo "ℹ️  No changes to commit"
else
    # Commit initial files
    echo "💾 Creating initial commit..."
    git commit -m "🎉 Initial commit: ENVOYOU SEC API

- FastAPI backend for SEC Climate Disclosure Rule compliance
- JWT authentication with role-based access control
- EPA emission factors data management system
- Redis caching with automated refresh mechanisms
- Comprehensive audit logging for SEC compliance
- Docker containerization and CI/CD pipeline
- Complete test suite and documentation

Features:
✅ Authentication & Authorization (CFO, General Counsel, Finance Team, Auditor, Admin)
✅ EPA Data Management (GHGRP, eGRID integration)
✅ Caching & Refresh System (Redis with TTL)
✅ Audit Trail System (Forensic-grade traceability)
✅ Database Models (PostgreSQL + TimescaleDB)
✅ API Endpoints (/v1/auth/*, /v1/emissions/*)
✅ Docker & CI/CD (GitHub Actions)
✅ Comprehensive Testing (pytest)
✅ Documentation (README, API docs)

Target: Mid-cap US public companies for SEC Climate Disclosure compliance"

    echo "✅ Initial commit created"
fi

# Set up main branch
echo "🌿 Setting up main branch..."
git branch -M main

echo ""
echo "🎉 Git repository setup complete!"
echo ""
echo "📋 Next steps to publish to GitHub:"
echo "1. Create a new repository on GitHub: https://github.com/new"
echo "2. Repository name: envoyou-sec-api"
echo "3. Description: Climate Disclosure Rule Compliance Platform for US Public Companies"
echo "4. Make it public or private as needed"
echo "5. Don't initialize with README (we already have one)"
echo ""
echo "6. Then run these commands:"
echo "   git remote add origin https://github.com/YOUR_USERNAME/envoyou-sec-api.git"
echo "   git push -u origin main"
echo ""
echo "🔧 Optional: Set up GitHub repository settings:"
echo "   - Enable branch protection for main branch"
echo "   - Require pull request reviews"
echo "   - Enable status checks (CI/CD)"
echo "   - Set up GitHub Pages for documentation"
echo ""
echo "🚀 Your ENVOYOU SEC API is ready for GitHub!"