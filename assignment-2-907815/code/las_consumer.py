# las_consumer.py
import json
import time
from kafka import KafkaConsumer
from cassandra.cluster import Cluster
import uuid
from cassandra.query import BatchStatement, BatchType
import os
from kafka.errors import KafkaError
import threading
import signal

# Configure Cassandra connection with retry logic and better error handling
import time
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from cassandra.query import ConsistencyLevel

# Add retry logic for more resilient connections
max_attempts = 5
attempt = 0
connected = False

while attempt < max_attempts and not connected:
    try:
        print(f"Attempt {attempt+1} to connect to Cassandra on localhost:9042...")
        
        # Try with increased timeout
        cluster = Cluster(
            ['localhost'], 
            port=9042,
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
point_insert_stmt.consistency_level = ConsistencyLevel.ANY

stats_insert_stmt = session.prepare("""
    INSERT INTO ingestion_stats (
        file_id, tenant_id, file_name, timestamp, file_size_mb, 
        ingestion_time_sec, records_processed, status, errors
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""")
stats_insert_stmt.consistency_level = ConsistencyLevel.ANY

def process_chunk(message):
    """Process a chunk of LAS data"""
    global session, cluster, point_insert_stmt, stats_insert_stmt
    
    tenant_id = message.get('tenant_id')
    file_name = message.get('file_name')
    points = message.get('points', [])
    
    # Generate a unique file ID
    file_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"{tenant_id}:{file_name}")
    
    start_time = time.time()
    
    # OPTIMIZATION 1: Increase batch size for better throughput
    batch_size = 250  # Increased from 100
    
    # OPTIMIZATION 2: Prepare all point data before batching
    prepared_points = []
    for point in points:
        point_id = uuid.uuid4()
        prepared_points.append({
            'id': point_id,
            'x': point.get('X', 0.0),
            'y': point.get('Y', 0.0),
            'z': point.get('Z', 0.0),
            'intensity': point.get('intensity', 0.0),
            'classification': int(point.get('classification', 0)),
            'point_source_id': int(point.get('point_source_id', 0)),
            'scan_angle_rank': int(point.get('scan_angle_rank', 0))
        })
    
    # Process points in batches with retry logic
    for i in range(0, len(prepared_points), batch_size):
        max_retries = 3
        retry_count = 0
        success = False
        
        while retry_count < max_retries and not success:
            try:
                batch_points = prepared_points[i:i+batch_size]
                
                # OPTIMIZATION 3: Use UNLOGGED batch with larger payload
                batch = BatchStatement(batch_type=BatchType.UNLOGGED)
                
                # OPTIMIZATION 4: Bulk add to batch
                for point in batch_points:
                    batch.add(point_insert_stmt, (
                        file_id, tenant_id, file_name, point['id'],
                        point['x'], point['y'], point['z'], 
                        point['intensity'], point['classification'], 
                        point['point_source_id'], point['scan_angle_rank']
                    ))
                
                # Execute batch with NON_QUORUM consistency for speed
                batch.consistency_level = ConsistencyLevel.ONE
                session.execute(batch)
                success = True
                
            except Exception as e:
                retry_count += 1
                print(f"Error processing batch {i//batch_size}: {e}. Retry {retry_count}/{max_retries}")
                
                # Fallback to smaller batches if needed
                if "Batch too large" in str(e) and retry_count == 1:
                    print("Batch too large, falling back to smaller batches")
                    try:
                        # Split the batch into two smaller batches
                        half_size = len(batch_points) // 2
                        
                        for split_start in [0, half_size]:
                            split_batch = BatchStatement(batch_type=BatchType.UNLOGGED)
                            split_points = batch_points[split_start:split_start+half_size]
                            
                            for point in split_points:
                                split_batch.add(point_insert_stmt, (
                                    file_id, tenant_id, file_name, point['id'],
                                    point['x'], point['y'], point['z'], 
                                    point['intensity'], point['classification'], 
                                    point['point_source_id'], point['scan_angle_rank']
                                ))
                            
                            session.execute(split_batch)
                            
                        success = True
                        continue
                    except Exception as inner_e:
                        print(f"Smaller batch inserts failed too: {inner_e}")
                
                time.sleep(1)  # Reduced wait time before retry
                
                # Original reconnection logic follows
                
                # Try to reconnect if needed
                if retry_count == max_retries - 1:
                    try:
                        print("Attempting to reconnect to Cassandra...")
                        cluster = Cluster(['localhost'], port=9042, connect_timeout=20)
                        session = cluster.connect("las_data")
                        
                        # Re-prepare statements without the global declaration here
                        point_insert_stmt = session.prepare("""
                            INSERT INTO points_by_file (
                                file_id, tenant_id, file_name, point_id, 
                                x, y, z, intensity, classification, point_source_id, scan_angle_rank
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """)
                        point_insert_stmt.consistency_level = ConsistencyLevel.ANY
                    except Exception as conn_err:
                        print(f"Failed to reconnect: {conn_err}")
    
    processing_time = time.time() - start_time
    
    # Estimate data size (average point is roughly 24 bytes × number of dimensions)
    # This assumes 8 dimensions with 3 bytes per dimension on average
    estimated_size_mb = len(points) * 24 * 8 / (1024 * 1024)
    throughput_mb_sec = estimated_size_mb / processing_time if processing_time > 0 else 0
    
    print(f"Processed chunk {message.get('chunk_number')} for {tenant_id} with {len(points)} points in {processing_time:.2f} seconds ({throughput_mb_sec:.2f} MB/s)")
    
    # Log processing information
    os.makedirs("../logs", exist_ok=True)
    log_entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tenant_id": tenant_id,
        "file_name": file_name,
        "chunk_number": message.get('chunk_number'),
        "points_processed": len(points),
        "processing_time_sec": processing_time,
        "throughput_mb_sec": round(throughput_mb_sec, 2),
        "status": "success"
    }
    
    with open(f"../logs/{tenant_id}_consumer_log.json", 'a') as log_file:
        log_file.write(json.dumps(log_entry) + "\n")
    
    return {
        "chunk_number": message.get('chunk_number'),
        "tenant_id": tenant_id,
        "points_processed": len(points),
        "processing_time": processing_time,
        "throughput_mb_sec": round(throughput_mb_sec, 2)
    }

def process_metadata(message):
    """Process file metadata message"""
    tenant_id = message.get('tenant_id')
    file_name = message.get('file_name')
    
    if message.get('status') == 'completed':
        file_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"{tenant_id}:{file_name}")
        
        # Insert processing statistics
        session.execute(stats_insert_stmt, (
            file_id,
            tenant_id,
            file_name,
            time.time(),
            message.get('file_size_mb', 0.0),
            message.get('processing_time_sec', 0.0),
            message.get('total_points', 0),
            message.get('status', 'unknown'),
            json.dumps([])
        ))
        
        # Calculate file processing throughput
        file_size_mb = message.get('file_size_mb', 0.0)
        processing_time = message.get('processing_time_sec', 0.0)
        throughput_mb_sec = file_size_mb / processing_time if processing_time > 0 else 0
        
        print(f"File {file_name} for {tenant_id} processing complete. Total points: {message.get('total_points')}, Throughput: {throughput_mb_sec:.2f} MB/s")
        
        # Log completion information
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tenant_id": tenant_id,
            "file_name": file_name,
            "file_size_mb": file_size_mb,
            "total_points": message.get('total_points', 0),
            "processing_time_sec": processing_time,
            "throughput_mb_sec": round(throughput_mb_sec, 2),
            "status": "completed"
        }
        
        with open(f"../logs/{tenant_id}_consumer_completed_log.json", 'a') as log_file:
            log_file.write(json.dumps(log_entry) + "\n")

def main():
    print("Starting Kafka consumers...")
    
    # Debug Kafka topics first
    try:
        print("Checking for available Kafka topics...")
        from kafka.admin import KafkaAdminClient
        admin_client = KafkaAdminClient(bootstrap_servers=['localhost:9092'])
        topics = admin_client.list_topics()
        print(f"Available Kafka topics: {topics}")
    except Exception as e:
        print(f"Error checking Kafka topics: {e}")
    
    # Create Kafka consumer for data chunks with timeout
    print("Initializing raw-data consumer...")
    consumer = KafkaConsumer(
        'raw-data',
        bootstrap_servers=['localhost:9092'],
        auto_offset_reset='earliest',
        group_id='las-processor',
        value_deserializer=lambda x: json.loads(x.decode('utf-8')),
        consumer_timeout_ms=10000  # 10 seconds timeout
    )
    
    # Create Kafka consumer for metadata
    print("Initializing raw-data-metadata consumer...")
    metadata_consumer = KafkaConsumer(
        'raw-data-metadata',
        bootstrap_servers=['localhost:9092'],
        auto_offset_reset='earliest', 
        group_id='las-metadata-processor',
        value_deserializer=lambda x: json.loads(x.decode('utf-8')),
        consumer_timeout_ms=10000  # 10 seconds timeout
    )
    
    # Create and run both consumers in separate threads
    def run_chunk_consumer():
        message_count = 0
        print("Starting LAS data consumer thread...")
        try:
            for message in consumer:
                print(f"Received raw-data message #{message_count+1}, timestamp: {message.timestamp}")
                data = message.value
                if 'points' in data:
                    print(f"Processing chunk {data.get('chunk_number')} with {len(data.get('points', []))} points")
                    process_chunk(data)
                    message_count += 1
                else:
                    print(f"Unknown message format: {list(data.keys())}")
        except KafkaError as ke:
            print(f"Kafka error in chunk consumer: {ke}")
        except StopIteration:
            print("No more messages in chunk consumer (timeout)")
        except Exception as e:
            print(f"Unexpected error in chunk consumer: {e}")
        print(f"Chunk consumer processed {message_count} messages")
    
    def run_metadata_consumer():
        message_count = 0
        print("Starting LAS metadata consumer thread...")
        try:
            for message in metadata_consumer:
                print(f"Received metadata message #{message_count+1}, timestamp: {message.timestamp}")
                data = message.value
                if 'status' in data:
                    print(f"Processing metadata for file {data.get('file_name')} with status {data.get('status')}")
                    process_metadata(data)
                    message_count += 1
                else:
                    print(f"Unknown metadata format: {list(data.keys())}")
        except KafkaError as ke:
            print(f"Kafka error in metadata consumer: {ke}")
        except StopIteration:
            print("No more messages in metadata consumer (timeout)")
        except Exception as e:
            print(f"Unexpected error in metadata consumer: {e}")
        print(f"Metadata consumer processed {message_count} messages")
    
    # Start both threads
    chunk_thread = threading.Thread(target=run_chunk_consumer)
    metadata_thread = threading.Thread(target=run_metadata_consumer)
    
    chunk_thread.daemon = True
    metadata_thread.daemon = True
    
    chunk_thread.start()
    metadata_thread.start()
    
    # Keep main thread running until interrupted
    try:
        while chunk_thread.is_alive() or metadata_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("Keyboard interrupt received, shutting down...")
        
    print("Consumer threads stopped.")

if __name__ == "__main__":
    main()