# las_consumer.py
import json
import time
from kafka import KafkaConsumer
from cassandra.cluster import Cluster
import uuid

# Configure Cassandra connection with retry logic and better error handling
import time
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider

# Add retry logic for more resilient connections
max_attempts = 5
attempt = 0
connected = False

while attempt < max_attempts and not connected:
    try:
        print(f"Attempt {attempt+1} to connect to Cassandra on localhost:9043...")
        
        # Try with increased timeout
        cluster = Cluster(
            ['localhost'], 
            port=9043,
            connect_timeout=15  # Increase timeout
        )
        session = cluster.connect()
        connected = True
        print("Connected to Cassandra!")
    except Exception as e:
        print(f"Failed to connect: {e}")
        attempt += 1
        if attempt < max_attempts:
            print(f"Retrying in 5 seconds...")
            time.sleep(5)
        else:
            print("Max attempts reached. Could not connect to Cassandra.")
            raise

# Create keyspace if it doesn't exist (with tenant isolation)
session.execute("""
    CREATE KEYSPACE IF NOT EXISTS las_data 
    WITH replication = {'class': 'SimpleStrategy', 'replication_factor': '1'}
""")

# Use the keyspace
session.execute("USE las_data")

# Create tables for storing processed LAS data
session.execute("""
    CREATE TABLE IF NOT EXISTS points_by_file (
        file_id UUID,
        tenant_id TEXT,
        file_name TEXT,
        point_id UUID,
        x DOUBLE,
        y DOUBLE,
        z DOUBLE,
        intensity DOUBLE,
        classification INT,
        point_source_id INT,
        scan_angle_rank INT,
        PRIMARY KEY ((file_id), point_id)
    )
""")

session.execute("""
    CREATE TABLE IF NOT EXISTS ingestion_stats (
        file_id UUID,
        tenant_id TEXT,
        file_name TEXT,
        timestamp TIMESTAMP,
        file_size_mb DOUBLE,
        ingestion_time_sec DOUBLE,
        records_processed BIGINT,
        status TEXT,
        errors TEXT,
        PRIMARY KEY (file_id)
    )
""")

# Prepare statements for batch inserts
point_insert_stmt = session.prepare("""
    INSERT INTO points_by_file (
        file_id, tenant_id, file_name, point_id, 
        x, y, z, intensity, classification, point_source_id, scan_angle_rank
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""")

stats_insert_stmt = session.prepare("""
    INSERT INTO ingestion_stats (
        file_id, tenant_id, file_name, timestamp, file_size_mb, 
        ingestion_time_sec, records_processed, status, errors
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""")

def process_chunk(message):
    """Process a chunk of LAS data"""
    tenant_id = message.get('tenant_id')
    file_name = message.get('file_name')
    points = message.get('points', [])
    
    # Generate a unique file ID if this is the first chunk
    if message.get('chunk_number', 0) == 0:
        file_id = uuid.uuid4()
    else:
        # This would need to be retrieved from storage in a production system
        # Here we're simplifying by generating a deterministic ID from the filename
        file_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"{tenant_id}:{file_name}")
    
    start_time = time.time()
    batch_size = 100  # Insert in smaller batches
    
    # Process points in batches to avoid overwhelming Cassandra
    for i in range(0, len(points), batch_size):
        batch_points = points[i:i+batch_size]
        for point in batch_points:
            # Extract point data with defaults for missing values
            point_id = uuid.uuid4()
            x = point.get('X', 0.0)
            y = point.get('Y', 0.0)
            z = point.get('Z', 0.0)
            intensity = point.get('intensity', 0.0)
            classification = int(point.get('classification', 0))
            point_source_id = int(point.get('point_source_id', 0))
            scan_angle_rank = int(point.get('scan_angle_rank', 0))
            
            # Insert into Cassandra
            session.execute(point_insert_stmt, (
                file_id, tenant_id, file_name, point_id,
                x, y, z, intensity, classification, point_source_id, scan_angle_rank
            ))
    
    processing_time = time.time() - start_time
    print(f"Processed chunk {message.get('chunk_number')} with {len(points)} points in {processing_time:.2f} seconds")
    
    return {
        "chunk_number": message.get('chunk_number'),
        "points_processed": len(points),
        "processing_time": processing_time
    }

def process_metadata(message):
    """Process file metadata message"""
    if message.get('status') == 'completed':
        file_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"{message.get('tenant_id')}:{message.get('file_name')}")
        
        # Insert processing statistics
        session.execute(stats_insert_stmt, (
            file_id,
            message.get('tenant_id'),
            message.get('file_name'),
            time.time(),
            message.get('file_size_mb', 0.0),
            message.get('processing_time_sec', 0.0),
            message.get('total_points', 0),
            message.get('status', 'unknown'),
            json.dumps([])
        ))
        
        print(f"File {message.get('file_name')} processing complete. Total points: {message.get('total_points')}")

def main():
    # Create Kafka consumer for data chunks
    consumer = KafkaConsumer(
        'raw-data',
        bootstrap_servers=['localhost:9092'],
        auto_offset_reset='earliest',
        group_id='las-processor',
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )
    
    # Create Kafka consumer for metadata
    metadata_consumer = KafkaConsumer(
        'raw-data-metadata',
        bootstrap_servers=['localhost:9092'],
        auto_offset_reset='earliest',
        group_id='las-metadata-processor',
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )
    
    # Process chunks in one thread
    try:
        print("Starting LAS data consumer...")
        for message in consumer:
            data = message.value
            if 'points' in data:
                process_chunk(data)
    except KeyboardInterrupt:
        print("Stopping chunk consumer...")
    
    # In a production system, you would use threading to handle both consumers
    # For simplicity, we're demonstrating the concept sequentially

    try:
        print("Starting LAS metadata consumer...")
        for message in metadata_consumer:
            data = message.value
            if 'status' in data:
                process_metadata(data)
    except KeyboardInterrupt:
        print("Stopping metadata consumer...")

if __name__ == "__main__":
    main()