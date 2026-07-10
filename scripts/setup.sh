#!/bin/bash
# Setup script for Nexus Personal AI System

set -euo pipefail

echo "🚀 Setting up Nexus Personal AI System..."

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required but not installed."; exit 1; }
command -v python3.11 >/dev/null 2>&1 || { echo "❌ Python 3.11+ is required but not installed."; exit 1; }

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3.11 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📚 Installing dependencies..."
pip install -e ".[dev]"

# Copy environment file
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env and set your credentials!"
fi

# Start infrastructure
echo "🐳 Starting Docker services..."
docker-compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 10

# Run database migrations
echo "🗄️  Running database migrations..."
alembic upgrade head

# Create initial user (interactive)
echo "👤 Let's create your admin account..."
python -c "
from nexus.cli.main import cli
import sys
sys.argv = ['nexus', 'auth', 'register']
cli()
"

echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "  1. Edit .env with your API keys (OpenRouter, Telegram, etc.)"
echo "  2. Start the backend: uvicorn nexus.api.main:app --reload"
echo "  3. Start the worker: celery -A nexus.workers.app worker --loglevel=info"
echo "  4. Access the API docs: http://localhost:8000/docs"
echo "  5. Use the CLI: nexus --help"
