from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import ExecutionProfile
import laspy
import numpy as np
import logging
from tqdm import tqdm
import sys
import argparse
from cassandra.policies import DCAwareRoundRobinPolicy, RetryPolicy
from cassandra.query import dict_factory
from cassandra import ConsistencyLevel

# Configure logging
logging.basicConfig(
    filename='ingestion_log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))  # Add console logging

# Add argument parser
def parse_args():
    parser = argparse.ArgumentParser(description='Ingest LAS data into Cassandra')
    parser.add_argument('--nodes', nargs='+', required=True,
                       help='List of Cassandra node IPs')
    return parser.parse_args()

def connect_to_cassandra(nodes):
    """Connect to Cassandra cluster using provided IPs."""
    seed_node = nodes[0]
    print(f"Attempting to connect to seed node: {seed_node}")
    
    default_profile = ExecutionProfile(
        load_balancing_policy=DCAwareRoundRobinPolicy(local_dc='dc1'),
        retry_policy=RetryPolicy(),
        consistency_level=ConsistencyLevel.ONE,
        request_timeout=60,  # Move timeout here
        row_factory=dict_factory
    )

    cluster = Cluster(
        seed_node,
        port=9042,
        protocol_version=4,
        connect_timeout=30,
        execution_profiles={
            'default': default_profile
        },
        compression=True,
        idle_heartbeat_interval=30
    )
    
    try:
        session = cluster.connect()
        print("Connected to cluster")
        logging.info(f"Connected to Cassandra cluster at {nodes}")
        return session
    except Exception as e:
        print(f"Connection error: {str(e)}")
        logging.error(f"Failed to connect: {str(e)}")
        raise

def create_schema(session):
    """Create keyspace and table for LAS data."""
    try:
        # Create keyspace
        session.execute("""
            CREATE KEYSPACE IF NOT EXISTS well_data
            WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 2}
        """)
        
        # Switch to keyspace
        session.set_keyspace('well_data')
        
        # Create table for LAS data
        session.execute("""
            CREATE TABLE IF NOT EXISTS las_data (
                depth float,
                measurement_type text,
                value float,
                well_id text,
                PRIMARY KEY ((well_id), depth, measurement_type)
            )
        """)
        logging.info("Schema created successfully")
    except Exception as e:
        logging.error(f"Failed to create schema: {str(e)}")
        raise

def process_las_file(filepath, batch_size=1000):
    """Process LiDAR LAS file in batches."""
    try:
        las = laspy.read(filepath)
        well_id = filepath.split('/')[-1].split('.')[0]
        
        # Get point cloud data
        points = np.stack([las.x, las.y, las.z], axis=0).transpose()
        total_points = len(points)
        
        # Prepare data in batches
        batch = []
        with tqdm(total=total_points, desc="Processing LAS data") as pbar:
            for i, point in enumerate(points):
                batch.append({
                    'depth': float(point[2]),  # z coordinate as depth
                    'measurement_type': 'x',    # store x coordinate
                    'value': float(point[0]),
                    'well_id': well_id
                })
                batch.append({
                    'depth': float(point[2]),  # z coordinate as depth
                    'measurement_type': 'y',    # store y coordinate
                    'value': float(point[1]),
                    'well_id': well_id
                })
                
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
                pbar.update(1)
            
            if batch:  # Don't forget the last batch
                yield batch

    except Exception as e:
        logging.error(f"Failed to process LAS file: {str(e)}")
        raise

def ingest_data(session, filepath, batch_size=5000):
    """Ingest LAS data into Cassandra in batches."""
    try:
        print(f"Starting data ingestion from {filepath}")  # Add debug print
        # Prepare batch statement
        batch_statement = """
            BEGIN BATCH
            INSERT INTO well_data.las_data (depth, measurement_type, value, well_id)
            VALUES (?, ?, ?, ?)
            INSERT INTO well_data.las_data (depth, measurement_type, value, well_id)
            VALUES (?, ?, ?, ?)
            APPLY BATCH
        """
        insert_prepared = session.prepare(batch_statement)
        
        total_processed = 0
        for batch in process_las_file(filepath, batch_size * 2):  # Double batch size since we're processing pairs
            # Process points in pairs (x,y for same depth)
            for i in range(0, len(batch), 2):
                if i + 1 >= len(batch):
                    break
                    
                point_x = batch[i]
                point_y = batch[i + 1]
                
                # Execute batch insert for x,y pair
                session.execute(insert_prepared, 
                    (point_x['depth'], point_x['measurement_type'], point_x['value'], point_x['well_id'],
                     point_y['depth'], point_y['measurement_type'], point_y['value'], point_y['well_id'])
                )
                
            total_processed += len(batch)
            print(f"Processed {total_processed} measurements")  # Add debug print
            logging.info(f"Processed {total_processed} measurements")
            
    except Exception as e:
        print(f"Ingestion error: {str(e)}")  # Add debug print
        logging.error(f"Failed to ingest data: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        args = parse_args()
        # Connect to cluster
        session = connect_to_cassandra(args.nodes)
        
        # Create schema
        create_schema(session)
        
        # Ingest data
        filepath = "./raw_data/nyu_2451_38660_las/F_150326_131440.las"
        ingest_data(session, filepath)
        
        logging.info("Data ingestion completed successfully")
        
    except Exception as e:
        logging.error(f"Script failed: {str(e)}")
        sys.exit(1)