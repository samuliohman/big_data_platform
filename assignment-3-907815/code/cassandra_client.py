from cassandra_utils import CassandraManager
import argparse
from datetime import datetime, timedelta
import json

def display_silver_metrics(cassandra, vm_id=None, hours=24):
    """Display silver metrics from Cassandra"""
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    
    if vm_id:
        # Get data for a specific VM
        results = cassandra.get_silver_data_for_vm(vm_id, start_time, end_time)
        print(f"Silver metrics for VM {vm_id} in the last {hours} hours:")
    else:
        # Get all data (this would be a custom query in the real implementation)
        # For simplicity, I'm limiting results
        query = """
            SELECT vm_id, window_start, window_end, avg_max_cpu, is_window_anomaly
            FROM silver_vm_metrics
            LIMIT 100
        """
        results = cassandra.session.execute(query)
        print(f"Recent silver metrics (up to 100 records):")
    
    for row in results:
        print(f"VM: {row.vm_id}, Window: {row.window_start} to {row.window_end}, Avg Max CPU: {row.avg_max_cpu}, Anomaly: {row.is_window_anomaly}")

def display_gold_recommendations(cassandra):
    """Display gold recommendations from Cassandra"""
    query = "SELECT * FROM gold_vm_recommendations"
    results = cassandra.session.execute(query)
    
    print("Gold VM Recommendations:")
    for row in results:
        print(f"VM: {row.vm_id}")
        print(f"  Period: {row.date_range_start} to {row.date_range_end}")
        print(f"  Overload Frequency: {row.overload_frequency * 100:.2f}%")
        print(f"  Recommendation: {row.recommendation}")
        print(f"  Processed at: {row.processed_time}")
        print("---")

def main():
    parser = argparse.ArgumentParser(description="Query VM metrics from Cassandra")
    parser.add_argument("--mode", choices=["silver", "gold"], default="gold", help="Which data to display")
    parser.add_argument("--vm", help="Filter by VM ID (for silver data only)")
    parser.add_argument("--hours", type=int, default=24, help="Hours to look back (for silver data only)")
    parser.add_argument("--host", default="localhost", help="Cassandra host address")
    parser.add_argument("--port", type=int, default=9042, help="Cassandra port")
    parser.add_argument("--keyspace", default="vm_metrics", help="Cassandra keyspace")
    args = parser.parse_args()
    
    try:
        # Create connection with provided connection parameters
        print(f"Connecting to Cassandra at {args.host}:{args.port}...")
        cassandra = CassandraManager(host=args.host, port=args.port, keyspace=args.keyspace).connect()
        
        # Display requested data
        if args.mode == "silver":
            display_silver_metrics(cassandra, args.vm, args.hours)
        else:
            display_gold_recommendations(cassandra)
            
        # Close connection
        cassandra.close()
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nTroubleshooting tips:")
        print("1. Ensure Cassandra container is running: docker ps | grep cassandra")
        print("2. Check if port mapping is correct: docker port external-cassandra1-1")
        print("3. Try connecting with different ports (9042, 9043, or 9044)")
        print("4. Make sure cassandra_utils.py is in the same directory")

if __name__ == "__main__":
    main()