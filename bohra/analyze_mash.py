import pandas as pd
import re
import argparse

def analyze_mash_distances(matrix_file, metadata_file, query_sequence, metadata_columns=None, output_file=None, all_samples=False):
    """
    Analyze mash distances for a given query sequence and annotate with metadata
    
    Parameters:
    matrix_file (str): Path to the mash distance matrix file
    metadata_file (str): Path to the metadata CSV file
    query_sequence (str): Query sequence identifier
    metadata_columns (list): List of metadata columns to include [default: geoLocName, country]
    output_file (str): Optional output file path for annotations
    all_samples (bool): If True, process all distances, not just top 20
    """
    # Set default metadata columns if not provided
    if metadata_columns is None:
        metadata_columns = ['geoLocName', 'country']
    
    # Read the matrix file
    print(f"Reading matrix file: {matrix_file}")
    df = pd.read_csv(matrix_file, sep="\t", index_col=0)
    
    # Clean index by removing any whitespace
    df.index = df.index.str.strip()
    
    # Read the metadata file
    print(f"Reading metadata file: {metadata_file}")
    metadata_df = pd.read_csv(metadata_file)
    
    # Select the columns that contain the query sequence
    query_df = df.filter(regex=query_sequence)
    
    # Sort by distance values
    query_df_sorted = query_df.sort_values(by=query_df.columns[0], ascending=True)
    
    # Remove self-matches (query sequence and its variations)
    labels_to_drop = [label for label in query_df_sorted.index 
                     if re.match(rf'{query_sequence}.*', label)]
    query_df_sorted_drop = query_df_sorted.drop(labels_to_drop, axis=0)
    
    # Get samples - either all or just top 20
    if all_samples:
        selected_samples = query_df_sorted_drop
        display_limit = min(20, len(selected_samples))  # Show only first 20 in console output
        print(f"\nProcessing all {len(selected_samples)} samples for {query_sequence}")
    else:
        selected_samples = query_df_sorted_drop[:20]
        display_limit = len(selected_samples)
        print(f"\nAnalysis for {query_sequence} (top 20 closest matches)")
    
    print("\nClosest matches with metadata:")
    print("--------------------------------------")
    
    # Store results for output
    results = []
    
    # Process all samples but only display first few in console
    for idx, (genome, distance) in enumerate(zip(selected_samples.index, selected_samples.iloc[:, 0]), 1):
        # Find matching metadata by filename
        metadata_match = metadata_df[metadata_df['filename'].str.contains(genome)]
        
        # Prepare result dictionary
        result = {
            'idx': idx,
            'genome': genome,
            'distance': distance
        }
        
        if not metadata_match.empty:
            # Extract requested metadata 
            for col in metadata_columns:
                if col in metadata_match.columns:
                    result[col] = metadata_match[col].iloc[0]
                else:
                    result[col] = "Unknown"
            
            # Display in console (limited to display_limit)
            if idx <= display_limit:
                # Format metadata for display
                metadata_str = ", ".join([f"{col}: {result[col]}" for col in metadata_columns if col in result])
                print(f"{idx}. {genome}: {distance:.4f} - {metadata_str}")
        else:
            # Display in console (limited to display_limit)
            if idx <= display_limit:
                print(f"{idx}. {genome}: {distance:.4f} - No metadata found")
        
        results.append(result)
    
    if all_samples and len(selected_samples) > display_limit:
        print(f"... and {len(selected_samples) - display_limit} more samples (see output file for complete list)")
    
    # Create DataFrame from results
    results_df = pd.DataFrame(results)
    
    # Save to file if output_file is specified
    if output_file:
        results_df.rename(columns={'distance': f'mash_distance_to_{query_sequence}'}, inplace=True)
        results_df.rename(columns={'idx': 'rank'}, inplace=True)
        results_df.to_csv(output_file, index=False)
        print(f"\nResults saved to {output_file}")
        
    return results_df

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze mash distances and annotate with metadata")
    parser.add_argument("-m", "--matrix", required=True, help="Mash distance matrix file")
    parser.add_argument("-d", "--metadata", required=True, help="Metadata CSV file")
    parser.add_argument("-q", "--query", required=True, help="Query sequence identifier")
    parser.add_argument("-c", "--columns", default="geoLocName,country", 
                        help="Comma-separated list of metadata columns to include")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("--all", action="store_true", 
                        help="Process distances to all samples, not just top 20")
    
    args = parser.parse_args()
    
    metadata_columns = args.columns.split(',')
    analyze_mash_distances(
        args.matrix, 
        args.metadata, 
        args.query, 
        metadata_columns=metadata_columns, 
        output_file=args.output,
        all_samples=args.all
    )