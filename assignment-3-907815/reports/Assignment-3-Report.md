### Part 1 - Design for Streaming Analytics  
*(Weighted factor for grades = 3)*

#### 1.1 Dataset Selection and Analytics Design  
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

# Dataset Selection and Suitability for Streaming Analytics

## Raw Dataset
We're working with the `vm_cpu_readings-file-*-of-195.csv.gz` subset from the Microsoft Cloud Trace dataset.

### Why This Dataset?
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

# Streaming Analytics (`tenantstreamapp`)

## What It Does
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

# Batch Analytics (`tenantbatchapp`)

## What It Does
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

# Data Flow and Trigger Logic

## How Streaming Feeds into Batch
- Silver data is stored in Cassandra, partitioned by day (`YYYY-MM-DD`).
- The batch job processes **only new data** (where `timestamp <= last execution time`).
- Example:
  - If the batch job runs on `2025-03-20`, it picks up everything up to `2025-03-19 23:59:59`.

---

# Why This Approach?
- **Streaming = Real-Time Response**: Quickly detects CPU spikes so tenants can act fast.
- **Batch = Long-Term Insights**: Helps with capacity planning and cost optimization.
- **Cassandra = Perfect Fit**: Handles both high-speed writes (streaming) and historical analysis (batch) efficiently.

This setup makes full use of the dataset’s time-based structure and works well within our platform's stack (Kafka, Spark, Cassandra).


#### 1.2 Messaging System Considerations  
- The tenant will send raw data through a messaging system, which provides stream data sources.  
- Discuss, explain, and give examples for:  
  - (i) Whether the streaming analytics should handle keyed or non-keyed data streams for the tenant data.  
  - (ii) Which types of message delivery guarantees should be suitable for the stream analytics and why.  
- *(1 point)*  

#### 1.3 Time, Windowing, and Data Order  
- Given streaming data from the tenant, explain and give examples for:  
  - (i) Which types of time should be associated with stream data sources for the analytics and be considered in stream processing.  
    - *(If the data sources have no timestamps associated with records, what would be your solution?)*  
  - (ii) Which types of windows should be developed for the analytics (or explain why no window is needed).  
  - (iii) What could cause out-of-order data/records with your selected data in your running example.  
  - (iv) Whether watermarks are needed or not and explain why.  
- *(1 point)*  

#### 1.4 Performance Metrics  
- List important performance metrics for the streaming analytics for your tenant cases.  
- For each metric, explain:  
  - (i) Its definition.  
  - (ii) How to measure it in your analytics/platform.  
  - (iii) Its importance and relevance for the analytics of the tenant (for whom/components and for which purposes).  
- *(1 point)*  

#### 1.5 Architecture Design  
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

---

### Part 2 - Implementation of Streaming Analytics  
*(Weighted factor for grades = 3)*

#### 2.1 Tenant Streaming Analytics (tenantstreamapp) Implementation  
- As a tenant, implement a tenantstreamapp.  
- For code design and implementation, explain:  
  - (i) The structures/schemas of the input streaming data and the analytics output/result (silver data) in your implementation, the role/importance of such schemas, and the reason to enforce them for input data and results.  
  - (ii) The data serialization/deserialization for the streaming analytics application (tenantstreamapp).  
  - (iii) The logic of the functions for processing events/records in tenantstreamapp in your implementation.  
  - (iv) Under which conditions/configurations and how the results are sent back to the tenant in a near real-time manner.  
- *(1 point)*  

#### 2.2 Tenant Batch Analytics (tenantbatchapp) Implementation  
- As a tenant, implement tenantbatchapp which is triggered by a predefined schedule.  
- The resulting gold data is also stored into mysimbdp-coredms, but separated from silver data.  
- Explain:  
  - (i) How the input silver data is determined for a run of the batch analytics when no duplicated input data in the batch analytics shall be allowed.  
  - (ii) The workflow structure and the logic of the main function performing the data analysis.  
  - (iii) How the schedule is implemented.  
  - (iv) The underlying service running the workflow.  
- *(1 point)*  

#### 2.3 Test Environment for Streaming Analytics  
- Explain a test environment for testing tenantstreamapp, including:  
  - How you emulate streaming data.  
  - The configuration of mysimbdp and other relevant parameters.  
- Run tenantstreamapp and show the operation of tenantstreamapp with your test environments.  
- Discuss the analytics and its performance observations when you increase/vary the speed of streaming data.  
- *(1 point)*  

#### 2.4 Error Handling Tests  
- Present your tests and explain them for the situation in which wrong data is sent from or is within the data sources.  
- Explain how you emulate wrong data for your tests.  
- Report how your implementation deals with that (e.g., exceptions, failures, and decreasing performance).  
- You should test with different error rates.  
- *(1 point)*  

#### 2.5 Parallelism Testing  
- Explain parallelism settings in your implementation (tenantstreamapp) and test with different (higher) degrees of parallelism for at least two instances of tenantstreamapp (e.g., using different subsets of the same dataset).  
- Report the performance and issues you have observed in your testing environments.  
- Is there any situation in which a high value of the application parallelism degree could cause performance problems, given your limited underlying computing resources?  
- *(1 point)*  

---

### Part 3 - Extension  
*(Weighted factor for grades = 2)*  

#### 3.1 Integration with an External RESTful Service  
- How would you integrate an external RESTful service into your platform?  
- Explain what the tenant must do to use such a service.  
- *(1 point)*  

#### 3.2 Trigger for Batch Analytics on Bounded Data  
- Design an implementation for a trigger that activates tenantbatchapp when raw data is completely processed by tenantstreamapp.  
- *(1 point)*  

#### 3.3 Workflow Coordination for Critical Conditions  
- Explain how workflow technologies coordinate interactions and tasks when a critical condition is detected.  
- *(1 point)*  

#### 3.4 Handling Schema Evolution  
- How would you ensure that tenantstreamapp handles the correct schema?  
- How can the developer/owner detect schema changes?  
- *(1 point)*  

#### 3.5 End-to-End Exactly-Once Delivery  
- Is exactly-once delivery possible in your design? If not, what changes are needed?  
- *(1 point)*  

