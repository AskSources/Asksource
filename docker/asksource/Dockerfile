# 1. Base image
FROM ghcr.io/astral-sh/uv:0.6.14-python3.10-bookworm

# 2. Set the working directory
WORKDIR /app

# 3. Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libavif-dev pkg-config \
    libjpeg-dev \
    gcc unzip zip \
    python3-dev \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 4. Copy the entire project structure to maintain correct import paths
COPY src/requirements.txt src/requirements.txt

# 5. Install Python dependencies from src directory
RUN UV_HTTP_TIMEOUT=1000 uv pip install -r src/requirements.txt --system

# 5.1. Fix OpenAI library compatibility issues
RUN UV_HTTP_TIMEOUT=1000 uv pip install --upgrade httpx httpcore openai --system

COPY . .
# 6. Command to run the application
# Use the correct module path to maintain the src structure
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]