# Assignment 2 - Deployment Instructions

## Prerequisites

- Docker and Docker Compose
- Python 3.8+ with pip
- Git (for cloning the repository)

## Step 1: Install Python Dependencies

```bash
cd /home/samuli/School/big_data/big_data_platform/assignment-2-907815
pip install -r requirements.txt
```

If requirements.txt is not available, install the following packages:

```bash
pip install laspy numpy kafka-python watchdog schedule cassandra-driver
```

## Step 2: Start Kafka Services

```bash
cd ./code
docker-compose up -d
```

Verify Kafka is running:
```bash
docker ps
# You should see zookeeper and kafka containers running
```

## Step 3: Start Cassandra Cluster

```bash
cd ../External
docker-compose -f apache-compose.yml up -d
```

Verify Cassandra is running:
```bash
docker ps
# You should see three cassandra containers running
```

Wait about 30-60 seconds for Cassandra to initialize fully.

## Step 4: Add LiDAR Data Files

Copy your LAS files to the tenant directories:

```bash
# Example - copy LAS files to tenant directories
cp /path/to/your/lidar-file1.las ./data/tenantA/
cp /path/to/your/lidar-file2.las ./data/tenantB/
```

> **Note**: LAS files are not included in this repository and must be provided separately.

## Step 5: Start the Batch Ingestion Manager

```bash
cd code
python batch_ingest_manager.py
```

This will start monitoring the tenant directories for new LAS files.

## Step 6: Start the Stream Processing Consumer

Open a new terminal window and run:

```bash
cd /home/samuli/School/big_data/big_data_platform/assignment-2-907815/code
python las_consumer.py
```

## Step 7: Testing the System

To test the system:

1. Place a new LAS file in one of the tenant directories:
   ```bash
   cp /path/to/your/new-file.las ./data/tenantA/
   ```

2. The batch_ingest_manager will automatically detect the file and start processing it.

3. Check the logs directory for processing information:
   ```bash
   cat ../logs/tenantA_ingestion_log.json
   cat ../logs/tenantA_consumer_log.json
   ```

## Step 8: Verify Data in Cassandra

```bash
docker exec -it external-cassandra1-1 cqlsh

# In the cqlsh prompt:
USE las_data;
SELECT COUNT(*) FROM points_by_file;
SELECT COUNT(*) FROM ingestion_stats;
SELECT * FROM ingestion_stats LIMIT 5;
```

## Step 9: Shut Down the System

When finished, stop all components:

```bash
# Stop the Python processes using Ctrl+C in their respective terminals

# Stop the Docker containers
cd /home/samuli/School/big_data/big_data_platform/assignment-2-907815/code
docker-compose down

cd ../External
docker-compose -f apache-compose.yml down
```

## Troubleshooting

- If Kafka connections fail, ensure the Kafka container is running and the port 9092 is accessible.
- If Cassandra connections fail, wait a bit longer for initialization or check port 9042 is accessible.
- For processing errors, check the log files in the `logs` directory.
