#!/bin/bash

# Setup script for PDF generation dependencies
# This script helps set up the required system dependencies for mkdocs-with-pdf

set -e

OS="$(uname -s)"

echo "Detected OS: $OS"

if [[ "$OS" == "Darwin" ]]; then
    echo "Setting up macOS dependencies..."
    
    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        echo "Error: Homebrew is not installed. Please install it from https://brew.sh"
        exit 1
    fi
    
    echo "Installing Homebrew packages..."
    brew install libffi cairo pango gdk-pixbuf libpng jpeg libtiff webp
    
    # Determine Homebrew prefix
    if [[ -d "/opt/homebrew" ]]; then
        HOMEBREW_PREFIX="/opt/homebrew"  # Apple Silicon
    else
        HOMEBREW_PREFIX="/usr/local"     # Intel
    fi
    
    echo ""
    echo "Setup complete! Add these to your shell profile (~/.zshrc or ~/.bash_profile):"
    echo ""
    echo "export PKG_CONFIG_PATH=\"$HOMEBREW_PREFIX/lib/pkgconfig:\$PKG_CONFIG_PATH\""
    echo "export DYLD_LIBRARY_PATH=\"$HOMEBREW_PREFIX/lib:\$DYLD_LIBRARY_PATH\""
    echo ""
    echo "Then reload your shell or run:"
    echo "source ~/.zshrc  # or source ~/.bash_profile"
    echo ""
    echo "After that, reinstall the Python packages:"
    echo "uv sync --reinstall-package mkdocs-with-pdf --reinstall-package weasyprint"
    echo "# Or using pip:"
    echo "pip install --upgrade --force-reinstall mkdocs-with-pdf weasyprint"
    
elif [[ "$OS" == "Linux" ]]; then
    echo "Setting up Linux dependencies..."
    
    # Detect Linux distribution
    if command -v apt-get &> /dev/null; then
        echo "Detected Debian/Ubuntu. Installing packages..."
        sudo apt-get update
        sudo apt-get install -y \
            python3-cffi \
            python3-brotli \
            libpango-1.0-0 \
            libpangoft2-1.0-0 \
            libharfbuzz0b \
            libcairo2 \
            libgdk-pixbuf2.0-0 \
            shared-mime-info
    elif command -v dnf &> /dev/null; then
        echo "Detected Fedora/RHEL/CentOS. Installing packages..."
        sudo dnf install -y \
            python3-cffi \
            python3-brotli \
            pango \
            cairo \
            gdk-pixbuf2 \
            shared-mime-info
    elif command -v yum &> /dev/null; then
        echo "Detected RHEL/CentOS (yum). Installing packages..."
        sudo yum install -y \
            python3-cffi \
            python3-brotli \
            pango \
            cairo \
            gdk-pixbuf2 \
            shared-mime-info
    else
        echo "Error: Unsupported Linux distribution. Please install dependencies manually."
        exit 1
    fi
    
    echo ""
    echo "Setup complete! Reinstall the Python packages:"
    echo "uv sync --reinstall-package mkdocs-with-pdf --reinstall-package weasyprint"
    echo "# Or using pip:"
    echo "pip install --upgrade --force-reinstall mkdocs-with-pdf weasyprint"
    
else
    echo "Error: Unsupported operating system: $OS"
    echo "Please install dependencies manually. See README.md for instructions."
    exit 1
fi

echo ""
echo "To verify the setup, run:"
echo "uv run python -c \"import weasyprint; print('WeasyPrint is available')\""
echo "# Or with activated environment:"
echo "python -c \"import weasyprint; print('WeasyPrint is available')\""

