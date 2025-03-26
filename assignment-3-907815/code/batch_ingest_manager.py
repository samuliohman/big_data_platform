# batch_ingest_manager.py
import sys
import os
import time
import subprocess
import json
import schedule
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class LasFileHandler(FileSystemEventHandler):
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id
        os.makedirs("../logs", exist_ok=True)
        
    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith('.las'):
            print(f"New LAS file detected: {event.src_path}")
            self._process_file(event.src_path)
    
    def _process_file(self, file_path):
        """Process a new LAS file using the chunker"""
        print(f"Submitting {file_path} for processing...")
        
        # Start processing in a separate process
        subprocess.Popen([sys.executable, 'las_chunker.py', file_path])
        
class BatchIngestManager:
    def __init__(self, tenant_dirs):
        """Initialize the batch ingestion manager
        
        Args:
            tenant_dirs: Dictionary mapping tenant IDs to their staging directories
        """
        self.tenant_dirs = tenant_dirs
        self.observers = []
    
    def start(self):
        """Start monitoring all tenant directories"""
        for tenant_id, directory in self.tenant_dirs.items():
            print(f"Monitoring directory for tenant {tenant_id}: {directory}")
            
            # Ensure directory exists
            os.makedirs(directory, exist_ok=True)
            
            # Create an observer for this directory
            event_handler = LasFileHandler(tenant_id)
            observer = Observer()
            observer.schedule(event_handler, directory, recursive=False)
            observer.start()
            
            self.observers.append(observer)
        
        print("Batch ingestion manager started. Press Ctrl+C to stop.")
    
    def stop(self):
        """Stop all directory observers"""
        for observer in self.observers:
            observer.stop()
        
        for observer in self.observers:
            observer.join()
        
        print("Batch ingestion manager stopped.")

def check_for_existing_files(tenant_dirs):
    """Check for existing LAS files in the monitored directories"""
    for tenant_id, directory in tenant_dirs.items():
        if not os.path.exists(directory):
            continue
            
        for filename in os.listdir(directory):
            if filename.lower().endswith('.las'):
                file_path = os.path.join(directory, filename)
                
                # Process existing files
                handler = LasFileHandler(tenant_id)
                handler._process_file(file_path)

if __name__ == "__main__":
    # Configure tenant directories
    tenant_dirs = {
        "tenantA": "../data/tenantA",
        "tenantB": "../data/tenantB",
        "tenantC": "../data/tenantC"
    }
    
    # Ensure logs directory exists
    os.makedirs("../logs", exist_ok=True)
    
    # Create staging directories
    for directory in tenant_dirs.values():
        os.makedirs(directory, exist_ok=True)
    
    # Process any existing files
    check_for_existing_files(tenant_dirs)
    
    # Start the manager
    manager = BatchIngestManager(tenant_dirs)
    
    try:
        manager.start()
        
        # Keep the script running
        counter = 0
        while True:
            time.sleep(1)
            counter += 1
            if counter % 60 == 0:  # Every minute
                print(f"Still monitoring directories for new files... ({time.strftime('%H:%M:%S')})")
    except KeyboardInterrupt:
        manager.stop()