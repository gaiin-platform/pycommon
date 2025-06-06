#!/usr/bin/env bash

# Exit on any error
set -e

echo "🔧 Setting up pre-commit hooks for this repository..."

# Check for virtualenv and pip
if ! command -v pip &> /dev/null; then
    echo "❌ pip is not installed. Please install Python and pip first."
    exit 1
fi

# Ensure pre-commit is installed
pip install --upgrade pre-commit

# Install the pre-commit hooks
pre-commit install

echo "✅ Pre-commit hooks installed successfully!"

# Optional: Run hooks on all files to catch up
echo "🎯 Running hooks on all existing files..."
pre-commit run --all-files

echo "🎉 All done!"
