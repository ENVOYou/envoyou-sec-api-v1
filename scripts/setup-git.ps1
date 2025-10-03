# ENVOYOU SEC API - Git Repository Setup Script (PowerShell)
# This script initializes the Git repository and prepares for GitHub publishing

Write-Host "🚀 Setting up Git repository for ENVOYOU SEC API..." -ForegroundColor Green

# Check if Git is installed
try {
    git --version | Out-Null
    Write-Host "✅ Git is installed" -ForegroundColor Green
} catch {
    Write-Host "❌ Git is not installed. Please install Git first: https://git-scm.com/" -ForegroundColor Red
    exit 1
}

# Initialize Git repository if not already initialized
if (-not (Test-Path ".git")) {
    Write-Host "📁 Initializing Git repository..." -ForegroundColor Yellow
    git init
    Write-Host "✅ Git repository initialized" -ForegroundColor Green
} else {
    Write-Host "📁 Git repository already exists" -ForegroundColor Yellow
}

# Add all files to Git
Write-Host "📦 Adding files to Git..." -ForegroundColor Yellow
git add .

# Check if there are any changes to commit
$changes = git diff --staged --name-only
if ($changes) {
    # Commit initial files
    Write-Host "💾 Creating initial commit..." -ForegroundColor Yellow
    
    $commitMessage = @"
🎉 Initial commit: ENVOYOU SEC API

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

Target: Mid-cap US public companies for SEC Climate Disclosure compliance
"@

    git commit -m $commitMessage
    Write-Host "✅ Initial commit created" -ForegroundColor Green
} else {
    Write-Host "ℹ️  No changes to commit" -ForegroundColor Blue
}

# Set up main branch
Write-Host "🌿 Setting up main branch..." -ForegroundColor Yellow
git branch -M main

Write-Host ""
Write-Host "🎉 Git repository setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Next steps to publish to GitHub:" -ForegroundColor Cyan
Write-Host "1. Create a new repository on GitHub: https://github.com/new" -ForegroundColor White
Write-Host "2. Repository name: envoyou-sec-api" -ForegroundColor White
Write-Host "3. Description: Climate Disclosure Rule Compliance Platform for US Public Companies" -ForegroundColor White
Write-Host "4. Make it public or private as needed" -ForegroundColor White
Write-Host "5. Don't initialize with README (we already have one)" -ForegroundColor White
Write-Host ""
Write-Host "6. Then run these commands:" -ForegroundColor Cyan
Write-Host "   git remote add origin https://github.com/YOUR_USERNAME/envoyou-sec-api.git" -ForegroundColor Yellow
Write-Host "   git push -u origin main" -ForegroundColor Yellow
Write-Host ""
Write-Host "🔧 Optional: Set up GitHub repository settings:" -ForegroundColor Cyan
Write-Host "   - Enable branch protection for main branch" -ForegroundColor White
Write-Host "   - Require pull request reviews" -ForegroundColor White
Write-Host "   - Enable status checks (CI/CD)" -ForegroundColor White
Write-Host "   - Set up GitHub Pages for documentation" -ForegroundColor White
Write-Host ""
Write-Host "🚀 Your ENVOYOU SEC API is ready for GitHub!" -ForegroundColor Green

# Show current Git status
Write-Host ""
Write-Host "📊 Current Git Status:" -ForegroundColor Cyan
git status --short