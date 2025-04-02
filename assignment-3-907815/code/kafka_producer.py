import json
import os
import time
import csv
import glob
import random
import uuid
import socket
from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic

BROKER_ADDRESS = "localhost:9093"

def load_schema(schema_file):
    """Load the schema from the given JSON file."""
    try:
        with open(schema_file, 'r') as f:
            schema = json.load(f)
            print(f"Schema loaded successfully")
            return schema
    except Exception as e:
        print(f"Error loading schema: {e}")
        return None

def convert_value(value, field_type):
    """Convert a single CSV value to the correct Python type based on schema."""
    try:
        if field_type == "long":
            return int(float(value))
        elif field_type == "double":
            return float(value)
        elif field_type == "string":
            return str(value)
        return value
    except Exception as e:
        # Return default values if conversion fails
        if field_type == "long":
            return 0
        elif field_type == "double":
            return 0.0
        elif field_type == "string":
            return ""

def test_kafka_connection(bootstrap_servers):
    """Test if Kafka is reachable."""
    host, port = bootstrap_servers[0].split(':')
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((host, int(port)))
        s.close()
        print(f"Successfully connected to Kafka at {bootstrap_servers[0]}")
        return True
    except Exception as e:
        print(f"Failed to connect to Kafka at {bootstrap_servers[0]}: {e}")
        return False

def create_topic_if_not_exists(bootstrap_servers, topic_name):
    """Ensure the topic exists."""
    try:
        admin_client = KafkaAdminClient(
            bootstrap_servers=bootstrap_servers,
            client_id='admin-client'
        )
        
        # Get existing topics
        existing_topics = admin_client.list_topics()
        
        if topic_name not in existing_topics:
            print(f"Topic {topic_name} does not exist. Creating it...")
            topic = NewTopic(name=topic_name, 
                            num_partitions=1, 
                            replication_factor=1)
            admin_client.create_topics([topic])
            print(f"Topic {topic_name} created successfully")
        else:
            print(f"Topic {topic_name} already exists")
        
        admin_client.close()
        return True
    except Exception as e:
        print(f"Error working with topics: {e}")
        return False

def create_producer():
    """Create and return a Kafka producer."""
    bootstrap_servers = [BROKER_ADDRESS]
    
    # Test connection first
    if not test_kafka_connection(bootstrap_servers):
        print("WARNING: Could not connect to Kafka. Exiting.")
        return None
    
    try:
        producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda x: json.dumps(x).encode('utf-8'),
            acks='all',  # Wait for all replicas
            retries=5,    # Retry a few times
            batch_size=16384,  # Default batch size
            linger_ms=1,  # Wait up to 1ms to batch messages
            buffer_memory=33554432,  # 32MB buffer
        )
        print("Kafka producer created successfully")
        return producer
    except Exception as e:
        print(f"Error creating Kafka producer: {e}")
        return None

def send_batch_to_kafka(producer, batch, topic):
    """Send a batch of records to Kafka."""
    if producer is None:
        return 0, len(batch)
    
    sent = 0
    errors = 0
    
    for record in batch:
        try:
            future = producer.send(topic, value=record)
            sent += 1
        except Exception as e:
            errors += 1
    
    # Flush to ensure all messages are sent
    producer.flush()
    return sent, errors

def process_and_send_data(data_dir, schema, producer, topic="raw-vm-metrics"):
    """Read CSV files in chunks and send data to Kafka as it's being read."""
    schema_fields = schema.get("fields", [])
    
    # Ensure topic exists
    print(f"Ensuring topic '{topic}' exists...")
    create_topic_if_not_exists([BROKER_ADDRESS], topic)
    
    files = glob.glob(os.path.join(data_dir, "*.csv"))
    if not files:
        print(f"No CSV files found in {data_dir}")
        return 0
    
    total_sent = 0
    total_errors = 0
    total_filtered = 0  # Track filtered records
    batch_size = 100  # Send records in batches of this size
    
    # Find the index of vm_id in the schema
    vm_id_index = next((i for i, field in enumerate(schema_fields) if field["name"] == "vm_id"), -1)
    if vm_id_index == -1:
        print("Warning: vm_id field not found in schema. Filtering will be skipped.")
    
    for file_path in files:
        print(f"Reading data from {file_path}")
        
        # Count total lines first (for progress reporting)
        total_lines = 0
        try:
            with open(file_path, 'r') as f:
                # Use a faster method to count lines
                for _ in f:
                    total_lines += 1
            print(f"File contains {total_lines} total lines")
        except Exception as e:
            print(f"Could not count lines in file: {e}")
            total_lines = 0  # We'll proceed without knowing the total
        
        line_count = 0
        valid_records = 0
        invalid_records = 0
        current_batch = []
        chunk_size = 10000  # Update progress every 10,000 lines
        last_progress_print = 0  # Track when we last printed progress
        
        with open(file_path, 'r') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                line_count += 1
                
                if len(row) >= len(schema_fields):
                    try:
                        # Get vm_id for filtering before creating the full data point
                        if vm_id_index >= 0 and vm_id_index < len(row):
                            vm_id = row[vm_id_index]
                            # Apply the filter: only process if hash(vm_id) % 10 == 0
                            if hash(vm_id) % 1000 != 0:
                                total_filtered += 1
                                continue  # Skip this record
                        
                        data_point = {}
                        for idx, field in enumerate(schema_fields):
                            field_name = field["name"]
                            field_type = field["type"]
                            data_point[field_name] = convert_value(row[idx], field_type)
                            
                        current_batch.append(data_point)
                        valid_records += 1
                        
                        # Send batch when it reaches the batch size
                        if len(current_batch) >= batch_size:
                            sent, errors = send_batch_to_kafka(producer, current_batch, topic)
                            total_sent += sent
                            total_errors += errors
                            current_batch = []  # Clear batch after sending
                            
                            # Print progress
                            if line_count - last_progress_print >= chunk_size:
                                if total_lines > 0:
                                    progress_percent = (line_count / total_lines) * 100
                                    print(f"Successfully processed and sent {line_count}/{total_lines} lines ({progress_percent:.1f}%) from {file_path}")
                                else:
                                    print(f"Successfully processed and sent {line_count} lines from {file_path}")
                                last_progress_print = line_count
                            
                    except Exception as e:
                        invalid_records += 1
                else:
                    invalid_records += 1
        
        # Send any remaining records in the batch
        if current_batch:
            sent, errors = send_batch_to_kafka(producer, current_batch, topic)
            total_sent += sent
            total_errors += errors
        
        # Final progress update
        if line_count > last_progress_print:
            if total_lines > 0:
                progress_percent = (line_count / total_lines) * 100
                print(f"Successfully processed and sent {line_count}/{total_lines} lines ({progress_percent:.1f}%) from {file_path}")
            else:
                print(f"Successfully processed and sent {line_count} lines from {file_path}")
        
        print(f"Finished reading {line_count} lines from {file_path}")
        print(f"Valid records: {valid_records}, Invalid records: {invalid_records}")
        print(f"Filtered out records (non-selected VMs): {total_filtered}")
    
    print(f"Total records sent: {total_sent}")
    print(f"Total records filtered: {total_filtered}")
    print(f"Total errors: {total_errors}")
    return total_sent

def main():
    print("Starting Kafka producer...")
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "configuration.json")
    schema = load_schema(schema_path)
    if not schema:
        print("No valid schema found. Exiting.")
        return

    producer = create_producer()
    if not producer:
        return
        
    # Get data directories from schema configuration
    data_dirs = schema.get("data_dirs", ["../data/tenantA"])
    
    # Process each directory specified in the configuration
    total_records_sent = 0
    for data_dir in data_dirs:
        print(f"Processing data from directory: {data_dir}")
        os.makedirs(data_dir, exist_ok=True)
        sent = process_and_send_data(data_dir, schema, producer)
        total_records_sent += sent
        print(f"Processed {sent} records from {data_dir}")
    
    print(f"Done. Sent {total_records_sent} records to Kafka from all directories.")

if __name__ == "__main__":
    main()