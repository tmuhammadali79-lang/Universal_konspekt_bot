FROM python:3.12-slim

# Install FFmpeg and yt-dlp system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

# Copy the rest of the app
COPY . .

# Create temp and data directories
RUN mkdir -p tmp data

# Run the bot
CMD ["python", "bot.py"]
