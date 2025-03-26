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

---

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

---

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

---

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

---

### Data Flow and Trigger Logic  

#### How Streaming Feeds into Batch  
- Silver data is stored in Cassandra, partitioned by day (`YYYY-MM-DD`).  
- The batch job processes **only new data** (where `timestamp <= last execution time`).  
- Example:  
  - If the batch job runs on `2025-03-20`, it picks up everything up to `2025-03-19 23:59:59`.  

---

### Why This Approach?  
- **Streaming = Real-Time Response**: Quickly detects CPU spikes so tenants can act fast.  
- **Batch = Long-Term Insights**: Helps with capacity planning and cost optimization.  
- **Cassandra = Perfect Fit**: Handles both high-speed writes (streaming) and historical analysis (batch) efficiently.  

This setup makes full use of the dataset’s time-based structure and works well within our platform's stack (Kafka, Spark, Cassandra).


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

---

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

---

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

---

#### (iii) Causes of Out-of-Order Data  
In the tenant’s scenario, out-of-order data can arise due to:

- **Network Latency:** A VM in a geographically distant region delays transmitting its CPU reading.  
  - *Example:* A record with `timestamp=12:00` arrives at `12:06` due to network congestion.
- **Distributed System Variability:** Parallel data producers (VMs) may emit data at slightly different rates.  
  - *Example:* Two VMs emit `timestamp=12:00` readings, but one is delayed by a garbage collection pause.

---

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

---

### Summary  
- **Event Time:** Mandatory for accurate VM performance analysis.
- **Tumbling Windows:** Align with periodic reporting needs.
- **Out-of-Order Data:** Inevitable in distributed cloud environments.
- **Watermarks:** Critical to balance latency and completeness in results.

This design ensures robust handling of real-world data quirks while maintaining low-latency alerts for the tenant.

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
│                 └───▶ [Kafka] alerts (Real-Time Anomalies)
│
└───▶ [Spark Batch] tenantbatchapp (Can be also scheduled for example daily)
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
   - Spark UI + CLI tools minimize setup effort for small projects.

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

## 2.2 Tenant Batch Analytics (tenantbatchapp) Implementation  
- As a tenant, implement tenantbatchapp which is triggered by a predefined schedule.  
- The resulting gold data is also stored into mysimbdp-coredms, but separated from silver data.  
- Explain:  
  - (i) How the input silver data is determined for a run of the batch analytics when no duplicated input data in the batch analytics shall be allowed.  
  - (ii) The workflow structure and the logic of the main function performing the data analysis.  
  - (iii) How the schedule is implemented.  
  - (iv) The underlying service running the workflow.  
- *(1 point)*  

## 2.3 Test Environment for Streaming Analytics  
- Explain a test environment for testing tenantstreamapp, including:  
  - How you emulate streaming data.  
  - The configuration of mysimbdp and other relevant parameters.  
- Run tenantstreamapp and show the operation of tenantstreamapp with your test environments.  
- Discuss the analytics and its performance observations when you increase/vary the speed of streaming data.  
- *(1 point)*  

## 2.4 Error Handling Tests  
- Present your tests and explain them for the situation in which wrong data is sent from or is within the data sources.  
- Explain how you emulate wrong data for your tests.  
- Report how your implementation deals with that (e.g., exceptions, failures, and decreasing performance).  
- You should test with different error rates.  
- *(1 point)*  

######2.5 Parallelism Testing  
- Explain parallelism settings in your implementation (tenantstreamapp) and test with different (higher) degrees of parallelism for at least two instances of tenantstreamapp (e.g., using different subsets of the same dataset).  
- Report the performance and issues you have observed in your testing environments.  
- Is there any situation in which a high value of the application parallelism degree could cause performance problems, given your limited underlying computing resources?  
- *(1 point)*  

---

# Part 3 - Extension  
*(Weighted factor for grades = 2)*  

## 3.1 Integration with an External RESTful Service  
- How would you integrate an external RESTful service into your platform?  
- Explain what the tenant must do to use such a service.  
- *(1 point)*  

## 3.2 Trigger for Batch Analytics on Bounded Data  
- Design an implementation for a trigger that activates tenantbatchapp when raw data is completely processed by tenantstreamapp.  
- *(1 point)*  

## 3.3 Workflow Coordination for Critical Conditions  
- Explain how workflow technologies coordinate interactions and tasks when a critical condition is detected.  
- *(1 point)*  

## 3.4 Handling Schema Evolution  
- How would you ensure that tenantstreamapp handles the correct schema?  
- How can the developer/owner detect schema changes?  
- *(1 point)*  

## 3.5 End-to-End Exactly-Once Delivery  
- Is exactly-once delivery possible in your design? If not, what changes are needed?  
- *(1 point)*

