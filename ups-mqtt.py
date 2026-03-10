import subprocess
import json
import time
import paho.mqtt.client as mqtt
import logging
import sys
from datetime import datetime, timezone
import os

# Logging configuration
log_format = "%(asctime)s [%(levelname)s] - %(message)s"
log_file_path = "/var/log/ups-mqtt.log"  # Log file path inside the container

# Set up the logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Create a formatter
formatter = logging.Formatter(log_format)

# Log to stdout
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(formatter)
logger.addHandler(stdout_handler)

# Log to file
file_handler = logging.FileHandler(log_file_path)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Environment variable setup (as before)
MQTT_HOST = os.getenv('MQTT_HOST', 'mqtt_broker_address')
MQTT_TOPIC = os.getenv('MQTT_TOPIC', '/path/to/topic/ups')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))

SAMPLE_RATE_ONLINE = int(os.getenv('SAMPLE_RATE_ONLINE', 60))
SAMPLE_RATE_OFFLINE = int(os.getenv('SAMPLE_RATE_OFFLINE', 10))

UPS_NAME = os.getenv('UPS_NAME', 'ups')
UPS_HOST = os.getenv('UPS_HOST', 'localhost')
UPS_PORT = os.getenv('UPS_PORT', '3493')

# Set up MQTT client
def setup_mqtt_client():
    client = mqtt.Client()
    try:
        logger.info(f"Attempting to connect to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
        client.connect(MQTT_HOST, MQTT_PORT)
        logger.info("Connected to MQTT broker successfully.")
    except Exception as e:
        logger.error(f"Error connecting to MQTT broker: {e}")
        exit(1)
    return client

# Function to fetch UPS data using upsc
def get_ups_data():
    ups_metrics = {}
    try:
        result = subprocess.run(['upsc', UPS_NAME + '@' + UPS_HOST + ':' + UPS_PORT], capture_output=True, text=True)
        lines = result.stdout.splitlines()
        for line in lines:
            try:
                key, value = line.split(":", 1)
                ups_metrics[key.strip()] = value.strip()
            except ValueError as e:
                logger.warning(f"Skipping malformed line: {line}. Error: {e}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing upsc command: {e}")
    except Exception as e:
        logger.error(f"Unexpected error while fetching UPS data: {e}")
    return ups_metrics

# Determine if UPS is online
def is_ups_online(ups_data):
    try:
        return ups_data.get("ups.status", "") == "OL"
    except Exception as e:
        logger.error(f"Error determining UPS status: {e}")
        return False

# Publish data to MQTT
def publish_to_mqtt(client, ups_metrics):
    try:
        ups_metrics["timestamp"] = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(ups_metrics)
        client.publish(MQTT_TOPIC, payload)
        logger.info(f"Published data: {payload}")
    except Exception as e:
        logger.error(f"Error publishing data to MQTT: {e}")

# Main function
def main():
    logger.info("Starting UPS to MQTT...")
    client = setup_mqtt_client()
    while True:
        try:
            ups_data = get_ups_data()
            if not ups_data:
                logger.warning("No UPS data available, retrying...")
                time.sleep(SAMPLE_RATE_OFFLINE)
                continue

            if is_ups_online(ups_data):
                sample_rate = SAMPLE_RATE_ONLINE
            else:
                sample_rate = SAMPLE_RATE_OFFLINE

            publish_to_mqtt(client, ups_data)

            time.sleep(sample_rate)
        except Exception as e:
            logger.error(f"Unhandled error in the main loop: {e}")
            time.sleep(SAMPLE_RATE_OFFLINE)

if __name__ == "__main__":
    main()
