FROM python:3.11-slim

LABEL maintainer="AIFORGE Analytics"
LABEL description="Enterprise AI Intelligence Platform"

# System dependencies for spaCy and scientific packages
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy source code
COPY . .

# Create directories that may not exist
RUN mkdir -p database data/raw data/processed data/synthetic

# Initialise database and generate synthetic data
RUN python scripts/setup_db.py && \
    python scripts/run_pipeline.py --mode synthetic

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run the dashboard
CMD ["streamlit", "run", "app/main.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
