# This directory is about the code.
>Note: we must be able to compile and/or run the code. No BINARY files are within the code. External libraries should be automatically downloaded (e.g., via Maven, npm, pip, docker pull)

## Apache Kafka Setup for Data Ingestion and Processing in WSL

### Setup Instructions

1. **Start Kafka Services** (add this to a docker-compose.yml file in the code directory):
```bash
docker-compose up -d
```

The Kafka topics raw-data and processed-data are automatically created when the containers start up. You can verify they exist with:
```bash
docker exec -it code-kafka-1 kafka-topics.sh --list --bootstrap-server localhost:9092
```

### Data Ingestion (Multitenant simulation)
Run the multitenant data producer script.
Listens to all the tenant subdirectories (etc. ../data/tenantA) and on new file additions it automatically ingests it using kafka.
```bash
python3 batch_ingest_manager.py
```

### Data Ingestion (single tenant)
Run the data producer script:
```bash
python3 las_chunker.py ../data/tenantA/sample_file.las
```

### Data Processing
Run the data consumer and processor script:
```bash
python3 las_consumer.py
```
### Checking rows in Kafka container
```bash
docker exec -it code-kafka-1 kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic raw-data --from-beginning
```

See the individual script files for more details on their functionality.
