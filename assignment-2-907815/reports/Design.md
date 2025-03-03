Big Data Platform Design for Batch Ingestion & Transformation
Overview
This design targets a big data platform (mysimbdp) that supports multiple tenants ingesting LiDAR data collected over Dublin City in 2015. The data, which includes LAS files containing 3D point-cloud information, will be processed locally. Cassandra is chosen for the coredms due to its high write throughput and scalability, and Python scripts will be used to handle data ingestion and transformation tasks.

The platform is built to serve:

Researchers who require rapid and reliable ingestion of high-volume geospatial data.
Urban planners and city officials who analyze urban development and density.
Data scientists working on 3D point-cloud processing and analytics.
Key performance metrics include:

Data Ingestion Rate: Targeting at least 0.5–1 GB per second, depending on hardware limitations.
Data Transformation (Mangling) Rate: Designed to handle similar throughput by leveraging parallel processing.
1. Define Constraints and Schemas
File Constraints
File Format: Only LAS files are supported.
File Size Limit: For example, each LAS file should not exceed 2 GB.
Naming Convention: Files must follow a strict pattern such as <tenant_id>_YYYYMMDD_<unique_id>.las to ensure proper routing.
Required Metadata: Files must include metadata (e.g., acquisition date, flight path, sensor information) embedded either in the file header or in an accompanying JSON file.
Tenant Service Agreement Constraints
Ingestion Throughput: Each tenant is allocated a maximum ingestion rate (e.g., Tenant A: 500 MB/s, Tenant B: 300 MB/s) to balance the load.
Latency: SLAs might require that each file is processed within a maximum latency window (e.g., 30–45 seconds).
Resource Quotas: Limits on the number of concurrent ingestion jobs and storage quotas (e.g., 100 GB for Tenant A vs. 80 GB for Tenant B).