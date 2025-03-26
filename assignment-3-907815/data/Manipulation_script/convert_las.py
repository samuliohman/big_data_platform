import laspy
import csv
import sys

# Number of points to process at a time
CHUNK_SIZE = 100000
# Maximum number of points to extract (set to None for all)
MAX_POINTS = 500000

try:
    # Check command line arguments
    if len(sys.argv) < 3:
        print("Usage: python3 convert_las.py input.las output.csv")
        sys.exit(1)
        
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    points_processed = 0
    
    # Define all dimensions based on the list_attributes.py output
    dimensions = [
        'X', 'Y', 'Z', 'intensity', 'return_number', 'number_of_returns',
        'scan_direction_flag', 'edge_of_flight_line', 'classification',
        'synthetic', 'key_point', 'withheld', 'scan_angle_rank',
        'user_data', 'point_source_id', 'gps_time', 'wavepacket_index',
        'wavepacket_offset', 'wavepacket_size', 'return_point_wave_location',
        'x_t', 'y_t', 'z_t'
    ]
    
    # Open CSV file for writing
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(dimensions)  # Write header with all dimensions
        
        # Use chunked reading to avoid loading entire file
        with laspy.open(input_file) as fh:
            for points in fh.chunk_iterator(CHUNK_SIZE):
                # Process each point in this chunk
                chunk_size = len(points.X)
                for i in range(chunk_size):
                    # Create a row with all dimension values
                    row = []
                    for dim in dimensions:
                        try:
                            row.append(getattr(points, dim)[i])
                        except (AttributeError, IndexError) as e:
                            row.append(None)  # Use None if attribute can't be retrieved
                    
                    writer.writerow(row)
                
                points_processed += chunk_size
                print(f"Processed {points_processed} points...")
                
                # Stop if we've reached the maximum number of points
                if MAX_POINTS and points_processed >= MAX_POINTS:
                    break
    
    print(f"Successfully converted {points_processed} points to {output_file}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()