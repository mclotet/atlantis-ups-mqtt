FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y nut-client && \
    rm -rf /var/lib/apt/lists/*

# Install atlantis-core Python library from the submodule
COPY libs/atlantis-core/python /tmp/atlantis-core
RUN pip install --no-cache-dir "/tmp/atlantis-core[mqtt]"

# Copy the service script
COPY ups_mqtt.py /app/ups_mqtt.py
WORKDIR /app

CMD ["python", "ups_mqtt.py"]
