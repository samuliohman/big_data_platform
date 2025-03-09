#!/usr/bin/env python3
"""
Data consumer for Kafka - processes data from raw-data topic and publishes to processed-data topic
"""
from kafka import KafkaConsumer, KafkaProducer
import json

def process_data(data):
    """
    Process the raw data
    - Add a data quality flag
    - Convert temperature to Fahrenheit
    - Calculate heat index
    """
    try:
        # Add data quality flag
        data['quality'] = 'good' if (15 <= data['temperature'] <= 30 and 
                                    30 <= data['humidity'] <= 70) else 'suspect'
        
        # Convert temperature to Fahrenheit
        data['temperature_f'] = round((data['temperature'] * 9/5) + 32, 2)
        
        # Simple heat index calculation (simplified version)
        data['heat_index'] = round(data['temperature'] + (0.05 * data['humidity']), 2)
        
        return data
    except Exception as e:
        print(f"Error processing data: {e}")
        data['quality'] = 'error'
        return data

def main():
    # Create Kafka consumer
    consumer = KafkaConsumer(
        'raw-data',
        bootstrap_servers=['localhost:9092'],
        auto_offset_reset='earliest',
        group_id='data-processor',
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )
    
    # Create Kafka producer for processed data
    producer = KafkaProducer(
        bootstrap_servers=['localhost:9092'],
        value_serializer=lambda x: json.dumps(x).encode('utf-8')
    )
    
    print("Kafka Consumer started. Processing data from 'raw-data' topic and sending to 'processed-data'. Press Ctrl+C to stop.")
    
    try:
        for message in consumer:
            raw_data = message.value
            print(f"Received: {raw_data}")
            
            # Process the data
            processed_data = process_data(raw_data)
            
            # Send the processed data to the processed-data topic
            producer.send('processed-data', value=processed_data)
            print(f"Processed and sent: {processed_data}")
    except KeyboardInterrupt:
        print("Stopping consumer...")
    finally:
        consumer.close()
        producer.close()

if __name__ == "__main__":
    main()
