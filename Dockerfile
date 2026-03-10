FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
    nut-client \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy the Python script
COPY ups-mqtt.py /app/ups-mqtt.py
WORKDIR /app

# Start the script
CMD ["python", "ups-mqtt.py"]