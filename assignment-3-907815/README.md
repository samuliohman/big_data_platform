# Project Structure - Streaming Analytics Platform

This project implements a scalable data analytics platform for real-time and batch processing of VM CPU metrics. The platform follows a silver/gold data model pattern using Apache Kafka, Apache Spark, and Apache Cassandra.

## Directory Structure

```
/assignment-3-907815/
├── code/                           # Main application code
│   ├── Kafka&Spark/                # Kafka and Spark setup
│   │   ├── docker-compose.yml      # Docker configuration for Kafka and Spark
│   │   └── README.md               # Instructions for Kafka configuration
│   ├── tenantstreamapp.py          # Real-time streaming analytics application
│   ├── tenantbatchapp.py           # Batch analytics application
│   ├── kafka_producer.py           # Simulates streaming data from CSV files
│   ├── cassandra_utils.py          # Cassandra connection and data handling utilities
│   ├── cassandra_client.py         # CLI tool for querying Cassandra
│   ├── configuration.json          # Schema definitions and configuration
│   └── requirements.txt            # Python dependencies
│
├── External/                        # External service configurations
│   ├── coredbms-cassandra-compose.yml  # Cassandra Docker setup
│   └── README.md                    # Instructions for Cassandra
│
├── data/                            # Data storage
│   ├── tenantA/                     # Tenant A data directory
│   ├── tenantB/                     # Tenant B data directory
│   └── tenantC/                     # Tenant C data directory
│
└── reports/                         # Documentation
    ├── Assignment-3-Report.md       # Detailed technical report
    └── Assignment-3-Deployment.md   # Deployment instructions
```

## System Components

1. **Data Flow Architecture**
   - **Raw Data:** VM CPU metrics from Azure Cloud Trace dataset
   - **Streaming Pipeline:** Raw data → Kafka → Spark Streaming → Silver data (anomaly detection)
   - **Batch Pipeline:** Silver data → Spark Batch → Gold data (optimization recommendations)

2. **Key Components**
   - **mysimbdp-messaging (Kafka):** Handles message queuing with topics for raw data, silver, and gold results
   - **mysimbdp-streaming (Spark Streaming):** Real-time analytics for anomaly detection
   - **mysimbdp-batch (Spark Batch):** Scheduled analytics for performance optimization
   - **mysimbdp-coredms (Cassandra):** Persistent storage for silver and gold data

3. **Network Configuration**
   - All components communicate over a shared Docker network `bigdata-shared-network`
   - **Kafka:** Accessible internally (9092) and externally (9093)
   - **Cassandra:** Accessible on port 9042
   - **Spark Master UI:** Available on port 8080

## Getting Started

Please see `reports/Assignment-3-Deployment.md` for detailed setup and deployment instructions.