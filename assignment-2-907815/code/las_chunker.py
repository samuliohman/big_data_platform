#!/usr/bin/env python
import sys
import laspy
import json
import time
import os
from kafka import KafkaProducer
from kafka.errors import KafkaError
import numpy as np
import traceback

def extract_tenant_id(file_path):
    """Extract tenant ID from file path"""
    path_parts = file_path.split(os.sep)
    for part in path_parts:
        if part.startswith('tenant'):
            return part
    return "tenantA"  # Default tenant

def main():
    if len(sys.argv) < 2:
        print("Usage: las_chunker.py <path_to_las_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    # Change topic to match what consumer is expecting
    topic = "raw-data"  
    
    # Create a Kafka producer with JSON serialization and larger message size limit
    producer = KafkaProducer(
        bootstrap_servers=['localhost:9092'],
        value_serializer=lambda x: json.dumps(x).encode('utf-8'),
        max_request_size=5242880,  # 5MB max message size
        batch_size=16384,          # Batch size in bytes
        compression_type='gzip',   # Compress messages
        linger_ms=100              # Wait for this time to batch messages
    )
    
    # Get tenant ID and file name
    tenant_id = extract_tenant_id(file_path)
    file_name = os.path.basename(file_path)
    
    # Get file size for logging
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    print(f"Processing file for {tenant_id}: {file_name} ({file_size_mb:.2f} MB)")
    
    # Start timing for throughput calculation
    start_time = time.time()
    
    # Set chunk size in number of points
    chunk_size = 2000 
    
    try:
        # Open LAS file with chunked reading
        with laspy.open(file_path) as fh:
            # Get dimensions from file
            dimensions = list(fh.header.point_format.dimension_names)
            print(f"{tenant_id}: Available dimensions: {dimensions}")
            
            # Use only core dimensions to reduce message size
            core_dimensions = ['X', 'Y', 'Z', 'intensity', 'classification', 'point_source_id']
            print(f"{tenant_id}: Using dimensions: {core_dimensions}")
            
            chunk_index = 0
            total_points = 0
            
            # Process in chunks
            while True:
                try:
                    # Get next chunk of points
                    points = next(fh.chunk_iterator(chunk_size))
                    
                    chunk_data = []
                    current_chunk_size = len(points.X)
                    
                    # Convert each point to a dictionary, using only core dimensions
                    for i in range(current_chunk_size):
                        point = {}
                        for dim in core_dimensions:
                            if dim in dimensions:  # Only use dimensions that exist in the file
                                try:
                                    val = getattr(points, dim)[i]
                                    if isinstance(val, (int, bool, np.integer)):
                                        point[dim] = int(val)
                                    else:
                                        point[dim] = float(val) if val is not None else None
                                except (AttributeError, TypeError, ValueError):
                                    point[dim] = None
                        chunk_data.append(point)
                    
                    # Create message with metadata
                    message = {
                        "tenant_id": tenant_id,
                        "file_name": file_name,
                        "chunk_number": chunk_index,
                        "points": chunk_data,
                        "timestamp": time.time()
                    }
                    
                    # Send the chunk to Kafka asynchronously
                    future = producer.send(topic, value=message)
                    
                    # Block for confirmation (synchronous send)
                    try:
                        record_metadata = future.get(timeout=30)
                        print(f"{tenant_id}: Chunk {chunk_index} with {len(chunk_data)} points sent to {record_metadata.topic}, "
                              f"partition {record_metadata.partition} at offset {record_metadata.offset}")
                    except KafkaError as e:
                        print(f"{tenant_id}: Failed to send chunk {chunk_index}: {e}")
                    
                    total_points += len(chunk_data)
                    chunk_index += 1
                    
                    # Add a flush periodically to ensure data is sent
                    if chunk_index % 10 == 0:
                        producer.flush()
                        print(f"{tenant_id}: Sent {chunk_index} chunks, {total_points} points")
                    
                except ValueError as e:
                    if "buffer size must be a multiple of element size" in str(e):
                        print(f"{tenant_id}: Reached end of file - processed {total_points} points in {chunk_index} chunks.")
                        break  # Exit the loop, we're done
                    else:
                        raise  # Re-raise if it's a different ValueError
                except StopIteration:
                    print(f"{tenant_id}: Reached end of file - all points processed.")
                    break  # We've reached the end of the iterator

        # Send completion message
        completion_message = {
            "tenant_id": tenant_id,
            "file_name": file_name,
            "status": "completed",
            "total_points": total_points,
            "total_chunks": chunk_index,
            "file_size_mb": file_size_mb,
            "processing_time_sec": time.time() - start_time
        }
        producer.send(f"{topic}-metadata", completion_message)
        print(f"{tenant_id}: Completion message sent to {topic}-metadata")

    except Exception as e:
        print(f"{tenant_id}: Error processing file {file_path}: {e}")
        traceback.print_exc()
    
    finally:
        # Log processing stats
        processing_time = time.time() - start_time
        throughput_mb_sec = file_size_mb / processing_time if processing_time > 0 else 0
        
        print(f"{tenant_id}: Processed {total_points} points in {processing_time:.2f} seconds")
        print(f"{tenant_id}: Throughput: {throughput_mb_sec:.2f} MB/s")
        
        # Create logs directory if it doesn't exist
        os.makedirs("../logs", exist_ok=True)
        
        # Write log entry
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tenant_id": tenant_id,
            "file_name": file_name,
            "file_size_mb": file_size_mb,
            "ingestion_time_sec": processing_time,
            "throughput_mb_sec": round(throughput_mb_sec, 2),
            "records_processed": total_points,
            "status": "success" if total_points > 0 else "error",
            "errors": []
        }
        
        with open(f"../logs/{tenant_id}_ingestion_log.json", 'a') as log_file:
            log_file.write(json.dumps(log_entry) + "\n")
        
        # Wait for all messages to be sent and close the producer cleanly
        producer.flush()
        producer.close()

if __name__ == "__main__":
    main()
