from kafka import KafkaConsumer, KafkaAdminClient
from kafka.admin import NewTopic
import json
import time

print("Checking Kafka topics and offsets...")

# Check topic information
try:
    admin_client = KafkaAdminClient(bootstrap_servers=['localhost:9092'])
    topics = admin_client.list_topics()
    print(f"Available topics: {topics}")
    
    # Try to create a new consumer with unique group ID
    print("\nTrying to read raw-data with new consumer group...")
    consumer = KafkaConsumer(
        'raw-data',
        bootstrap_servers=['localhost:9092'],
        auto_offset_reset='earliest',
        group_id=f'inspector-{int(time.time())}',  # Use a unique group ID
        max_partition_fetch_bytes=10485760,
        consumer_timeout_ms=30000  # 30 second timeout
    )
    
    message_found = False
    for message in consumer:
        data = json.loads(message.value.decode('utf-8'))
        message_found = True
        
        # Print metadata about the message
        print(f"Topic: {message.topic}")
        print(f"Partition: {message.partition}")
        print(f"Offset: {message.offset}")
        print(f"Tenant ID: {data.get('tenant_id')}")
        print(f"File Name: {data.get('file_name')}")
        print(f"Chunk Number: {data.get('chunk_number')}")
        print(f"Points Count: {len(data.get('points', []))}")
        
        # Print a sample of the first point only
        if data.get('points'):
            print("\nSample Point Data:")
            print(json.dumps(data['points'][0], indent=2))
        
        # Exit after one message
        break
    
    if not message_found:
        print("No messages found in raw-data topic")
        
    # Now check the metadata topic
    print("\nChecking raw-data-metadata topic...")
    metadata_consumer = KafkaConsumer(
        'raw-data-metadata',
        bootstrap_servers=['localhost:9092'],
        auto_offset_reset='earliest',
        group_id=f'inspector-meta-{int(time.time())}',  # Use a unique group ID
        consumer_timeout_ms=10000
    )
    
    metadata_found = False
    for message in metadata_consumer:
        data = json.loads(message.value.decode('utf-8'))
        metadata_found = True
        
        print(f"Metadata message found:")
        print(json.dumps(data, indent=2))
        break
    
    if not metadata_found:
        print("No messages found in raw-data-metadata topic")
    
    # Add after your existing raw-data-metadata check:

    print("\nChecking processed-data topic...")
    processed_consumer = KafkaConsumer(
        'processed-data',
        bootstrap_servers=['localhost:9092'],
        auto_offset_reset='earliest',
        group_id=f'inspector-processed-{int(time.time())}',  # Use a unique group ID
        consumer_timeout_ms=10000
    )

    processed_found = False
    for message in processed_consumer:
        data = json.loads(message.value.decode('utf-8'))
        processed_found = True
        
        print(f"Processed message found:")
        print(json.dumps(data, indent=2))
        break

    if not processed_found:
        print("No messages found in processed-data topic")
    
except Exception as e:
    print(f"Error: {e}")