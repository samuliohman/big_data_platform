import time
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from cassandra.query import ConsistencyLevel, BatchStatement, BatchType
import uuid

class CassandraManager:
    def __init__(self, host='localhost', port=9042, keyspace='vm_metrics'):
        self.host = host
        self.port = port
        self.keyspace = keyspace
        self.cluster = None
        self.session = None
        self.max_attempts = 5
        self.silver_insert_stmt = None
        self.gold_insert_stmt = None

    def connect(self):
        """Connect to Cassandra with retry logic"""
        attempt = 0
        connected = False

        while attempt < self.max_attempts and not connected:
            try:
                print(f"Attempt {attempt+1} to connect to Cassandra on {self.host}:{self.port}...")
                
                # Try with increased timeout
                self.cluster = Cluster(
                    [self.host], 
                    port=self.port,
                    connect_timeout=15
                )
                self.session = self.cluster.connect()
                connected = True
                print("Connected to Cassandra!")
            except Exception as e:
                print(f"Failed to connect: {e}")
                attempt += 1
                if attempt < self.max_attempts:
                    print(f"Retrying in 5 seconds...")
                    time.sleep(5)
                else:
                    print("Max attempts reached. Could not connect to Cassandra.")
                    raise

        # Create keyspace if it doesn't exist
        self.session.execute(f"""
            CREATE KEYSPACE IF NOT EXISTS {self.keyspace} 
            WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': '1'}}
        """)

        # Use the keyspace
        self.session.execute(f"USE {self.keyspace}")
        
        # Create tables for VM metrics data
        self._create_tables()
        self._prepare_statements()
        return self

    def _create_tables(self):
        """Create tables for VM metrics data"""
        # Silver data table - Time series data with window aggregations
        self.session.execute("""
            CREATE TABLE IF NOT EXISTS silver_vm_metrics (
                vm_id TEXT,
                window_start TIMESTAMP,
                window_end TIMESTAMP,
                avg_max_cpu DOUBLE,
                is_window_anomaly BOOLEAN,
                PRIMARY KEY ((vm_id), window_start)
            ) WITH CLUSTERING ORDER BY (window_start DESC)
        """)

        # Gold data table - Recommendations based on historical analysis
        self.session.execute("""
            CREATE TABLE IF NOT EXISTS gold_vm_recommendations (
                vm_id TEXT,
                date_range_start TIMESTAMP,
                date_range_end TIMESTAMP,
                total_windows BIGINT,
                anomaly_windows BIGINT,
                overload_frequency DOUBLE,
                recommendation TEXT,
                processed_time TIMESTAMP,
                PRIMARY KEY (vm_id)
            )
        """)

    def _prepare_statements(self):
        """Prepare statements for data insertion"""
        self.silver_insert_stmt = self.session.prepare("""
            INSERT INTO silver_vm_metrics (
                vm_id, window_start, window_end, avg_max_cpu, is_window_anomaly
            ) VALUES (?, ?, ?, ?, ?)
        """)
        self.silver_insert_stmt.consistency_level = ConsistencyLevel.ONE

        self.gold_insert_stmt = self.session.prepare("""
            INSERT INTO gold_vm_recommendations (
                vm_id, date_range_start, date_range_end, total_windows, 
                anomaly_windows, overload_frequency, recommendation, processed_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """)
        self.gold_insert_stmt.consistency_level = ConsistencyLevel.ONE

    def insert_silver_data(self, vm_id, window_start, window_end, avg_max_cpu, is_window_anomaly):
        """Insert a single silver data record"""
        try:
            self.session.execute(
                self.silver_insert_stmt,
                (vm_id, window_start, window_end, avg_max_cpu, is_window_anomaly)
            )
            return True
        except Exception as e:
            print(f"Error inserting silver data: {e}")
            return False

    def batch_insert_silver_data(self, records):
        """Insert multiple silver data records in batch"""
        batch = BatchStatement(batch_type=BatchType.UNLOGGED)
        for record in records:
            batch.add(
                self.silver_insert_stmt,
                (
                    record["vm_id"], 
                    record["window_start"], 
                    record["window_end"], 
                    record["avg_max_cpu"], 
                    record["is_window_anomaly"]
                )
            )
        
        try:
            self.session.execute(batch)
            return True
        except Exception as e:
            print(f"Error batch inserting silver data: {e}")
            return False

    def insert_gold_data(self, vm_id, date_range_start, date_range_end, total_windows,
                        anomaly_windows, overload_frequency, recommendation, processed_time):
        """Insert a gold data record"""
        try:
            self.session.execute(
                self.gold_insert_stmt,
                (
                    vm_id, date_range_start, date_range_end, total_windows,
                    anomaly_windows, overload_frequency, recommendation, processed_time
                )
            )
            return True
        except Exception as e:
            print(f"Error inserting gold data: {e}")
            return False

    def get_silver_data_for_vm(self, vm_id, start_time=None, end_time=None):
        """Retrieve silver data for a specific VM with optional time range"""
        if start_time and end_time:
            query = """
                SELECT vm_id, window_start, window_end, avg_max_cpu, is_window_anomaly
                FROM silver_vm_metrics
                WHERE vm_id = %s AND window_start >= %s AND window_start <= %s
            """
            result = self.session.execute(query, (vm_id, start_time, end_time))
        else:
            query = """
                SELECT vm_id, window_start, window_end, avg_max_cpu, is_window_anomaly
                FROM silver_vm_metrics
                WHERE vm_id = %s
            """
            result = self.session.execute(query, (vm_id,))
        
        return list(result)

    def close(self):
        """Close Cassandra connection"""
        if self.cluster:
            self.cluster.shutdown()