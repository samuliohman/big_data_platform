#!/usr/bin/env python3
"""
Data producer for Kafka - ingests data and publishes to raw-data topic
"""
from kafka import KafkaProducer
import json
import time
import random
from datetime import datetime

def generate_sample_data():
    """Generate sample data for demonstration"""
    return {
        "timestamp": datetime.now().isoformat(),
        "sensor_id": f"sensor_{random.randint(1, 10)}",
        "temperature": round(random.uniform(15.0, 35.0), 2),
        "humidity": round(random.uniform(30.0, 80.0), 2),
        "pressure": round(random.uniform(995.0, 1015.0), 2)
    }

def main():
    # Create Kafka producer
    producer = KafkaProducer(
        bootstrap_servers=['localhost:9092'],
        value_serializer=lambda x: json.dumps(x).encode('utf-8')
    )
    
    print("Kafka Producer started. Sending data to 'raw-data' topic. Press Ctrl+C to stop.")
    
    try:
        # Continuous data generation and publication
        while True:
            data = generate_sample_data()
            producer.send('raw-data', value=data)
            print(f"Sent: {data}")
            time.sleep(2)  # Send data every 2 seconds
    except KeyboardInterrupt:
        print("Stopping producer...")
    finally:
        producer.close()

if __name__ == "__main__":
    main()
