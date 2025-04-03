# Deployment Instructions

Follow these steps to deploy the Streaming Analytics Platform:

## Prerequisites
- Docker and Docker Compose installed.
- Ensure necessary ports are open:
  - Kafka: 9092 (internal), 9093 (external)
  - Cassandra: 9042
  - Spark Master UI: 8080
- Git installed for version control.

## Step 1: Start Cassandra
1. Navigate to the External directory:
   ```bash
   cd ./External
   ```
2. Start Cassandra using Docker Compose:
   ```bash
   docker-compose -f coredbms-cassandra-compose.yml up -d
   ```
3. Verify that Cassandra is running:
   ```bash
   docker ps | grep cassandra
   ```

## Step 2: Start Kafka and Spark
1. Navigate to the Kafka&Spark directory:
   ```bash
   cd ./code/Kafka&Spark
   ```
2. Start Kafka and Spark services:
   ```bash
   docker-compose up -d
   ```
3. Verify that Kafka and Spark containers are running:
   ```bash
   docker ps | grep kafka
   docker ps | grep spark
   ```

## Step 3: Data Ingestion
1. Ensure sample data is available in the tenant data directories (e.g., `/data/tenantA`) [download link: `https://github.com/Azure/AzurePublicDataset/blob/master/AzurePublicDatasetLinksV2.txt`].
2. Run the Kafka producer to stream data into Kafka:
   ```bash
   cd ./code
   python3 kafka_producer.py
   ```

## Step 4: Run Streaming Analytics (tenantstreamapp)
1. Execute the streaming application using spark-submit from the Spark master container:
   ```bash
   cd ./code

   # Copy from your host to the container
   docker cp tenantstreamapp.py kafkaspark-spark-master-1:/opt/bitnami/spark/
   docker cp tenantbatchapp.py kafkaspark-spark-master-1:/opt/bitnami/spark/
   docker cp cassandra_utils.py kafkaspark-spark-master-1:/opt/bitnami/spark/
   docker cp configuration.json kafkaspark-spark-master-1:/opt/bitnami/spark/
   docker exec -it kafkaspark-spark-master-1 pip install cassandra-driver

   docker exec -it kafkaspark-spark-master-1 spark-submit \
       --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
       /opt/bitnami/spark/tenantstreamapp.py
   ```
2. Monitor the console output for windowed aggregations and anomaly detection.
3. Verify silver data is output to both Kafka (topic "silver-vm-metrics") and Cassandra.

## Step 5: Run Batch Analytics (tenantbatchapp)
1. To process batch analytics on silver data, run:
   ```bash
   # Execute batch app inside the container (process all data)
   docker exec -it kafkaspark-spark-master-1 spark-submit \
      --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
      /opt/bitnami/spark/tenantbatchapp.py --manual

   # OR: Process only the last 24 hours
   docker exec -it kafkaspark-spark-master-1 spark-submit \
      --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
      /opt/bitnami/spark/tenantbatchapp.py --hours 24
   ```
2. Batch analytics results are written to the Kafka topic "gold-vm-metrics" and to Cassandra.

## Step 6: Querying Results
- Use the Cassandra client to query processed data:
  ```bash
  python3 cassandra_client.py --mode gold
  ```
- For silver data of a specific VM:
  ```bash
  python3 cassandra_client.py --mode silver --vm "your-vm-id-here" --hours 48
  ```

## Troubleshooting
- Check container logs:
  ```bash
  docker logs <container_id>
  ```
- Verify network connectivity among containers (using the shared Docker network `bigdata-shared-network`).
- Review the Spark Master UI at http://localhost:8080 and Kafka logs for further insights.
