FROM python:3.11-slim

COPY ./certs/ /usr/local/share/ca-certificates/

RUN apt-get update && apt-get install -y ca-certificates openjdk-21-jre-headless \
    && update-ca-certificates     
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
CMD ["python", "-m", "impl", "--config", "/data/config/config.json", "--novalidator"]
