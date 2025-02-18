# Use Python 3.11 slim image as base
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY main.py .
COPY .env .

# Create a directory for the service account file
RUN mkdir -p /app/creds

# The service account JSON file should be mounted as a volume
# or copied during build (not recommended for security)
# COPY your-service-account.json /app/creds/

# Set environment variables if needed
# These can be overridden during container run
ENV PYTHONUNBUFFERED=1

# Run the script
CMD ["python", "main.py"]