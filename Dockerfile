FROM python:3.11.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and model file first for better caching
COPY requirements.txt .
COPY modelf1.h5 .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (excluding unnecessary files)
COPY . .

# Create necessary directories
RUN mkdir -p session_images

# Set non-root user for security (optional but recommended)
RUN useradd -m -r appuser && \
    chown appuser:appuser -R /app
USER appuser

# Expose the port the app runs on
EXPOSE 5110

# Command to run the server
CMD ["python", "app.py"]
