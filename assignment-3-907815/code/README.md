# Kafka Producer and Consumer Setup

## Kafka Broker Address
Ensure that the Kafka producer and consumer use the correct broker address:
- **Inside Docker**: Use `kafkaspark-kafka-1:9092`.
- **From Host Machine**: Use `localhost:9092`.

## Running the Producer
Run the Kafka producer script:
```bash
python3 kafka_producer.py
```

The producer now streams data directly to Kafka as it's being read from the files, instead of loading the entire dataset into memory first. This allows for handling very large files efficiently.

## Consuming Messages
To consume messages from the topic:
```bash
docker exec -it kafkaspark-kafka-1 kafka-console-consumer.sh --bootstrap-server kafkaspark-kafka-1:9092 --topic raw-vm-metrics --from-beginning
```

## Monitoring Progress
The producer provides regular status updates as it processes files:
- Number of lines processed
- Number of records successfully sent to Kafka
- Any errors encountered during processing

TODO:
- Implement tenantbatchapp -> golden data
- Update documentation
- idea for parallelization:
    cpu_df = cpu_df.filter(expr("hash(vm_id) % 10 = 0"))  # Process 10% of VMs
- fix data retention limits to function properly with memory limits
- fix the timestamps to work properly (instead of just integer timestamps), think about watermarks.
- Silver data to cassandra also
- Demonstrate graph for example a single device IDs cpu_util
- performance metrics?

docker exec -it kafkaspark-kafka-1 kafka-run-class.sh kafka.tools.GetOffsetShell --broker-list localhost:9092 --topic raw-vm-metrics --time -1
docker exec -it kafkaspark-kafka-1 kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic raw-vm-metrics --from-beginning --max-messages 5

docker exec -it kafkaspark-kafka-1 kafka-run-class.sh kafka.tools.GetOffsetShell --broker-list localhost:9092 --topic silver-vm-metrics --time -1
docker exec -it kafkaspark-kafka-1 kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic silver-vm-metrics --from-beginning --max-messages 5

# Copy from your host to the container
docker cp tenantstreamapp.py kafkaspark-spark-master-1:/opt/bitnami/spark/
docker cp tenantbatchapp.py kafkaspark-spark-master-1:/opt/bitnami/spark/
docker cp cassandra_utils.py kafkaspark-spark-master-1:/opt/bitnami/spark/
docker cp configuration.json kafkaspark-spark-master-1:/opt/bitnami/spark/

# Execute spark-submit inside the container
docker exec -it kafkaspark-spark-master-1 pip install cassandra-driver

docker exec -it kafkaspark-spark-master-1 spark-submit \
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
    /opt/bitnami/spark/tenantstreamapp.py


# Execute batch app inside the container (process all data)
docker exec -it kafkaspark-spark-master-1 pip install cassandra-driver
docker exec -it kafkaspark-spark-master-1 spark-submit \
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
    /opt/bitnami/spark/tenantbatchapp.py --manual

# OR: Process only the last 24 hours
docker exec -it kafkaspark-spark-master-1 spark-submit \
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
    /opt/bitnami/spark/tenantbatchapp.py --hours 24

# Run the batch app daily
docker exec -it kafkaspark-spark-master-1 spark-submit \
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
    /opt/bitnami/spark/tenantbatchapp.py --hours 24



# Basic usage (connects to localhost:9042 by default)
python cassandra_client.py

# Connect to a specific Cassandra node on a custom port
python cassandra_client.py --host localhost --port 9042 --mode silver

# View silver data for a specific VM
python cassandra_client.py --mode silver --vm "your-vm-id-here" --hours 48

# View gold recommendations
python cassandra_client.py --mode gold
