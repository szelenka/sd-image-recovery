#!/bin/bash
# Install system and Python dependencies for SD Image Recovery Tool

set -e

echo "Installing SD Image Recovery Tool Dependencies"
echo "=============================================="

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "Error: This tool is designed for macOS only"
    exit 1
fi

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "Homebrew not found. Please install from https://brew.sh"
    exit 1
fi

echo ""
echo "Step 1: Installing PhotoRec (testdisk package)..."
if brew list testdisk &> /dev/null; then
    echo "  testdisk already installed"
else
    brew install testdisk
fi

# Verify PhotoRec installation
if command -v photorec &> /dev/null; then
    PHOTOREC_VERSION=$(photorec /version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
    echo "  PhotoRec $PHOTOREC_VERSION installed successfully"
else
    echo "  Error: PhotoRec not found after installation"
    exit 1
fi

echo ""
echo "Step 2: Setting up Python virtual environment..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  Virtual environment created"
else
    echo "  Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate

echo ""
echo "Step 3: Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Step 4: Installing development dependencies..."
pip install -r requirements-dev.txt

echo ""
echo "Step 5: Installing package in development mode..."
pip install -e .

echo ""
echo "=============================================="
echo "Installation Complete!"
echo "=============================================="
echo ""
echo "To activate the virtual environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To verify installation, run:"
echo "  sd-recovery check"
echo ""
echo "To see available commands, run:"
echo "  sd-recovery --help"
echo ""
echo "To run tests, run:"
echo "  pytest"
