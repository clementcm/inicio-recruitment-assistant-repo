FROM python:3.9-slim

WORKDIR /app

# Install system dependencies for psycopg2 and other tools
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port 8080 (Google Cloud Run default)
EXPOSE 8080

# Command to run the application
# We use host 0.0.0.0 and port 8080 for cloud compatibility
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
