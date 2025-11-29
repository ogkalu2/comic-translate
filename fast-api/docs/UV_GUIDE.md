# Running with UV Package Manager

This project uses [UV](https://github.com/astral-sh/uv), a fast Python package manager.

## Quick Start

### 1. Install Dependencies

```bash
uv sync
```

This will install all dependencies including the backend server packages (FastAPI, Uvicorn, etc.)

### 2. Run the Server

```bash
uv run python run_server.py
```

Or simply:

```bash
uv run run_server.py
```

The server will start on http://localhost:8000

### 3. Test the API

**Option A: Use the test client**
```bash
uv run python test_client.py path/to/manga_image.jpg
```

**Option B: Open the web interface**
```bash
# Open example_web_client.html in your browser
```

**Option C: Access the API docs**
```
http://localhost:8000/docs
```

## Alternative: Using Standard Python

If you prefer not to use `uv`, you can also run with standard Python:

```bash
# Install dependencies
pip install -e .

# Run the server
python run_server.py
```

## UV Commands Cheat Sheet

```bash
# Install dependencies
uv sync

# Add a new dependency
uv add package-name

# Run a Python script
uv run python script.py

# Run a command in the virtual environment
uv run command

# Update dependencies
uv lock --upgrade

# Show installed packages
uv pip list

# Activate virtual environment manually (if needed)
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

## Configuration

Create a `.env` file (copy from `.env.example`):

```bash
copy .env.example .env
```

Edit the `.env` file to customize:
- Port number
- GPU settings
- Default models
- Languages

## Troubleshooting

### Issue: Module not found
**Solution**: Run `uv sync` to install dependencies

### Issue: Port already in use
**Solution**: Change PORT in `.env` file or:
```bash
# Edit .env and set PORT=8001
uv run python run_server.py
```

### Issue: Permission denied
**Solution**: Run as administrator or use a different port

## What UV Does

- **Faster**: UV is 10-100x faster than pip
- **Reliable**: Lockfile ensures reproducible installs
- **Integrated**: Manages Python versions and virtual environments
- **Compatible**: Works with standard `pyproject.toml`

## Development Workflow

```bash
# 1. Install dependencies
uv sync

# 2. Make changes to code

# 3. Run the server (auto-reloads on changes)
uv run python run_server.py

# 4. Test in another terminal
uv run python test_client.py manga.jpg

# 5. Access API docs
# Open http://localhost:8000/docs
```

## Server is Now Running! 🚀

Your Manga Translation API server is ready at:
- **API Base**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

See [API_README.md](API_README.md) for complete API documentation.
