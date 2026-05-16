FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y nut-client && \
    rm -rf /var/lib/apt/lists/*

# Install atlantis-core Python library from the submodule
COPY libs/atlantis-core/python /tmp/atlantis-core
RUN pip install --no-cache-dir "/tmp/atlantis-core[mqtt,config]"

# Copy the service package and entry point
COPY ups_mqtt/ /app/ups_mqtt/
COPY main.py atlantis.toml /app/
WORKDIR /app

CMD ["python", "main.py"]
