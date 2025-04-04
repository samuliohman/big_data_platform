from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, to_timestamp, expr, window, when, lit, from_unixtime
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType, BooleanType
from datetime import datetime
import os
import json
from cassandra_utils import CassandraManager

BROKER_ADDRESS = "kafkaspark-kafka-1:9092"
CASSANDRA_HOST = "cassandra1"  # Hostname of the first Cassandra node

def load_schema_from_json(file_path):
    """Load schema from a JSON file"""
    try:
        with open(file_path, 'r') as schema_file:
            schema_json = json.load(schema_file)
            fields = schema_json.get("fields", [])
            
            schema = StructType([
                StructField(field["name"], 
                           eval(field["type"].capitalize() + "Type()"),
                           field.get("nullable", True))
                for field in fields
            ])
            return schema
    except Exception as e:
        print(f"Error loading schema: {e}")
        # Fallback to hardcoded schema
        return StructType([
            StructField("timestamp", LongType(), True),
            StructField("vm_id", StringType(), True),
            StructField("min_cpu", DoubleType(), True),
            StructField("max_cpu", DoubleType(), True),
            StructField("avg_cpu", DoubleType(), True)
        ])

def create_spark_session():
    """Create the Spark session with necessary configurations"""
    return (SparkSession
            .builder
            .appName("TenantStreamingApp")
            # Memory optimization
            .config("spark.sql.shuffle.partitions", "8")  # Drastically reduce partitions
            .config("spark.memory.fraction", "0.8")
            .config("spark.memory.storageFraction", "0.3")
            # Streaming optimizations
            .config("spark.streaming.kafka.maxRatePerPartition", "100")  # Limit rate
            .config("spark.streaming.backpressure.enabled", "true")  # Enable backpressure
            .master("local[2]")  # Reduce cores to 2 instead of all
            .getOrCreate())

def write_to_cassandra(batch_df, batch_id):
    """Write batch data to Cassandra"""
    try:
        # Create Cassandra connection for this batch
        cassandra = CassandraManager(host=CASSANDRA_HOST).connect()
        
        # Collect data from DataFrame
        records = []
        for row in batch_df.collect():
            records.append({
                "vm_id": row.vm_id,
                "window_start": datetime.strptime(row.window_start, "%Y-%m-%d %H:%M:%S"),
                "window_end": datetime.strptime(row.window_end, "%Y-%m-%d %H:%M:%S"),
                "avg_max_cpu": row.avg_max_cpu,
                "is_window_anomaly": row.is_window_anomaly
            })
        
        # Insert data in batches
        if records:
            success = cassandra.batch_insert_silver_data(records)
            print(f"Batch {batch_id}: Inserted {len(records)} records to Cassandra ({success})")
        
        # Close connection
        cassandra.close()
    except Exception as e:
        print(f"Error writing batch {batch_id} to Cassandra: {e}")

def main():
    # Create Spark session with optimized settings
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    # Load schema from JSON file
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "configuration.json")
    cpu_schema = load_schema_from_json(schema_path)
    
    print("Starting tenant streaming application...")
    
    # Read from Kafka - add maxOffsetsPerTrigger to limit batch size
    raw_df = (spark
              .readStream
              .format("kafka")
              .option("kafka.bootstrap.servers", BROKER_ADDRESS)
              .option("subscribe", "raw-vm-metrics")
              .option("startingOffsets", "earliest")
              .option("maxOffsetsPerTrigger", 1000)  # Process smaller batches
              .load())
    
    # Parse the Kafka messages
    parsed_df = raw_df.selectExpr("CAST(value AS STRING) as json_data")
    
    # Parse the JSON data
    cpu_df = parsed_df.select(from_json(col("json_data"), cpu_schema).alias("data")).select("data.*")
    
    # Convert timestamp and mark anomalies in one step
    cpu_df = cpu_df.withColumn("adjusted_timestamp", col("timestamp") + 1546300800) \
                   .withColumn("event_time", to_timestamp(col("adjusted_timestamp"))) \
                   .withColumn("is_anomaly", when(col("max_cpu") > 90.0, True).otherwise(False))
    
    # Use a shorter window to reduce state size
    windowed_df = cpu_df \
        .withWatermark("event_time", "30 seconds") \
        .groupBy(col("vm_id"), window(col("event_time"), "3 minutes")) \
        .agg({"max_cpu": "avg"}) \
        .withColumnRenamed("avg(max_cpu)", "avg_max_cpu") \
        .select(
            col("vm_id"),
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            col("avg_max_cpu"),
            when(col("avg_max_cpu") > 90.0, True).otherwise(False).alias("is_window_anomaly")
        )
    
    # Prepare silver data for output
    silver_df = windowed_df.selectExpr(
        "vm_id", 
        "CAST(window_start AS STRING) as window_start", 
        "CAST(window_end AS STRING) as window_end", 
        "avg_max_cpu", 
        "is_window_anomaly"
    )
    
    # Write to console only for testing
    console_query = (silver_df
                     .writeStream
                     .format("console")
                     .outputMode("update")
                     .option("truncate", "false")
                     .option("numRows", 10)  # Show fewer rows
                     .start())
    
    # Write to Kafka silver topic
    silver_query = (silver_df
                    .selectExpr("vm_id AS key", "to_json(struct(*)) AS value")
                    .writeStream
                    .format("kafka")
                    .option("kafka.bootstrap.servers", BROKER_ADDRESS)
                    .option("topic", "silver-vm-metrics")
                    .option("checkpointLocation", "/tmp/checkpoint/silver")
                    .option("maxOffsetsPerTrigger", 500)
                    .outputMode("update")
                    .start())
    
    # Write to Cassandra
    cassandra_query = (silver_df
                       .writeStream
                       .foreachBatch(write_to_cassandra)
                       .outputMode("update")
                       .option("checkpointLocation", "/tmp/checkpoint/cassandra")
                       .start())
    
    # Wait for termination
    spark.streams.awaitAnyTermination()

if __name__ == "__main__":
    main()