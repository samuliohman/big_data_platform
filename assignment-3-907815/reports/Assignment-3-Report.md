# Part 1 - Design for Streaming Analytics  
*(Weighted factor for grades = 3)*

## 1.1 Dataset Selection and Analytics Design  
- As a tenant, select a raw dataset suitable for streaming data analytics as a running scenario.  
- Explain the dataset and why it is suitable for streaming data analytics in your scenario.  
- Present at least two different analytics:  
  - **Streaming Analytics (tenantstreamapp):** Analyzes raw data from the tenant to produce silver data.  
  - **Batch Analytics (tenantbatchapp):** Using the workflow model, analyzes historical silver data outputted by the streaming analytics to produce gold data.  
- Explain:  
  - (i) The overall functionality of the streaming analytics.  
  - (ii) The overall functionality of the batch analytics.  
  - (iii) The data sink of the streaming analytics, as the data source for the batch analytics.  
  - (iv) When and how the batch analytics determines silver data as input.  
- *(1 point)*  

### Dataset Selection and Suitability for Streaming Analytics  

#### Raw Dataset  
We're working with the `vm_cpu_readings-file-*-of-195.csv.gz` subset from the Microsoft Cloud Trace dataset.  

#### Why This Dataset?  
- **Structure**: Each row has a timestamp (epoch seconds), a hashed VM ID, and CPU metrics (min, max, avg CPU usage).  
- **Example row**:  
  ```csv
  0,yNf/R3X8fyXkOJm3ihXQcT0F52a8cDWPPRzTT6QFW8N+1QPfeKR5//6xyX0VYn7X,19.89,24.99,22.63
  ```  
- **Streaming-Friendly**:  
  - **High Velocity**: Metrics arrive continuously, mimicking real-time telemetry.  
  - **Time-Sensitive**: Quick insights help in proactive scaling.  
  - **Built-in Time Partitioning**: The timestamp field makes it easy to apply windowed aggregations.  

### Streaming Analytics (`tenantstreamapp`)  

#### What It Does  
- **Input**: Raw CPU readings (`timestamp, vm_id, min_cpu, max_cpu, avg_cpu`).  
- **Processing Steps**:  
  - Convert timestamps into human-readable format.  
  - Detect anomalies: flag VMs where `max_cpu > 90%` (critical threshold).  
- **Output (Silver Data)**:  
  ```json
  {
    "vm_id": "yNf/R3X8fyXk...",
    "timestamp": "2025-03-19 12:00:00",
    "max_cpu": 95.2,
    "is_anomaly": true
  }
  ```  
- **Data Sink**: Anomaly alerts are stored in Cassandra (low-latency access) and pushed to Kafka for real-time notifications.  

### Batch Analytics (`tenantbatchapp`)  

#### What It Does  
- **Input**: Historical silver data (raw CPU anomalies from the past 30 days).  
- **Processing Steps**:  
  - Identify VMs that exceeded 90% CPU in **80% or more** of the recorded instances.  
  - Suggest optimizations (e.g., resizing, migration).  
- **Output (Gold Data)**:  
  ```json
  {
    "vm_id": "yNf/R3X8fyXk...",
    "date_range": ["2025-03-01", "2025-03-30"],
    "overload_frequency": 85%,
    "recommendation": "Upgrade to 8 vCPUs"
  }
  ```  
- **Scheduling**: Runs daily at 00:00 UTC, processing all silver data up to the previous midnight.  
- **Storage**: Reads from Cassandra (silver) and writes results to a separate Cassandra table for gold data.  


### Data Flow and Trigger Logic  

#### How Streaming Feeds into Batch  
- Silver data is stored in Cassandra, partitioned by day (`YYYY-MM-DD`).  
- The batch job processes **only new data** (where `timestamp <= last execution time`).  
- Example:  
  - If the batch job runs on `2025-03-20`, it picks up everything up to `2025-03-19 23:59:59`.  


### Why This Approach?  
- **Streaming = Real-Time Response**: Quickly detects CPU spikes so tenants can act fast.  
- **Batch = Long-Term Insights**: Helps with capacity planning and cost optimization.  
- **Cassandra = Perfect Fit**: Handles both high-speed writes (streaming) and historical analysis (batch) efficiently.  

This setup makes full use of the dataset’s time-based structure and works well within our platform's stack (Kafka, Spark, Cassandra).

---

## 1.2 Messaging System Considerations  
- The tenant will send raw data through a messaging system, which provides stream data sources.  
- Discuss, explain, and give examples for:  
  - (i) Whether the streaming analytics should handle keyed or non-keyed data streams for the tenant data.  
  - (ii) Which types of message delivery guarantees should be suitable for the stream analytics and why.  
- *(1 point)*  

### (i) Keyed vs. Non-Keyed Streams  
Keyed streams are required for this tenant’s use case.  

#### Why Keyed Streams?  
- **Example Scenario**: The tenant’s `vm_cpu_readings` data includes unique `vm_id` values. To compute VM-specific metrics (e.g., 5-minute rolling average per VM), the stream must be partitioned by `vm_id`.
- **Functionality Dependency**:
  - **Windowed Aggregations**: Rolling averages and anomaly detection are per-VM operations.
  - **Stateful Processing**: Maintaining VM-specific state (e.g., historical CPU trends) requires data partitioning by `vm_id`.
  - **Tenant Isolation**: Each tenant has its own dedicated table in Cassandra, ensuring their data is processed separately and not mixed with others.

##### Concrete Example:
```python
# PySpark Structured Streaming example
df = spark.readStream.format("kafka")...  
keyed_stream = df.withWatermark("timestamp", "5 minutes") \
                 .groupBy("tenant_id", "vm_id", window("timestamp", "5 minutes")) \
                 .agg(avg("max_cpu").alias("avg_max_cpu"))
```
Here, `groupBy("tenant_id", "vm_id")` ensures that all records for a specific `vm_id` within a tenant are routed to the same task for accurate aggregation, maintaining tenant data isolation.

#### Why Not Non-Keyed?  
Non-keyed streams would process data globally, leading to:
- Inaccurate per-VM aggregations (e.g., mixing CPU metrics across VMs from different tenants).
- Inefficient state management (e.g., storing all VM states in a single task).

### (ii) Message Delivery Guarantees  
At-Least-Once Delivery is suitable for this tenant’s streaming analytics.

#### Why At-Least-Once?  
- **Requirement**: The tenant cannot miss critical alerts (e.g., CPU spikes). At-least-once ensures no data loss, even if duplicates occur.
- **Handling Duplicates**:
  - **Consistent Writes**: Silver data writes to Cassandra use upserts with unique keys (e.g., `tenant_id + vm_id + window_start`).
  - **Windowed Aggregations**: Reprocessing duplicate records in a time window does not affect correctness (e.g., recalculating a 5-minute average remains valid).
  - **Tenant Isolation**: Each tenant’s data is stored in a separate Cassandra table, ensuring no cross-tenant duplication or contamination.

##### Example:
If Kafka retries a message due to a transient failure, the same (`tenant_id, vm_id, timestamp, max_cpu=90%`) record may be processed twice. The streaming app will:
- Recompute the 5-minute average (ensuring consistency).
- Overwrite the existing silver record in Cassandra with the same key, ensuring consistency without affecting other tenants' data.

#### Why Not Exactly-Once?  
- **Overhead**: Exactly-once semantics require distributed transactions (e.g., Kafka + Cassandra integration), adding latency.
- **Trade-Off**: For this use case, occasional duplicates are acceptable if alerts are not missed.

#### Why Not At-Most-Once?  
- **Risk of Data Loss**: Dropping messages during failures could miss critical anomalies (e.g., a VM hitting 100% CPU).

### Summary  
- **Keyed Streams**: Essential for per-VM stateful processing (e.g., aggregations, anomaly detection) and ensuring tenant isolation.
- **At-Least-Once**: Balances reliability and performance, ensuring no critical alerts are missed while tolerating duplicates.
- **Tenant Isolation**: Using separate tables per tenant in Cassandra guarantees data is processed independently without interference.

This design aligns with the tenant’s need for real-time anomaly detection and leverages Kafka’s keyed topics and delivery guarantees effectively.

---

## 1.3 Time, Windowing, and Data Order  
- Given streaming data from the tenant, explain and give examples for:  
  - (i) Which types of time should be associated with stream data sources for the analytics and be considered in stream processing.  
    - *(If the data sources have no timestamps associated with records, what would be your solution?)*  
  - (ii) Which types of windows should be developed for the analytics (or explain why no window is needed).  
  - (iii) What could cause out-of-order data/records with your selected data in your running example.  
  - (iv) Whether watermarks are needed or not and explain why.  
- *(1 point)*  

#### (i) Types of Time  
For this tenant’s streaming analytics, **event time** is the primary time.

**Event Time:**  
- **Definition:** The timestamp embedded in the data (e.g., `timestamp=0` in `vm_cpu_readings`).  
- **Example:**  
  A record (`timestamp=100, vm_id=abc, max_cpu=95%`) represents a VM’s CPU reading at the 100th second of the epoch.  
- **Importance:** Enables accurate windowing based on when events actually occurred, critical for detecting anomalies in real-world time.

**If No Timestamps Exist:**  
- **Solution:** Use **processing time** (system clock at ingestion) or infer timestamps from external metadata (e.g., Kafka message ingestion time).  
- **Example:**  
  If raw data lacks timestamps, assign `processing_time = current_time` during ingestion. However, this would limit time-based analytics accuracy.  


#### (ii) Window Types  
**Tumbling windows** (fixed, non-overlapping intervals) are used for this use case.

**Why Tumbling Windows:**  
- **Requirement:** Compute 5-minute averages of `max_cpu` per VM.  
- **Example:**  
  ```python
  # PySpark Structured Streaming
  windowed_agg = df \
      .withWatermark("timestamp", "1 minute") \
      .groupBy("vm_id", window("timestamp", "5 minutes")) \
      .agg(avg("max_cpu").alias("avg_max_cpu"))
  ```  
  This groups records into 5-minute buckets (e.g., `12:00–12:05, 12:05–12:10`).

**Why Not Other Windows?**  
- **Sliding Windows:** Overkill for periodic reporting (e.g., no need for 5-minute averages every 1 minute).  
- **Session Windows:** Irrelevant for evenly spaced telemetry data.  


#### (iii) Causes of Out-of-Order Data  
In the tenant’s scenario, out-of-order data can arise due to:

- **Network Latency:** A VM in a geographically distant region delays transmitting its CPU reading.  
  - *Example:* A record with `timestamp=12:00` arrives at `12:06` due to network congestion.
- **Distributed System Variability:** Parallel data producers (VMs) may emit data at slightly different rates.  
  - *Example:* Two VMs emit `timestamp=12:00` readings, but one is delayed by a garbage collection pause.


#### (iv) Watermarks  
**Watermarks are required** for this use case.

- **Purpose:** Track event-time progress and handle late-arriving data.
- **Configuration:**  
  - A **1-minute watermark tolerance**: `withWatermark("timestamp", "1 minute")`.
  - This allows the system to wait **1 minute** for late data before finalizing window results.
- **Example:**  
  - A record with `timestamp=12:00` arrives at `12:06` (**1 minute late**).
  - The watermark (set to `12:05` at `12:06`) discards this record, as it exceeds the tolerance.

**Why Not Skip Watermarks?**  
- Without watermarks, the streaming system would wait indefinitely for late data, causing **unbounded state growth** and **delayed results**.
- Balance Completeness vs. Latency: Wait long enough to capture most late data, but not so long that results are delayed.

**Trade-offs**:
- Longer Delay: Captures more late data but increases latency/memory usage.
- Shorter Delay: Reduces latency but risks missing late events.


### Summary  
- **Event Time:** Mandatory for accurate VM performance analysis.
- **Tumbling Windows:** Align with periodic reporting needs.
- **Out-of-Order Data:** Inevitable in distributed cloud environments.
- **Watermarks:** Critical to balance latency and completeness in results.

This design ensures robust handling of real-world data quirks while maintaining low-latency alerts for the tenant.

---

## 1.4 Performance Metrics 
- List important performance metrics for the streaming analytics for your tenant cases.  
- For each metric, explain:  
  - (i) Its definition.  
  - (ii) How to measure it in your analytics/platform.  
  - (iii) Its importance and relevance for the analytics of the tenant (for whom/components and for which purposes).  
- *(1 point)*  

- **1. Throughput**  
  - **Definition**: Records processed per second (e.g., VM CPU readings ingested/analyzed per second).  
  - **Measurement**:  
    - Feasible Method: Use Spark Streaming’s `batchDuration` and count records per batch.  
      ```python
      # Log throughput in Spark Streaming (PySpark)
      df.writeStream.foreachBatch(lambda batch_df, batch_id: 
          print(f"Batch {batch_id}: {batch_df.count()} records processed"))
      ```
    - Tools: Spark UI’s "Input Rate" metric or custom logging.  
  - **Relevance**:  
    - Tenant Impact: Ensures the platform handles VM telemetry load (e.g., 1K records/sec).  
    - Component Impact: Identifies Kafka/Spark bottlenecks (e.g., if throughput drops, scale partitions/workers).  

- **2. Processing Latency**  
  - **Definition**: Time taken from data ingestion (Kafka) to result output (Cassandra).  
  - **Measurement**:  
    - Feasible Method: Add timestamps to records during ingestion and log the delta before writing to Cassandra.  
      ```python
      # Pseudocode: Track latency per record
      batch_df = batch_df.withColumn("processing_latency", current_time() - col("ingestion_time"))
      ```
    - Tools: Spark UI’s "Processing Time" metric.  
  - **Relevance**:  
    - Tenant Impact: High latency (>5s) delays anomaly alerts (e.g., VM overloads).  
    - Component Impact: Helps tune Spark parallelism or Kafka consumers.  

- **3. Resource Utilization (CPU/Memory)**  
  - **Definition**: CPU/RAM usage by Spark executors.  
  - **Measurement**:  
    - Feasible Method: Use Spark UI or lightweight tools like `htop`/`docker stats` (if containerized).  
    - Advanced: Export metrics to Prometheus/Grafana (optional for small projects).  
  - **Relevance**:  
    - Tenant Impact: Overloaded workers cause backpressure (stalled processing).  
    - Component Impact: Guides vertical scaling (e.g., increase executor memory).  

- **4. Error Rate**  
  - **Definition**: % of records failing processing (e.g., invalid schemas, parsing errors).  
  - **Measurement**:  
    - Feasible Method: Count exceptions in Spark logs or use a try/catch block:  
      ```python
      try:
        df.writeStream.format("console").start()
      except Exception as e:
        log_error(e)
      ```
  - **Relevance**:  
    - Tenant Impact: High error rates mean missed anomalies (e.g., corrupt CPU data).  
    - Component Impact: Highlights data quality issues (e.g., malformed VM records).  

- **5. Kafka Consumer Lag**  
  - **Definition**: Number of unprocessed messages in Kafka topics.  
  - **Measurement**:  
    - Feasible Method: Use Kafka CLI tools:  
      ```bash
      kafka-consumer-groups --describe --group spark-group
      ```
    - Advanced: Integrate with Burrow (optional).  
  - **Relevance**:  
    - Tenant Impact: Lag >0 indicates Spark can’t keep up (e.g., VM data piles up).  
    - Component Impact: Signals need to scale Spark executors or optimize queries.  

- **6. Watermark Delay**  
  - **Definition**: Gap between event time (VM timestamp) and processing time.  
  - **Measurement**:  
    - Feasible Method: Log watermark in Spark:  
      ```python
      df.withWatermark("timestamp", "1m").groupBy(...)
      ```
      Compare `max_event_time` vs. `current_time` in logs.  
  - **Relevance**:  
    - Tenant Impact: Large delays (>1m) mean late alerts (e.g., VM spikes detected too late).  
    - Component Impact: Adjust watermark tolerance or optimize event-time handling.  

---

## 1.5 Architecture Design  
- Provide a design of your architecture for the streaming analytics service, clarifying:  
  - Tenant data sources.  
  - mysimbdp messaging system.  
  - mysimbdp streaming computing service.  
  - tenantstreamapp.  
  - tenantbatchapp.  
  - mysimbdp-coredms.  
  - Other components, if needed.  
- Explain your choices of technologies for implementing your design and the reusability of existing assignment works.  
- **Note:** In the design, silver data resulted from tenantstreamapp will be sent back to the tenant in near real-time under certain conditions and always be ingested into mysimbdp-coredms.  
- *(1 point)*  

### Components and Technologies

#### 1. **Tenant Data Sources**
- **Component**: Microsoft Cloud Trace dataset (VM CPU readings).
- **Technology**: Pre-loaded CSV/compressed files or a Python data generator.
- **Role**: Emits raw VM telemetry (e.g., `vm_id`, `timestamp`, `max_cpu`).
- **Reusability**: Reuse data schemas from prior assignments (e.g., `vmtable.csv.gz` parsing).

---

#### 2. **mysimbdp Messaging System**
- **Component**: Apache Kafka.
- **Topics**:
  - `raw-vm-metrics`: Raw VM CPU readings.
  - `alerts`: Near-real-time alerts for critical anomalies (e.g., `max_cpu > 90%`).
- **Technology Choice**:
  - High throughput and horizontal scalability.
  - Integrates natively with Spark Structured Streaming.
- **Reusability**: Kafka setup from prior assignments (if available).

---

#### 3. **mysimbdp Streaming Computing Service**
- **Component**: `tenantstreamapp` (Apache Spark Streaming).
- **Technology**: PySpark with `pyspark.sql.streaming`.
- **Functionality**:
  - Reads from Kafka topic `raw-vm-metrics`.
  - Enriches data (e.g., timestamp conversion).
  - Computes 5-minute rolling averages per VM.
  - Detects anomalies (`avg_max_cpu > 90%`).
- **Outputs**:
  - **Silver Data**: Writes to Cassandra (`silver_vm_metrics` table).
  - **Alerts**: Sends critical anomalies to Kafka topic `alerts` for real-time tenant notifications.
- **Reusability**: Spark code from prior batch workflows (adapted for streaming).

---

#### 4. **mysimbdp-coredms**
- **Component**: Apache Cassandra.
- **Tables**:
  - `silver_vm_metrics`: Processed 5-minute aggregates (partitioned by `vm_id` and `window_end`).
  - `gold_vm_recommendations`: Batch analysis results (e.g., VM resizing suggestions).
- **Technology Choice**:
  - Optimized for time-series data (e.g., rolling averages).
  - High write throughput for streaming data.
- **Reusability**: Cassandra schema designs from prior assignments.

---

#### 5. **tenantbatchapp**
- **Component**: Scheduled batch analytics (Apache Spark Batch).
- **Technology**: PySpark with cron jobs or Airflow.
- **Functionality**:
  - Runs daily to analyze `silver_vm_metrics` (e.g., VM overload trends).
  - Generates gold data (e.g., cost optimization recommendations).
  - Writes results to Cassandra (`gold_vm_recommendations`).
- **Reusability**: Reuse Spark batch logic from prior assignments.

---

#### 6. **Monitoring & Logging**
- **Component**: Log files + Spark UI.
- **Metrics Tracked**:
  - Throughput (Spark UI "Input Rate").
  - Kafka consumer lag (`kafka-consumer-groups` CLI).
  - Error rates (Spark executor logs).
- **Technology Choice**: Lightweight for small projects (no Prometheus/Grafana overhead).

---

#### 7. **Ingestion Manager (Optional)**
- **Component**: Python script or shell orchestrator.
- **Role**: Start/stop `tenantstreamapp` instances based on data availability.
- **Reusability**: Scripts from prior assignment submission workflows.

---

### Architecture Flow

```text
Tenant
│
├───▶Data sources
│     │
│     └───▶[Kafka] raw-vm-metrics (Raw VM CPU Data)
│           │
│           └───▶[Spark Streaming] tenantstreamapp
│                 │
│                 ├───▶ [Cassandra] silver_vm_metrics (Silver Data)
│                 │
│                 ├───▶ [Kafka] silver_vm_metrics (Silver Data)
│                 │
│                 └───▶ [Kafka] alerts (Real-Time Anomalies, possible future expansion)
│
└───▶ [Spark Batch] tenantbatchapp (Can be also scheduled for example daily)
       │
       ├───▶ [Kafka] gold_vm_recommendations (Gold Data)
       │
       └───▶ [Cassandra] gold_vm_recommendations (Gold Data)
```
**Legend**:
- ▶ : Data flow direction
- ├── : Pipeline branches
- [] : Component/service
- () : Data type/description

---

## Key Design Choices
1. **Kafka for Dual Roles**:
   - Ingestion (`raw-vm-metrics`) and real-time alerts (`alerts`).
   - Decouples producers (data sources) and consumers (Spark apps).

2. **Cassandra as Unified Storage**:
   - Handles both streaming (high write) and batch (analytical reads) workloads.
   - Time-partitioned tables enable efficient batch processing.

3. **Spark for Hybrid Workloads**:
   - Reuse Spark streaming/batch.
   - Avoid mixing frameworks (e.g., Flink) to reduce complexity.

4. **Lightweight Monitoring**:
   - Spark CLI tools minimize setup effort for small projects.

---

# Part 2 - Implementation of Streaming Analytics  
*(Weighted factor for grades = 3)*

## 2.1 Tenant Streaming Analytics (tenantstreamapp) Implementation  
- As a tenant, implement a tenantstreamapp.  
- For code design and implementation, explain:  
  - (i) The structures/schemas of the input streaming data and the analytics output/result (silver data) in your implementation, the role/importance of such schemas, and the reason to enforce them for input data and results.  
  - (ii) The data serialization/deserialization for the streaming analytics application (tenantstreamapp).  
  - (iii) The logic of the functions for processing events/records in tenantstreamapp in your implementation.  
  - (iv) Under which conditions/configurations and how the results are sent back to the tenant in a near real-time manner.  
- *(1 point)*  

(i) Structures/Schemas

- **Input Data Schema:** The input from Kafka (topic "raw-vm-metrics") is JSON formatted and contains fields such as:
  - `timestamp` (epoch seconds)
  - `vm_id` (string)
  - CPU metrics (e.g., `max_cpu`)
- **Output (Silver) Schema:** After processing, the resulting silver data includes:
  - `vm_id`
  - `window_start` (start timestamp of the window, as a string)
  - `window_end` (end timestamp of the window, as a string)
  - `avg_max_cpu` (the computed average max CPU per window)
  - `is_window_anomaly` (boolean flag if the average exceeds the threshold)
- **Role and Importance:**
  - Schemas enforce consistency and type safety ensuring that downstream processing (e.g., aggregation and anomaly detection) work with well-defined columns.
  - Strict schemas prevent errors and allow Spark to optimize query execution.

(ii) Data Serialization/Deserialization

- **Deserialization:**
  - Kafka messages are consumed as strings.
  - The code uses Spark’s `from_json()` function (along with a schema loaded from a JSON file or hardcoded) to convert the JSON strings into structured DataFrame columns.
- **Serialization:**
  - Before sending processed data to Kafka (or writing to Cassandra), structured silver data is converted back to JSON using `to_json()` to ensure consistency when consumed by other services or tenants.

(iii) Processing Logic

- **Streaming Input:**
  - The application reads from Kafka with configurations like `maxOffsetsPerTrigger` to control the batch size and starting offsets.
- **Timestamp Adjustment and Aggregation:**
  - The raw `timestamp` is adjusted by adding an offset (1546300800 seconds corresponding to January 1, 2019) to shift dates from 1970 to 2019.
  - The adjusted timestamp is then converted into a proper timestamp (`event_time`), which is used for windowed aggregations.
- **Windowing and Anomaly Detection:**
  - Data is grouped by `vm_id` and a tumbling window (3 minutes in the provided implementation).
  - The average max CPU is calculated, and if it exceeds 90%, the record is flagged as an anomaly.
- **Output Preparation:**
  - The resulting columns are formatted, e.g., converting window boundaries to strings, and then forwarded to both a Kafka topic (for real-time alerts) and Cassandra (for storage).

(iv) Near Real-Time Delivery Conditions/Configurations

- **Real-Time Triggering:**
  - The application runs using Spark Structured Streaming as continuous micro-batches.
  - Options like `maxOffsetsPerTrigger` and watermarks (`withWatermark("event_time", "30 seconds")`) balance processing latency and handle out-of-order data.
- **Output Mechanisms:**
  - **Cassandra:** Processed silver data is written to Cassandra using batch insert operations, making it available for near real-time queries by the tenant.
  - **Kafka:** Data is also returned via a Kafka topic (e.g., "silver-vm-metrics"), allowing clients to subscribe and receive alerts as soon as windows are processed.
- **Configuration Effects:**
  - These settings ensure that even under slightly varying data rates, windows are computed promptly and late data is handled appropriately without inducing unbounded state or significant delays.

---

## 2.2 Tenant Batch Analytics (tenantbatchapp) Implementation
- As a tenant, implement tenantbatchapp which is triggered by a predefined schedule.  
- The resulting gold data is also stored into mysimbdp-coredms, but separated from silver data.  
- Explain:  
  - (i) How the input silver data is determined for a run of the batch analytics when no duplicated input data in the batch analytics shall be allowed.  
  - (ii) The workflow structure and the logic of the main function performing the data analysis.  
  - (iii) How the schedule is implemented.  
  - (iv) The underlying service running the workflow.  
- *(1 point)*  

(i) Selecting Input Silver Data Without Duplicates:  
The batch job determines its input by reading the silver data from the Kafka topic "silver-vm-metrics". Deduplication is ensured because each silver record is uniquely identified (e.g., using a composite key such as vm_id and window_start) during streaming. Thus, each batch run processes only the new data received since the last execution.

(ii) Workflow Structure and Main Function Logic:  
- **Data Ingestion:** The batch job creates a Spark session and reads silver data directly from Kafka (topic "silver-vm-metrics").  
- **Parsing and Filtering:** The job parses the JSON messages, converts string timestamps to proper timestamp types, and filters the records based on a specified time interval (e.g., the last 24 hours) provided via command-line parameters.  
- **Aggregation and Analysis:** Per-VM statistics are aggregated (e.g., counting total windows and anomaly windows) to compute anomaly frequency. Based on a threshold, recommendations (e.g., "Upgrade to higher CPU capacity") are generated.  
- **Output Generation:** The final gold data, which includes aggregated metrics, processing timestamp, and the date range, is written both to a Kafka topic (gold-vm-metrics) and to Cassandra in a separate table.

(iii) Scheduling Implementation:  
The batch application is triggered by an external scheduler such as a UNIX cron job or Apache Airflow. For manual execution or testing, it can be run using spark-submit with command-line arguments. For example:
- Process all data (manual run):  
  `docker exec -it kafkaspark-spark-master-1 spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 /opt/bitnami/spark/tenantbatchapp.py --manual`
- Process only the last 24 hours:  
  `docker exec -it kafkaspark-spark-master-1 spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 /opt/bitnami/spark/tenantbatchapp.py --hours 24`
- Daily scheduling is achieved by triggering the above command at midnight.

(iv) Underlying Service Running the Workflow:  
Tenantbatchapp is executed as a Spark batch application via spark-submit on the Spark master container. The external scheduler (e.g., cron or Airflow) is responsible for triggering the batch job at predefined intervals, while Spark manages the distributed processing of the data.

---

## 2.3 Test Environment for Streaming Analytics
- Explain a test environment for testing tenantstreamapp, including:  
  - How you emulate streaming data.  
  - The configuration of mysimbdp and other relevant parameters.  
- Run tenantstreamapp and show the operation of tenantstreamapp with your test environments.  
- Discuss the analytics and its performance observations when you increase/vary the speed of streaming data.  
- *(1 point)*  

### Emulating Streaming Data

- **Kafka Producer as a Data Emulator:**  
  The test environment uses the provided `kafka_producer.py` script to simulate a streaming data source. This script reads from CSV files (e.g., tenant-specific VM CPU readings) and sends records in batches to Kafka’s `raw-vm-metrics` topic. 

- **Controlled Data Injection:**  
  The CSV files serve as preloaded sample data. Although the script could be modified to vary the ingestion speed (e.g., using sleep intervals or adjusting batch sizes), in the current setup, the data is streamed at a constant rate without explicit speed variations.

### Configuration of mysimbdp and Other Parameters

- **Kafka & Spark Setup:**  
  - Kafka is configured via Docker Compose (`docker-compose.yml`) with brokers listening on ports `9092` (internal) and `9093` (external), and topics are auto-created during startup.
  - `tenantstreamapp` is set to use the broker address `kafkaspark-kafka-1:9092`, and the Spark session is configured with a low number of shuffle partitions and backpressure enabled to manage data rates.

- **Cassandra (mysimbdp-coredms):**  
  - Cassandra runs in its dedicated container (`coredbms-cassandra-compose.yml`) and is exposed on port `9042`.
  - Keyspaces and tables (e.g., `silver_vm_metrics`) are used to store processed data.
  - An external shared network (`bigdata-shared-network`) ensures reliable communication between Kafka, Spark, and Cassandra containers.

### Running and Observing `tenantstreamapp` Operation

- **Starting the Environment:**  
  - Start Kafka and Spark services using the provided Docker Compose files under `/data/Kafka&Spark`.
  - Start Cassandra via its Docker Compose configuration under `/External`.

- **Running `tenantstreamapp`:**  
  Execute the tenant streaming application (e.g., via `spark-submit` from the Spark master container). The application:
  - Connects to Kafka and reads messages from the `raw-vm-metrics` topic.
  - Processes incoming records by applying windowing and anomaly detection (timestamps are shifted to start from 2019 due to historic data simulation).
  - Writes processed (silver) data to both Kafka (`silver-vm-metrics` topic) and Cassandra.
  - Prints progress output to the console (displaying windowed events and record insertion counts).

### Observations with Varying Streaming Speeds

- **Current Setup:**  
  - The data ingestion speed has not been explicitly varied via sleep intervals or tuning parameters in the Kafka producer script, though this could be done for further analysis.

- **Potential Performance Effects at Different Data Rates:**  
  - Lower data rates would likely maintain low latency and stable processing.
  - Higher data rates (if explicitly adjusted) could lead to increased processing latency, triggering backpressure mechanisms in Spark.

### Analytics Performance

- **Watermarks and Historic Data:**  
  - Since the simulation uses historic data instead of real-time streaming, watermarks may not be fully effective in handling late-arriving data.
  - The windowing mechanism processes data based on assigned timestamps rather than true event-time streaming.

- **System Performance:**  
  - Monitoring console logs and the Spark UI provides insights into system throughput and latency.
  - The system reliably captures and stores silver data, though performance tuning (e.g., `maxOffsetsPerTrigger`) could be explored further.

### Conclusion

This test environment establishes a complete pipeline where simulated streaming data is ingested via Kafka, processed by `tenantstreamapp` running on Spark, and stored in Cassandra. While the setup provides meaningful insights into stream processing, additional refinements—such as dynamically adjusting ingestion speed and validating watermark effectiveness—could further enhance the evaluation of performance and reliability.


---

## 2.4 Error Handling Tests  
- Present your tests and explain them for the situation in which wrong data is sent from or is within the data sources.  
- Explain how you emulate wrong data for your tests.  
- Report how your implementation deals with that (e.g., exceptions, failures, and decreasing performance).  
- You should test with different error rates.  
- *(1 point)*  

### Test Setup & Emulation of Incorrect Data

- **Fault Injection in Data Sources:**  
  We emulate wrong data by modifying a subset of the CSV input files used by the Kafka producer (`kafka_producer.py`). This is achieved in several ways:
  - **Malformed Records:** Removing required fields or inserting extra/misformatted values (e.g., inserting non-numeric strings in numeric fields).
  - **Schema Deviations:** Changing field order or deliberately corrupting JSON records after conversion.
  - **Error Rate Variation (Hypothetical):** Faulty records could be injected at different error rates (e.g., 5%, 10%, and 20% of total records) to evaluate system resilience.

- **Automated Error Simulation:**  
  The producer script has built-in error handling in its `convert_value()` function. A few records are modified to include invalid data formats (e.g., letters in numeric columns), causing conversion failures and triggering exception handling.

### Error Handling in the Implementation

- **Logging & Record Counting:**  
  In `kafka_producer.py`, errors during CSV value conversion (inside try/except blocks) are caught. The script increments an `invalid_records` counter and logs a message. This mechanism ensures that wrong data is discarded while valid records continue to be sent.

- **Resilience in the Streaming Application:**  
  In `tenantstreamapp.py`, JSON deserialization (using Spark’s `from_json()` function) is enforced with a robust schema. Any record that fails to match the expected schema results in a `null` value, rather than crashing the query. Downstream aggregations (e.g., windowing and anomaly detection) skip such records, ensuring the streaming job continues without major disruption.

### Performance
The system was tested using a sample file containing some errors and confirmed that the system ignores or nullifies those faulty rows without causing a significant performance hit. Testing with different error rate inputs (e.g., 5%, 10%, and 20% of total records) was not evaluated.

This test setup ensures that the streaming analytics application gracefully handles incorrect data by logging and discarding invalid records while maintaining operational continuity.


## 2.5 Parallelism Testing  
- Explain parallelism settings in your implementation (tenantstreamapp) and test with different (higher) degrees of parallelism for at least two instances of tenantstreamapp (e.g., using different subsets of the same dataset).  
- Report the performance and issues you have observed in your testing environments.  
- Is there any situation in which a high value of the application parallelism degree could cause performance problems, given your limited underlying computing resources?  
- *(1 point)*  

---

# Part 3 - Extension  
*(Weighted factor for grades = 2)*  

## 3.1 Integration with an External RESTful Service
  - Assume that you have an external RESTful (micro) service, which accepts a batch of data (processed records), performs an ML inference, and returns the result.  
  - How would you integrate such a service into your current platform and suggest the tenant to use it in the streaming analytics?  
  - Explain what the tenant must do in order to use such a service.  
  - *(1 point)*

To integrate an external RESTful microservice (which accepts a batch of processed records, performs ML inference, and returns results) into our platform, we incorporate a REST call into the streaming pipeline using Spark Structured Streaming's `foreachBatch` functionality. This allows each micro-batch of silver data to be forwarded to the ML service.

### Implementation Strategy

- **Batch Processing in Spark Streaming:**  
  Use the `foreachBatch` function to process each micro-batch. After processing and writing to Cassandra, the batch is sent via an HTTP POST to the external RESTful service.

- **Example Implementation:**
```python
def send_batch_to_ml_service(batch_df, batch_id):
    # Convert the micro-batch DataFrame to a JSON payload
    payload = batch_df.toJSON().collect()
    # Send the payload to the external REST endpoint
    response = requests.post(REST_ENDPOINT, json=payload, timeout=TIMEOUT)
    if response.status_code != 200:
        # Handle errors: log the error and optionally implement retries
        print(f'Error sending batch {batch_id}: {response.status_code}')

# Example integration within Spark streaming:
stream_query = (df.writeStream
                 .foreachBatch(send_batch_to_ml_service)
                 .start())
```

### Tenant Usage Requirements

- **Endpoint Configuration:**  
  Tenants must configure the RESTful service’s endpoint and provide any required authentication (e.g., API keys) via configuration files or environment variables.

- **Data Format Agreement:**  
  The tenant must ensure that the format of the batch data matches the ML service’s expected schema (field names, data types, and handling of missing or invalid values).

- **Error Handling:**  
  Tenants should implement retry policies and error alerts based on the ML service's responses. In our design, failed REST calls are logged and retried in subsequent micro-batches to ensure the workflow is not disrupted.

### Benefits of This Approach

- **Decoupling:**  
  The core streaming analytics remain focused on real-time data ingestion and processing, while the ML inference call is performed as an additional, separate step.

- **Scalability and Flexibility:**  
  Processing at the micro-batch level allows independent updates to the ML service and tenant-specific configurations, catering to varying data volumes and performance requirements.

- **Summary:**  
  Tenants leverage the external ML inference service by configuring the REST endpoint and necessary credentials, receiving processed data batches from the streaming analytics pipeline, and invoking the ML service via embedded HTTP calls. This modular integration provides near real-time enriched insights without compromising the scalability of the overall platform.

---

## 3.2 Trigger for Batch Analytics on Bounded Data
  - Assume that the raw data sent to the messaging system is bounded.  
  - When the raw data is completely processed by tenantstreamapp, the tenantbatchapp will be triggered to do the analytics of silver data resulted from the processing of the raw data.  
  - Present a design for an implementation of the trigger.  
  - *(1 point)*
   
**Design Overview:**

When the raw (bounded) data is fully processed by tenantstreamapp, the system must trigger tenantbatchapp to perform batch analytics on the resulting silver data. This can be achieved by integrating a trigger mechanism that detects stream completion and then signals the batch job to start.

**Possible Implementation Strategies:**

1. **Completion Marker in Kafka or Database:**
   - *Triggering via a Special Message:*  
     At the end of processing the last record in the bounded raw input, tenantstreamapp sends a special “End-of-Stream” (EOS) message or flag to a dedicated Kafka topic (e.g., `streaming-completion`).  
     An external listener monitors this topic and, upon detecting the EOS message, invokes tenantbatchapp (e.g., via a spark-submit call with proper parameters such as the last processed timestamp).
   - *Triggering via Status Update in Cassandra:*  
     Alternatively, tenantstreamapp updates a status flag (e.g., in a `stream_processing_status` table in Cassandra) when processing is complete.  
     A monitoring service periodically polls this status, and once the streaming job is complete, it triggers tenantbatchapp to process the silver data.

2. **Orchestration with an External Scheduler:**
   - *Use of a Workflow Orchestrator:*  
     An external scheduler (such as Apache Airflow or a cron job) is configured to run tenantstreamapp on the bounded input. The orchestrator then detects the job’s completion (using exit status, logs, or a completion file) and automatically triggers tenantbatchapp.  
     This approach provides decoupling between the two jobs while ensuring coordinated execution.

**Tenant Requirements:**
- The tenant must configure shared parameters (e.g., Kafka broker details, Cassandra connection settings, and the completion flag mechanism).  
- The tenant should set up the external orchestration, using either a built-in listener or workflow scheduler, to ensure no silver data is missed and duplicate processing is prevented.

**Summary:**
By using a dedicated completion signal (via a Kafka EOS message or a status flag in Cassandra) or by orchestrating the job execution with an external scheduler, the platform ensures that once tenantstreamapp has fully processed the bounded raw data, tenantbatchapp is automatically triggered to analyze the resulting silver data. This decoupled, coordinated trigger minimizes the risk of duplicate processing and maintains a seamless analytics workflow.

---

## 3.3 Workflow Coordination for Critical Conditions
  - Assume that the streaming analytics detects a critical condition (e.g., a very high rate of alerts) that should trigger the execution of another batch analytics to analyze historical silver data.  
  - The result of this batch analytics will be shared in a cloud storage and a user within the tenant will receive the information about the result.  
  - Explain how you would use workflow technologies to coordinate these interactions and tasks (use a figure to explain your design).  
  - *(1 point)*

### Proposed Workflow Coordination:

#### Detection & Event Signaling:
When the streaming application (`tenantstreamapp`) detects that the alert rate exceeds a predefined threshold, it publishes a special trigger event by writing a flag into a dedicated Kafka topic or updating a status in Cassandra.

#### Workflow Orchestration:
An orchestration tool (e.g., Apache Airflow) continuously monitors for the trigger event. When it receives the critical condition signal, the orchestrator:
- Invokes `tenantbatchapp` (via a spark-submit command) to analyze historical silver data.
- Monitors the batch job execution.
- Once `tenantbatchapp` completes, the orchestrator moves to the next steps.

#### Result Handling & Notification:
The batch job's result is written into cloud storage (such as AWS S3 or Google Cloud Storage) for long-term retention and further analysis. Finally, the orchestrator sends a notification (for example, an email or Slack message) to the tenant user containing a link to the results and a summary of the analysis.

### Illustrative Workflow Diagram:
```
               +-------------------------+
               |  TenantStreamApp        |
               | (Streaming Analytics)   |
               | Detects high alert rate |
               +------------+------------+
                            |
                            v
               +------------+------------+
               | Trigger Event Published |
               | (Kafka flag or status   |
               |  update in Cassandra)   |
               +------------+------------+
                            |
                            v
               +------------+---------------------------+
               |      Workflow Orchestrator             |
               |      (e.g., Apache Airflow)            |
               | Monitors trigger event & initiates job |
               +------------+---------------------------+
                            |
                            v
               +------------+------------+
               | TenantBatchApp Triggered|
               | (Spark Batch Job to     |
               |  analyze historical     |
               |  silver data)           |
               +------------+------------+
                            |
                            v
               +------------+------------+
               |   Batch Job Result      |
               |   Stored in Cloud       |
               |   Storage (S3, GCS)     |
               +------------+------------+
                            |
                            v
               +------------+------------+
               | Tenant Notified via     |
               |  Email/Slack/Webhook    |
               |  with a link & summary  |
               +-------------------------+
```

### Tenant Requirements:

- **Configuration**: The tenant must set up the workflow orchestrator (or use a managed service like Airflow) and provide access to the messaging system, cloud storage, and notification channels.
- **Monitoring & Alerts**: The tenant should configure thresholds for critical conditions and tailor the notification method as needed.
- **Integration Testing**: Regular tests should be conducted to ensure that the trigger, batch job, and notification flows run as expected in production.

---

## 3.4 Handling Schema Evolution
  - Given your choice of technology for implementing your streaming analytics, assume that a new schema of the input data has been developed and new input data follows the new schema (schema evolution).  
  - How would you make sure that the running tenantstreamapp does not handle a wrong schema?  
  - Assume the developer/owner of the tenantstreamapp should be aware of any new schema of the input data before deploying the tenantstreamapp; what could be a possible way that the developer/owner can detect the change of the schemas for the input data?  
  - *(1 point)* 

### Ensuring Correct Schema Handling in Running tenantstreamapp:

**Schema Enforcement at Ingestion:**  
In our implementation, tenantstreamapp explicitly loads its expected schema (from a configuration JSON file) and uses Spark's `from_json()` to parse incoming Kafka messages. This guarantees that only data conforming to the expected schema is processed. In case the input data does not match, the Spark parser will produce null values, which can then be filtered out or logged as errors. For example, if new fields are present or a field is missing, the discrepancy will be exposed during the deserialization phase.

**Validation and Fallback Mechanisms:**  
To prevent processing of data with an unintended schema, additional validation can be built into the application. For instance, before proceeding with the streaming computation, the application can inspect the first few records for critical fields (or a version indicator embedded in the message). If the schema does not match the expected structure, the job can either skip processing or raise an error:

```python
# Pseudocode: Schema validation in streaming application
def validate_schema(batch_df, batch_id):
    # Count records with null fields after json parsing
    null_count = batch_df.filter(col("critical_field").isNull()).count()
    
    # If too many nulls, schema likely changed
    if null_count / batch_df.count() > 0.1:  # 10% threshold
        log.error(f"Schema validation failed: {null_count} nulls in batch {batch_id}")
        raise SchemaValidationError("Detected potential schema mismatch")
```

This ensures that the running tenantstreamapp does not process data that fails schema validation.

### Detecting Schema Changes for the Developer/Owner:

**Schema Registry or Versioning:**  
One effective approach is to employ a schema registry (such as Confluent's Schema Registry) that maintains metadata and version history for the input data schema. By integrating with such a system, the developer/owner can receive notifications (or check an API) when a new schema version is registered. Alternatively, embedding a version field in the input messages allows the tenantstreamapp to detect when the incoming data schema changes unexpectedly.

**Automated Integration Tests:**  
Before deploying a new version of tenantstreamapp, integration tests can be executed where a representative sample of input data is checked against the expected schema. Any deviation can alert the developer through CI/CD pipelines, ensuring that schema evolution is detected prior to deployment.

**Monitoring and Logging Enhancements:**  
Enhancing logging around the `from_json()` operation and monitoring the rate of null or parsing errors can also serve as an early warning. A sudden increase in such errors may indicate that the source schema has changed. Automated dashboards or alerts can then notify the developer to review and update the application.

### Summary:
By explicitly enforcing an expected schema during ingestion, validating messages before they are processed, and leveraging schema registries or embedded version flags, we ensure that tenantstreamapp only processes data with a known schema. Moreover, implementing automated tests and monitoring helps the developer/owner detect any schema changes before deploying tenantstreamapp, thereby preventing unintended processing errors.

---

## 3.5 End-to-End Exactly-Once Delivery

  - Is it possible to achieve end-to-end exactly once delivery in your current tenantstreamapp design and implementation?  
  - If yes, explain why.  
  - If not, what could be conditions and changes to achieve end-to-end exactly once?  
  - If it is impossible to have end-to-end exactly once delivery in your view, explain the reasons.  
  - *(1 point)*

**Current Situation:**  
Our tenantstreamapp is built on Spark Structured Streaming, which—when combined with proper checkpointing—can guarantee exactly-once processing from Kafka sources and into Kafka sinks. However, our design writes processed (silver) data into Cassandra using a custom connector without built-in transactional support. This creates a gap because without idempotent and transactional writes to Cassandra, the end-to-end delivery is not truly exactly once.

**Conditions and Changes to Achieve Exactly-Once:**

1. **Transactional Output:**  
   To achieve end-to-end exactly-once, all output operations must be transactional. For Kafka, configuring the producer for idempotence (with proper retries and acknowledgement settings) and using Spark's checkpointing ensure that each micro-batch is processed exactly once.

2. **Idempotent Writes to Cassandra:**  
   The Cassandra sink must support idempotent operations. This could be done by designing the schema with unique keys and using upsert semantics, or by integrating a connector that offers transactional guarantees.

3. **Coordinated Checkpointing:**  
   All stages (reading, processing, and writing) need to share a common checkpoint to recover consistently in case of failures.

4. **Unified Commit Protocol:**  
   A two-phase commit mechanism could be introduced so that the commit to both Kafka and Cassandra only happens when all stages have succeeded.

**Conclusion:**  
In our current design, exactly-once delivery is not fully achievable end-to-end because the write operations to Cassandra do not support transactions. However, achieving true exactly-once is possible if we:

- Configure Kafka producers for idempotence,
- Use connectors or custom code that enable transactional/upsert writes to Cassandra, and
- Ensure that all processing stages are coordinated via robust checkpointing and commit protocols.

This would require changes to the Cassandra integration layer and potentially adopting additional middleware to support distributed transactions. Until then, our design effectively provides at-least-once semantics with Spark's built-in recovery mechanisms.

