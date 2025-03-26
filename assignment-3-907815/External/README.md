## Instructions on how to run the Cassandra cluster on a local machine

### Prerequisites
- Docker and Docker Compose installed
- The `apache-compose.yml` file

### Running Cassandra
```bash
# Start the Cassandra cluster
docker-compose -f apache-compose.yml up

# Connect to the cluster from your local machine
docker exec -it external-cassandra1-1 cqlsh --request-timeout=60


# OR if you're already inside the container
cqlsh $(hostname -i) 9042
```

### Inspect Cassandra DB
```bash
USE las_data;

SELECT COUNT(*) FROM las_data.points_by_file;
SELECT COUNT(*) FROM las_data.ingestion_stats;

SELECT * FROM las_data.ingestion_stats LIMIT 5;
SELECT * FROM las_data.points_by_file LIMIT 5;

```

### Stopping Cassandra
```bash
docker-compose -f apache-compose.yml down
```

