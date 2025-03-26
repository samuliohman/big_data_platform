import laspy
import sys

try:
    # Open the LAS file
    with laspy.open(sys.argv[1]) as fh:
        # Get point format information
        point_format = fh.header.point_format
        print(f"Point format ID: {point_format.id}")
        
        # Get the actual dimensions (attributes) available
        print("\nAvailable point dimensions:")
        for dimension in point_format.dimension_names:
            print(f"- {dimension}")
        
        # Get a sample to show some values
        sample = next(fh.chunk_iterator(5))
        
        # Show example values for first point
        print("\nExample values (first point):")
        for dimension in point_format.dimension_names:
            try:
                value = getattr(sample, dimension)[0]
                print(f"- {dimension}: {value}")
            except:
                print(f"- {dimension}: <unable to retrieve>")

except Exception as e:
    print(f"Error: {e}")