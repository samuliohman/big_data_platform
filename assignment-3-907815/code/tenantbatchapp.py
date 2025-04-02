from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, to_timestamp, count, lit, when, current_timestamp, from_unixtime
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, BooleanType, ArrayType
import json
import os
import argparse
from datetime import datetime, timedelta
from cassandra_utils import CassandraManager

BROKER_ADDRESS = "kafkaspark-kafka-1:9092"
CASSANDRA_HOST = "cassandra1"  # Hostname of the first Cassandra node

def load_silver_schema():
    """Define schema for the silver data"""
    return StructType([
        StructField("vm_id", StringType(), True),
        StructField("window_start", StringType(), True),
        StructField("window_end", StringType(), True),
        StructField("avg_max_cpu", DoubleType(), True),
        StructField("is_window_anomaly", BooleanType(), True)
    ])

def load_config():
    """Load configuration settings"""
    # You can extend this to read from a config file
    return {
        "anomaly_threshold": 90.0,  # CPU percentage threshold for anomalies
        "frequency_threshold": 0.8,  # 80% threshold for recommendation
        "lookback_hours": 24,        # Hours of historical data to analyze
    }

def create_spark_session():
    """Create the Spark session with necessary configurations"""
    return (SparkSession
            .builder
            .appName("TenantBatchApp")
            .config("spark.sql.shuffle.partitions", "8")
            .config("spark.memory.fraction", "0.8")
            .master("local[2]")
            .getOrCreate())

def process_data(spark, silver_schema, config, start_time=None, end_time=None):
    """Process silver data to create gold data with recommendations"""
    print(f"Starting batch processing from {start_time} to {end_time}...")
    
    # Read silver data from Kafka
    silver_df = (spark
                 .read
                 .format("kafka")
                 .option("kafka.bootstrap.servers", BROKER_ADDRESS)
                 .option("subscribe", "silver-vm-metrics")
                 .option("startingOffsets", "earliest")
                 .option("endingOffsets", "latest")
                 .load())
    
    # Parse the Kafka messages
    parsed_df = silver_df.selectExpr("CAST(value AS STRING) as json_data")
    
    # Parse the JSON data
    silver_df = parsed_df.select(from_json(col("json_data"), silver_schema).alias("data")).select("data.*")
    
    # Convert string timestamps to actual timestamps
    silver_df = silver_df.withColumn("start_ts", to_timestamp(col("window_start")))
    silver_df = silver_df.withColumn("end_ts", to_timestamp(col("window_end")))
    
    # Filter by time range if specified
    if start_time and end_time:
        silver_df = silver_df.filter(
            (col("start_ts") >= start_time) & 
            (col("end_ts") <= end_time)
        )
    
    # Count total windows and anomaly windows per VM
    vm_stats = silver_df.groupBy("vm_id").agg(
        count("*").alias("total_windows"),
        count(when(col("is_window_anomaly") == True, True)).alias("anomaly_windows")
    )
    
    # Calculate anomaly frequency and generate recommendations
    gold_df = vm_stats.withColumn(
        "overload_frequency", 
        (col("anomaly_windows") / col("total_windows"))
    ).withColumn(
        "recommendation",
        when(col("overload_frequency") >= config["frequency_threshold"], 
             "Upgrade to higher CPU capacity")
        .otherwise("Current configuration is adequate")
    ).withColumn(
        "processed_time", 
        current_timestamp()
    )
    
    # If we have time range, add it to the output
    if start_time and end_time:
        gold_df = gold_df.withColumn("date_range_start", lit(start_time.strftime("%Y-%m-%d %H:%M:%S")))
        gold_df = gold_df.withColumn("date_range_end", lit(end_time.strftime("%Y-%m-%d %H:%M:%S")))
    
    return gold_df

def write_gold_to_cassandra(gold_df):
    """Write gold data to Cassandra"""
    try:
        # Create Cassandra connection
        cassandra = CassandraManager(host=CASSANDRA_HOST).connect()
        
        # Collect data from DataFrame
        for row in gold_df.collect():
            # Format date range properly
            date_range_start = None
            date_range_end = None
            if hasattr(row, 'date_range_start'):
                date_range_start = datetime.strptime(row.date_range_start, "%Y-%m-%d %H:%M:%S")
            if hasattr(row, 'date_range_end'):
                date_range_end = datetime.strptime(row.date_range_end, "%Y-%m-%d %H:%M:%S")
            
            # Insert gold data
            cassandra.insert_gold_data(
                row.vm_id,
                date_range_start,
                date_range_end,
                row.total_windows,
                row.anomaly_windows,
                row.overload_frequency,
                row.recommendation,
                datetime.now()
            )
        
        print(f"Inserted {gold_df.count()} gold records to Cassandra")
        
        # Close connection
        cassandra.close()
        return True
    except Exception as e:
        print(f"Error writing gold data to Cassandra: {e}")
        return False

def main():
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description='Process silver data to generate gold recommendations')
        parser.add_argument('--hours', type=int, default=24, help='Number of hours to look back')
        parser.add_argument('--manual', action='store_true', help='Run manual processing of all data')
        args = parser.parse_args()
        
        # Create Spark session
        spark = create_spark_session()
        spark.sparkContext.setLogLevel("WARN")
        
        # Load configuration
        config = load_config()
        config["lookback_hours"] = args.hours
        
        # Load schema
        silver_schema = load_silver_schema()
        
        # Set time range for processing
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=config["lookback_hours"])
        
        # For manual processing, use all data
        if args.manual:
            start_time = None
            end_time = None
        
        # Process data
        gold_df = process_data(spark, silver_schema, config, start_time, end_time)
        
        # Show results
        print("Gold Data Results:")
        gold_df.show(truncate=False)
        
        # Write to Kafka gold topic
        gold_kafka_df = gold_df.selectExpr(
            "vm_id AS key", 
            "to_json(struct(*)) AS value"
        )
        
        gold_kafka_df.write \
            .format("kafka") \
            .option("kafka.bootstrap.servers", BROKER_ADDRESS) \
            .option("topic", "gold-vm-metrics") \
            .save()
        
        print("Gold data written to Kafka topic 'gold-vm-metrics'")
        
        # Write to Cassandra
        success = write_gold_to_cassandra(gold_df)
        if success:
            print("Gold data successfully written to Cassandra")
        
        spark.stop()
        print("Batch processing completed successfully")
    except Exception as e:
        import traceback
        print(f"ERROR: {str(e)}")
        print(traceback.format_exc())
        spark.stop()
        return

if __name__ == "__main__":
    main()