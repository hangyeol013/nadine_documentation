# Nadine Documentation

Documentation for the Nadine social robot project, built with MkDocs.

## Installation

### Prerequisites

This project uses [uv](https://github.com/astral-sh/uv) for Python package management. Install uv if you haven't already:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Python Dependencies

Install the required Python packages using uv:

```bash
uv sync
```

Alternatively, if you prefer using pip:

```bash
pip install -r requirements.txt
```

### System Dependencies for PDF Generation

`mkdocs-with-pdf` requires additional system libraries for PDF generation. These are **optional** - MkDocs will work fine without them, but PDF generation will be disabled.

**Quick Setup:** Run the automated setup script:
```bash
./setup_pdf_deps.sh
```

Or follow the manual instructions below:

#### macOS

Install dependencies via Homebrew:

```bash
brew install libffi cairo pango gdk-pixbuf libpng jpeg libtiff webp
```

After installation, you may need to set environment variables for the libraries to be found:

```bash
export PKG_CONFIG_PATH="/opt/homebrew/lib/pkgconfig:$PKG_CONFIG_PATH"
export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"
```

**Note:** With uv, system libraries installed via Homebrew should work directly. No additional conda packages are needed.

#### Linux (Ubuntu/Debian)

```bash
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
```

#### Linux (Fedora/RHEL/CentOS)

```bash
sudo dnf install -y \
    python3-cffi \
    python3-brotli \
    pango \
    cairo \
    gdk-pixbuf2 \
    shared-mime-info
```

#### Windows

Follow the [WeasyPrint installation guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows)

### Verifying PDF Dependencies

To verify that PDF dependencies are correctly installed, try:

```bash
# Using uv (recommended)
uv run python -c "import weasyprint; print('WeasyPrint is available')"

# Or with activated environment
python -c "import weasyprint; print('WeasyPrint is available')"
```

If this command succeeds, PDF generation will work. If it fails, MkDocs will still work but PDF generation will be skipped.

## Usage

### Building the Documentation Site

```bash
# Using uv (recommended - uses the virtual environment automatically)
uv run mkdocs build

# Or activate the environment first
uv sync
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
mkdocs build
```

### Serving Locally

```bash
# Using uv (recommended)
uv run mkdocs serve

# Or with activated environment
mkdocs serve
```

### Generating PDF

**Note:** PDF generation requires the system dependencies listed above. If they are not installed, MkDocs will build successfully but skip PDF generation.

The PDF will be automatically generated when you run `mkdocs build` (if dependencies are available). The PDF file will be created in the `site` directory as `document.pdf` (or the path specified in `mkdocs.yml`).

```bash
mkdocs build
```

If PDF dependencies are correctly installed, you should see a message like:
```
Converting X articles to PDF took X.Xs
```

If dependencies are missing, the build will complete successfully but without generating a PDF.

The generated PDF will include:
- Cover page with title and author information
- Table of Contents
- All documentation pages with proper heading numbering
- Automatically adjusted heading levels for sub-pages

### Troubleshooting PDF Generation

#### Error: `cannot load library 'libpango-1.0-0'` (macOS)

This error occurs because WeasyPrint can't find the required system libraries. Follow these steps:

1. **Install Homebrew dependencies** (if not already installed):
   ```bash
   brew install libffi cairo pango gdk-pixbuf libpng jpeg libtiff webp
   ```

2. **Set environment variables** in your shell profile (`~/.zshrc` for zsh or `~/.bash_profile` for bash):
   ```bash
   # For Apple Silicon Macs (M1/M2/M3)
   export PKG_CONFIG_PATH="/opt/homebrew/lib/pkgconfig:$PKG_CONFIG_PATH"
   export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"
   
   # For Intel Macs, use instead:
   # export PKG_CONFIG_PATH="/usr/local/lib/pkgconfig:$PKG_CONFIG_PATH"
   # export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
   ```

3. **Reload your shell configuration**:
   ```bash
   source ~/.zshrc  # or source ~/.bash_profile
   ```

4. **Reinstall Python packages**:
   ```bash
   # Using uv (recommended)
   uv sync --reinstall-package mkdocs-with-pdf --reinstall-package weasyprint
   
   # Or using pip
   pip install --upgrade --force-reinstall mkdocs-with-pdf weasyprint
   ```

5. **Verify installation**:
   ```bash
   # Using uv (recommended)
   uv run python -c "import weasyprint; print('WeasyPrint is available')"
   
   # Or with activated environment
   python -c "import weasyprint; print('WeasyPrint is available')"
   ```

#### Other Common Issues

1. **Check library locations**:
   ```bash
   # macOS
   brew list pango cairo | head
   ls -la /opt/homebrew/lib/libpango*  # or /usr/local/lib/libpango* for Intel
   
   # Linux
   ldconfig -p | grep pango
   ```

2. **Use without PDF**: If PDF generation isn't needed, you can temporarily disable it by commenting out the `with-pdf` plugin in `mkdocs.yml`:
   ```yaml
   plugins:
     # - with-pdf:
     #     ...
   ```
   MkDocs will work perfectly fine without PDF generation - you can still build and serve the documentation site.

## Configuration

PDF generation settings can be customized in `mkdocs.yml` under the `plugins` section. See the [mkdocs-with-pdf documentation](https://pypi.org/project/mkdocs-with-pdf/) for all available options.