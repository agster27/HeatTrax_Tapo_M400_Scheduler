FROM python:3.11-slim

# Metadata labels
LABEL org.opencontainers.image.title="HeatTrax Tapo M400 Scheduler"
LABEL org.opencontainers.image.description="Automated control system for TP-Link Kasa/Tapo smart plugs based on weather conditions"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.authors="agster27"
LABEL org.opencontainers.image.source="https://github.com/agster27/HeatTrax_Tapo_M400_Scheduler"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py .

# Copy web UI files
COPY web/ ./web/

# Create directories for logs and state
RUN mkdir -p /app/logs /app/state

# Run the application
CMD ["python", "-u", "main.py"]
