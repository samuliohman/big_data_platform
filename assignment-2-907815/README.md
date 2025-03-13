# Assignment 2 907815

# LiDAR Data Ingestion and Transformation Platform

This project implements a multi-tenant LiDAR data processing platform that ingests, transforms, and stores point cloud data from LAS files. The architecture supports both batch and near real-time data ingestion paths.

## Project Structure

### `/External`

Contains the Cassandra database setup:
- `apache-compose.yml` - Docker Compose file for a 3-node Cassandra cluster
- `README.md` - Instructions for running and interacting with Cassandra

### `/code`

Contains the core processing components:
- `docker-compose.yml` - Kafka and ZooKeeper services
- `batch_ingest_manager.py` - Monitors tenant directories for new LAS files
- `las_chunker.py` - Processes LAS files in chunks for ingestion into Kafka
- `las_consumer.py` - Consumes data from Kafka and stores it in Cassandra
- `README.md` - Instructions for running the application

### `/data`

Contains tenant-specific data directories:
- `/data/tenantA` - Place LAS files here for TenantA
- `/data/tenantB` - Place LAS files here for TenantB
- `/data/tenantC` - Place LAS files here for TenantC

**Note:** LAS files are not included in the repository and must be provided separately.

### `/logs`

Contains tenant-specific log files in JSON format:
- Ingestion metrics (throughput, timing, file sizes)
- Processing statistics
- Error logs

### `/reports`

Contains project documentation:
- `Assignment-907815-Report.md` - Detailed report answering assignment requirements
- `Overall_design.md` - High-level design overview and architectural decisions
- `Assignment-907815-Deployment.md` - Step-by-step deployment instructions

## Data Flow

1. LAS files are placed in tenant-specific directories under `/data`
2. `batch_ingest_manager.py` detects new files and launches `las_chunker.py` for each file
3. `las_chunker.py` processes files in chunks and sends data to Kafka
4. `las_consumer.py` consumes data from Kafka and stores it in Cassandra
5. Performance metrics are logged to tenant-specific files in the `/logs` directory

## Multi-Tenant Design

The system maintains tenant isolation at multiple levels:
- Separate data directories for each tenant
- Tenant ID embedded in all messages and logs
- Tenant ID used as part of the primary key in Cassandra

## Quick Start

See `Assignment-907815-Deployment.md` in the `/reports` directory for complete setup and execution instructions.
