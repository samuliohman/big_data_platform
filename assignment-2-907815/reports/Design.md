# Big Data Platform Design for Batch Ingestion & Transformation

## Overview

This design targets a big data platform (`mysimbdp`) that supports multiple tenants ingesting LiDAR data collected over Dublin City in 2015. The data—including LAS files containing 3D point-cloud information—will be processed locally. Cassandra is chosen for the core data management system (`mysimbdp-coredms`) due to its high write throughput and scalability, and Python scripts will be used to handle data ingestion and transformation tasks.

### Deployment Context
This platform is designed to run entirely on a single laptop for development and demonstration purposes. All components, including Cassandra, Python processing scripts, and messaging systems (for future extension) will operate locally with resource constraints typical of a development laptop (16GB RAM, 4-8 cores).

### Multi-Tenancy Scale
The platform is designed to support 3-5 concurrent tenants on a laptop deployment, with the ability to scale to more tenants on more powerful hardware. For demonstration and testing purposes, we will implement and test with 2 tenants.

### Key Technology Choices
- **Core Database (`mysimbdp-coredms`)**: Cassandra - Selected for high write throughput, horizontal scalability, and flexible schema design. Its column-family model works well for geospatial data and will support both batch and streaming pipelines.
- **Processing Framework**: Python with multi-processing - Provides a lightweight yet powerful environment for data transformation.
- **Message Queue** (for Part 2): Apache Kafka - Will facilitate real-time data ingestion in Part 2 extensions.

### Key Performance Metrics
- **Data Ingestion Rate:** Targeting 50-100 MB per second on laptop hardware.
- **Data Transformation Rate:** Designed to handle similar throughput by leveraging parallel processing.
- **Latency:** Maximum processing latency of 5 seconds per file for files under 500MB.

## Part 1 - Batch Data Ingestion and Transformation

### 1. Define Constraints and Schemas

// ...existing code...

### 2. Ingestion Pipeline

#### Design Overview
- **Data Source:** LAS files are placed in a dedicated staging directory: `tenant-staging-input-dir/<tenant_id>`.
- **Monitoring:** A Python-based monitoring script (using libraries like watchdog) watches for new files.
- **Data Validation and Transformation:** The script validates each file against the configured file constraints, extracts metadata, and performs necessary data transformations (e.g., coordinate normalization, conversion to a Cassandra-friendly schema).
- **Storage:** Transformed data is inserted into Cassandra with proper partitioning and indexing (using tenant ID and time buckets).

#### Implementation Details
- **Parallel Processing:** Utilize multi-threading or multi-processing to handle multiple files concurrently.
- **Error Handling:** Log invalid files and move them to an error directory for manual review.
- **Batch Processing:** Group files into batches to optimize Cassandra writes, reducing overhead and improving throughput.
- **Data Transformation:** Apply tenant-specific transformations including:
  - Coordinate system normalization
  - Point cloud thinning for large datasets
  - Metadata extraction and enrichment
  - Format conversion to match Cassandra's data model

#### Data Flow Diagram

```
tenant-staging-input-dir/<tenant_id>/*.las 
    → File Validation (format, size, naming)
        → Metadata Extraction
            → Data Transformation
                → Batch Formation
                    → Cassandra Write Operations
```

#### Sample Pseudocode

```python
import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class IngestionHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        process_file(event.src_path)

def process_file(file_path):
    # Validate file constraints (format, size, naming)
    # Extract metadata and perform transformation
    # Write the transformed data into Cassandra
    print(f"Processing {file_path}")
    time.sleep(2)  # Simulated processing time
    print(f"Finished processing {file_path}")

if __name__ == '__main__':
    staging_dir = '/local/path/to/tenant-staging-input-dir'
    event_handler = IngestionHandler()
    observer = Observer()
    observer.schedule(event_handler, staging_dir, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
```

This script monitors the staging directory for new LAS files, validates them, transforms the data, and writes the results into Cassandra.

### 3. Batch Ingestion Manager

#### Design Overview
The `mysimbdp-batchingestmanager` orchestrates the ingestion process across multiple tenants.

- **Scheduling:** Periodically scans tenant directories and enqueues new ingestion tasks.
- **Task Distribution:** Schedules tasks based on tenant-specific configurations and resource availability.
- **Resource Management:** Monitors and adjusts resource allocation based on workload and tenant priorities.
- **Error Handling:** Manages failures and retries for resilient data ingestion.

#### Scheduling Mechanism
- **Polling Interval:** Polls each tenant's staging directory every 30 seconds.
- **Task Queue:** Uses a lightweight task queue (via Python's queue module or Celery for advanced needs) to manage ingestion jobs.
- **Concurrency Controls:** Limits the number of concurrent ingestion tasks per tenant according to their configured quotas.
- **Failure Recovery:** Re-queues or flags failed tasks for manual intervention.
- **Priority-Based Execution:** Handles tenant task priorities based on SLA requirements.

#### Implementation Architecture

```
Batch Ingestion Manager
├── Directory Scanner (polls tenant-staging-input-dir/<tenant_id>)
├── Task Queue (manages pending ingestion tasks)
├── Worker Pool (processes tasks concurrently)
├── Resource Monitor (tracks CPU, memory, I/O usage)
├── Configuration Manager (loads tenant-specific settings)
└── Logging Service (records metrics and events)
```

#### Scheduling Algorithm
The batch ingestion manager uses a weighted fair queuing algorithm that:

1. Assigns weights to tasks based on tenant priority and SLA
2. Ensures resource fairness across tenants
3. Prevents resource starvation for lower-priority tenants
4. Adaptively adjusts concurrency based on system load

This approach ensures optimal resource utilization on a laptop while maintaining tenant isolation and fairness.

### 4. Multi-Tenancy Model

#### Design Overview
- **Shared Components:** The ingestion pipeline script, batch ingestion manager, and logging/monitoring modules are shared across all tenants.
- **Dedicated Components:**
  - **Staging Directories:** Each tenant has a dedicated sub-directory under `tenant-staging-input-dir`.
  - **Cassandra Keyspaces:** Separate keyspaces or column families in Cassandra ensure data isolation.
  - **Configuration Files:** Each tenant has its own configuration file that defines file constraints and service agreements.
  - **Resource Quotas:** CPU, memory, and I/O quotas defined at the tenant level.

#### Isolation Mechanisms
- **File Isolation:** Files for each tenant are stored in `tenant-staging-input-dir/<tenant_id>`.
- **Data Partitioning:** In Cassandra, data is partitioned by tenant ID and further subdivided by time or geographic area, ensuring isolation and query efficiency.
- **Resource Management:** The batch ingestion manager enforces resource quotas (e.g., maximum concurrent jobs) defined per tenant.
- **Process Isolation:** Separate Python processes handle each tenant's ingestion tasks to prevent interference.

#### Testing & Performance Metrics
- **Simulation Workloads:** Each tenant will be tested with:
  - Small files (10-50MB): Testing rapid ingestion of many small files
  - Medium files (100-500MB): Testing balanced throughput scenarios
  - Large files (500MB-2GB): Testing system behavior under heavy load

- **Performance Metrics to be Collected:**
  - **Throughput:** MB/s ingestion rate per tenant
  - **Latency:** Time from file appearance to complete ingestion
  - **Resource Usage:** CPU, memory, and I/O consumption per tenant
  - **Failure Rate:** Percentage of files that fail validation or ingestion
  - **Interference:** Impact of one tenant's workload on others

- **Failure Testing:**
  - Malformed files (incorrect headers, corrupt data)
  - Oversize files (exceeding tenant limits)
  - Rapid ingestion (exceeding rate limits)
  - Resource exhaustion (memory/CPU limits)

#### Expected Performance (Laptop Environment)
- **Tenant A:** 50-80 MB/s with 3 concurrent jobs
- **Tenant B:** 30-50 MB/s with 2 concurrent jobs
- **Combined throughput:** 70-100 MB/s with balanced resource allocation

### 5. Logging Features

#### Logging Objectives
- **Metrics Collection:** Log ingestion time, file size, number of records processed, and error details for every file.
- **Error Tracking:** Maintain logs for files that fail validation or processing.
- **Statistical Analysis:** Aggregate logs to generate insights on system performance and tenant-specific metrics.
- **Resource Monitoring:** Track system resource usage during ingestion activities.
- **SLA Compliance:** Monitor and report on adherence to tenant service agreements.

#### Log Storage & Analysis
- **Local Log Files:** Use Python's logging module to write logs into separate files (or a local database) for each tenant.
- **Structured Log Entries:** Each log entry (in JSON format) includes a timestamp, tenant ID, file name, file size, processing duration, and status.
- **Post-Processing:** Analyze logs using Python scripts or lightweight tools (e.g., an ELK stack on a local instance) to compute metrics such as average ingestion times, throughput (GB per second), and error rates.
- **Dashboard (Optional):** Use Flask and Plotly (or Grafana with a local data source) to display real-time performance metrics.

#### Example Log Entry (JSON)
```json
{
  "timestamp": "2025-02-26T14:32:00Z",
  "tenant_id": "tenantA",
  "file_name": "tenantA_20250226_001.las",
  "file_size_mb": 1500,
  "ingestion_time_sec": 25,
  "records_processed": 1000000,
  "status": "success",
  "errors": []
}
```

#### Statistical Analysis Methods
The logging system supports the following analytical capabilities:

1. **Time-Series Analysis:** Track ingestion performance over time to identify patterns and degradation.
2. **Tenant Comparison:** Compare performance metrics across tenants to identify imbalances.
3. **Error Pattern Detection:** Analyze errors to identify common failure modes and potential improvements.
4. **Resource Utilization:** Correlate system resource usage with ingestion performance.
5. **SLA Compliance Reports:** Generate reports on adherence to tenant service agreements.

Sample statistical queries include:

- Average processing time per MB of data
- 95th percentile latency for each tenant
- Error rate by file type and size
- Resource utilization patterns during peak loads
- Correlation between file characteristics and processing time

## Foundation for Parts 2 and 3

This design for batch processing lays the groundwork for future extensions:

### Streaming Integration Preparation
- The chosen technologies (Cassandra, Python) are compatible with streaming data processing.
- The multi-tenancy model can be extended to streaming contexts.
- The logging and monitoring infrastructure can be adapted for real-time metrics.

### Extensibility Considerations
- **Messaging System Integration:** The design allows for easy integration with Apache Kafka or MQTT for the streaming pipeline in Part 2.
- **Monitoring Expansion:** The logging system can be extended to support real-time alerting and monitoring.
- **Security Foundations:** The tenant isolation model can be extended to support the encrypted data ingestion requirements in Part 3.
- **Quality Control:** The validation mechanisms can be expanded to support the data quality requirements in Part 3.

## Conclusion

This design for Part 1 covers all key aspects of a batch data ingestion and transformation platform:

- **Constraints and Schemas:** Clearly defined file constraints and tenant service agreements with sample configurations.
- **Ingestion Pipeline:** A Python-based pipeline that validates, transforms, and ingests LAS files into Cassandra.
- **Batch Ingestion Manager:** A scheduling component that enforces tenant-specific resource quotas and manages concurrent tasks.
- **Multi-Tenancy Model:** File system and database-level isolation ensure each tenant's data is managed separately.
- **Logging & Monitoring:** A robust logging mechanism captures critical metrics for performance analysis and error tracking.

The design is optimized for local deployment on a laptop while providing a foundation for extending to streaming ingestion and advanced features in Parts 2 and 3.