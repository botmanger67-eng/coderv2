# Setup Guide

This document provides instructions for setting up the project environment, dependencies, and configuration.

## Prerequisites

- Python 3.10 or higher
- pip (Python package installer)
- Git (for cloning the repository)
- Virtual environment tool (recommended: `venv` or `conda`)

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/your-project.git
cd your-project
```

### 2. Create a Virtual Environment

#### Using venv (recommended)

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### Using conda

```bash
conda create -n your-project python=3.10
conda activate your-project
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

For development dependencies:

```bash
pip install -r requirements-dev.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit the `.env` file with your specific configuration:

```env
# Application settings
APP_NAME=YourProject
APP_ENV=development
APP_DEBUG=true
APP_SECRET_KEY=your-secret-key-here

# Database settings
DATABASE_URL=sqlite:///./data/app.db

# API settings
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Logging settings
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
```

### 5. Initialize the Database

```bash
python scripts/init_db.py
```

### 6. Run Database Migrations

```bash
python scripts/migrate.py
```

### 7. Verify Installation

Run the test suite to ensure everything is set up correctly:

```bash
pytest tests/ -v
```

## Docker Setup (Alternative)

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+

### Build and Run

```bash
docker-compose build
docker-compose up -d
```

### Verify Docker Setup

```bash
docker-compose ps
docker-compose logs -f app
```

## Development Setup

### Install Development Tools

```bash
pip install -r requirements-dev.txt
pre-commit install
```

### Configure IDE

For VS Code, create `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    }
}
```

### Run Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Troubleshooting

### Common Issues

1. **Permission denied when creating virtual environment**
   ```bash
   sudo chown -R $(whoami) .
   ```

2. **Missing system dependencies**
   ```bash
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install python3-dev build-essential
   
   # macOS
   brew install python
   ```

3. **Database connection errors**
   - Ensure database service is running
   - Check DATABASE_URL in .env file
   - Verify network connectivity

### Logs

Check application logs for detailed error information:

```bash
tail -f logs/app.log
```

## Verification Checklist

- [ ] Virtual environment activated
- [ ] Dependencies installed
- [ ] Environment variables configured
- [ ] Database initialized
- [ ] Migrations applied
- [ ] Tests passing
- [ ] Development server running

## Next Steps

After completing the setup:

1. Read the [API Documentation](api.md)
2. Explore the [Architecture Guide](architecture.md)
3. Check the [Contributing Guidelines](contributing.md)

## Support

If you encounter any issues during setup:

- Check the [FAQ](faq.md)
- Open an issue on GitHub
- Contact the development team at dev@example.com