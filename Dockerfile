FROM python:3.11-slim

# Install Java Runtime for HL7 validator and CA certificates
RUN apt-get update && apt-get install -y openjdk-21-jre-headless ca-certificates && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip --trusted-host pypi.org --trusted-host files.pythonhosted.org && \
    pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

# Copy the application code
COPY impl/ ./impl/

# Create data directories
RUN mkdir -p /data/Test_Scripts /data/Example_Instances /data/Profiles /data/Results /data/config

# Set up volume for data
VOLUME ["/data"]

# Default command
CMD ["python", "-m", "impl", "--config", "/data/config/config.json"]
