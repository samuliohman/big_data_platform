# las_chunker.py
import laspy
import json
import time
import os
import sys
from kafka import KafkaProducer

# Configuration
CHUNK_SIZE = 10000  # Points per chunk
TENANT_ID = "tenantA"  # Tenant identifier

def process_las_file(las_file_path, topic):
    """Process a LAS file and send chunks to Kafka"""
    
    start_time = time.time()
    producer = KafkaProducer(
        bootstrap_servers=['localhost:9092'],
        value_serializer=lambda x: json.dumps(x).encode('utf-8'),
        max_request_size=10485760  # 10MB max message size
    )
    
    file_size_mb = os.path.getsize(las_file_path) / (1024 * 1024)
    file_name = os.path.basename(las_file_path)
    
    print(f"Processing file: {file_name} ({file_size_mb:.2f} MB)")
    
    # Track statistics
    total_points = 0
    chunks_sent = 0
    
    try:
        # Open LAS file with chunked reading
        with laspy.open(las_file_path) as fh:
            # Get dimensions from file
            dimensions = fh.header.point_format.dimension_names
            
            # Process in chunks
            for points in fh.chunk_iterator(CHUNK_SIZE):
                chunk_data = []
                chunk_size = len(points.X)
                
                # Convert each point to a dictionary
                for i in range(chunk_size):
                    point = {}
                    for dim in dimensions:
                        try:
                            point[dim] = float(getattr(points, dim)[i])
                        except (AttributeError, TypeError):
                            point[dim] = None
                    chunk_data.append(point)
                
                # Create message with metadata
                message = {
                    "tenant_id": TENANT_ID,
                    "file_name": file_name,
                    "chunk_number": chunks_sent,
                    "points": chunk_data,
                    "timestamp": time.time()
                }
                
                # Send to Kafka
                producer.send(topic, message)
                
                total_points += chunk_size
                chunks_sent += 1
                
                # Log progress
                if chunks_sent % 10 == 0:
                    print(f"Sent {chunks_sent} chunks, {total_points} points")
                    
        # Send completion message
        completion_message = {
            "tenant_id": TENANT_ID,
            "file_name": file_name,
            "status": "completed",
            "total_points": total_points,
            "total_chunks": chunks_sent,
            "file_size_mb": file_size_mb,
            "processing_time_sec": time.time() - start_time
        }
        producer.send(f"{topic}-metadata", completion_message)
        
        print(f"File processing complete. Sent {chunks_sent} chunks with {total_points} points.")
    
    except Exception as e:
        print(f"Error processing file: {e}")
        # Send error message
        error_message = {
            "tenant_id": TENANT_ID,
            "file_name": file_name,
            "status": "error",
            "error_message": str(e),
            "processing_time_sec": time.time() - start_time
        }
        producer.send(f"{topic}-metadata", error_message)
    
    finally:
        producer.flush()
        producer.close()
        
        # Log ingestion metrics
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tenant_id": TENANT_ID,
            "file_name": file_name,
            "file_size_mb": file_size_mb,
            "ingestion_time_sec": time.time() - start_time,
            "records_processed": total_points,
            "status": "success" if total_points > 0 else "error",
            "errors": []
        }
        
        with open(f"logs/{TENANT_ID}_ingestion_log.json", 'a') as log_file:
            log_file.write(json.dumps(log_entry) + "\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python las_chunker.py path/to/las_file.las")
        sys.exit(1)
    
    las_file_path = sys.argv[1]
    
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    
    # Process the file and send to the raw-data topic
    process_las_file(las_file_path, "raw-data")