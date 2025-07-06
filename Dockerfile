# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy the application code and requirements file
COPY main.py .
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

# Expose Flask port (Render.com requires the port specified in the environment)
EXPOSE 5000

# Set environment variables (Render.com will override these with its environment variables)
ENV TELEGRAM_TOKEN="7757173484:AAHgpnhRNpGQfG1ABDVo-2ud5gojriEK0Y4"
ENV ADMIN_CHAT_ID="5860415170"
ENV REPLIT_URL="https://anna-cdvw.onrender.com:5000"
ENV FLASK_ENV=production

# Command to run the Flask application
CMD ["python", "main.py"]
