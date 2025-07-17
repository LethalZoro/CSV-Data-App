#!/usr/bin/env bash
# Build script for Render

# Exit on any error
set -e

echo "🔧 Starting build process..."

# Upgrade pip to latest version
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p uploads
mkdir -p instance

# Verify critical files exist
echo "🔍 Verifying files..."
if [ ! -f "app.py" ]; then
    echo "❌ app.py not found!"
    exit 1
fi

if [ ! -f "templates/index.html" ]; then
    echo "❌ templates/index.html not found!"
    exit 1
fi

# Test import of main app
echo "🧪 Testing app import..."
python -c "import app; print('✅ App import successful')"

# Run comprehensive startup test
echo "🧪 Running startup tests..."
python test_startup.py

echo "✅ Build completed successfully!"
