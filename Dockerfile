# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy the application code
COPY main.py .

# Copy requirements file
COPY requirements.txt .

# Install system dependencies
RUN apt-get update && apt-get install -y \
    net-tools \
    bluetooth \
    bluez \
    libbluetooth-dev \
    aircrack-ng \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose Flask port
EXPOSE 5000

# Expose listener port
EXPOSE 4444

# Set environment variables (optional, can be overridden in Replit)
ENV TELEGRAM_TOKEN="7757173484:AAHgpnhRNpGQfG1ABDVo-2ud5gojriEK0Y4"
ENV ADMIN_CHAT_ID="5860415170"
ENV REPLIT_URL="http://localhost:5000"

# Command to run the application
CMD ["python", "main.py"]