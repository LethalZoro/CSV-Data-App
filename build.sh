#!/usr/bin/env bash
# Build script for Render

# Exit on any error
set -e

# Upgrade pip to latest version
pip install --upgrade pip

# Install Python dependencies
pip install -r requirements.txt

# Any additional build steps can go here
echo "Build completed successfully!"
