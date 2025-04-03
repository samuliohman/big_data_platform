## Instructions on how to run the Cassandra cluster on a local machine

### Prerequisites
- Docker and Docker Compose installed
- The `coredbms-cassandra-compose.yml` file

### Running Cassandra
```bash
# Start the Cassandra cluster
docker-compose -f coredbms-cassandra-compose.yml up -d

# Connect to the cluster from your local machine
docker exec -it external-cassandra1-1 cqlsh --request-timeout=60


# OR if you're already inside the container
cqlsh $(hostname -i) 9042
```

### Inspect Cassandra DB
```bash
DESCRIBE KEYSPACES;
USE vm_metrics;
DESCRIBE TABLES;

SELECT COUNT(*) FROM silver_vm_metrics;
SELECT COUNT(*) FROM gold_vm_recommendations;

SELECT * FROM silver_vm_metrics LIMIT 100;
SELECT * FROM gold_vm_recommendations LIMIT 100;

```

### Stopping Cassandra
```bash
docker-compose -f coredbms-cassandra-compose.yml down
```

