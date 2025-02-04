from cassandra.cluster import Cluster
import json
import logging

# Configure logging
logging.basicConfig(filename='../logs/ingestion_log.txt', level=logging.INFO)

def connect_to_cassandra():
    """Connect to Cassandra and return the session."""
    cluster = Cluster(['127.0.0.1'])  # Update with external IP if running remotely
    session = cluster.connect()
    session.set_keyspace('mysimbdp_keyspace')
    return session

def create_schema(session):
    """Create a simple schema for data storage."""
    session.execute("""
        CREATE TABLE IF NOT EXISTS user_data (
            id UUID PRIMARY KEY,
            name TEXT,
            age INT,
            city TEXT
        )
    """)

def ingest_data(session, file_path):
    """Load JSON data and insert it into Cassandra."""
    with open(file_path, 'r') as file:
        data = json.load(file)
        for record in data:
            session.execute(
                """
                INSERT INTO user_data (id, name, age, city)
                VALUES (uuid(), %s, %s, %s)
                """,
                (record['name'], record['age'], record['city'])
            )
    logging.info("Data ingestion completed successfully.")

if __name__ == "__main__":
    session = connect_to_cassandra()
    create_schema(session)
    ingest_data(session, 'sample_data.json')
