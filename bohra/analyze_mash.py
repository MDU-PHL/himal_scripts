import pandas as pd
import re
import argparse

def analyze_mash_distances(matrix_file, metadata_file, query_sequence, metadata_columns=None, output_file=None):
    """
    Analyze mash distances for a given query sequence and annotate with metadata
    
    Parameters:
    matrix_file (str): Path to the mash distance matrix file
    metadata_file (str): Path to the metadata CSV file
    query_sequence (str): Query sequence identifier
    metadata_columns (list): List of metadata columns to include [default: geoLocName, country]
    output_file (str): Optional output file path for annotations
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
    
    # Get top 20 closest matches
    top_20 = query_df_sorted_drop[:20]
    
    print(f"\nAnalysis for {query_sequence}:")
    print("\nTop 20 closest matches with metadata:")
    print("--------------------------------------")
    
    # Store results for output
    results = []
    
    for idx, (genome, distance) in enumerate(zip(top_20.index, top_20.iloc[:, 0]), 1):
        # Find matching metadata by filename
        metadata_match = metadata_df[metadata_df['filename'].str.contains(genome)]
        
        if not metadata_match.empty:
            # Extract requested metadata 
            metadata_info = {}
            for col in metadata_columns:
                if col in metadata_match.columns:
                    metadata_info[col] = metadata_match[col].iloc[0]
                else:
                    metadata_info[col] = "Unknown"
            
            # Format metadata for display
            metadata_str = ", ".join([f"{col}: {metadata_info[col]}" for col in metadata_columns])
            print(f"{idx}. {genome}: {distance:.4f} - {metadata_str}")
            
            results.append({
                'idx': idx,
                'genome': genome,
                'distance': distance,
                **metadata_info
            })
        else:
            print(f"{idx}. {genome}: {distance:.4f} - No metadata found")
            results.append({
                'idx': idx,
                'genome': genome,
                'distance': distance
            })
    
    # Create DataFrame from results
    results_df = pd.DataFrame(results)
    
    # Save to file if output_file is specified
    if output_file:
        results_df.to_csv(output_file, index=False)
        print(f"\nResults saved to {output_file}")
    
    # Create annotation file for tree visualization
    if output_file:
        tree_annotation_file = output_file.replace('.csv', '_tree_annotation.csv')
        
        # Create tree annotation dataframe 
        tree_df = pd.DataFrame()
        tree_df['filename'] = results_df['genome']
        
        # Add requested metadata columns
        for col in metadata_columns:
            if col in results_df.columns:
                tree_df[col] = results_df[col]
        
        # Save tree annotation file
        tree_df.to_csv(tree_annotation_file, index=False)
        print(f"Tree annotation file created: {tree_annotation_file}")
        print(f"Use this file with ggtree_annotate.R using --match-column filename")
    
    return results_df

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze mash distances and annotate with metadata")
    parser.add_argument("-m", "--matrix", required=True, help="Mash distance matrix file")
    parser.add_argument("-d", "--metadata", required=True, help="Metadata CSV file")
    parser.add_argument("-q", "--query", required=True, help="Query sequence identifier")
    parser.add_argument("-c", "--columns", default="geoLocName,country", 
                        help="Comma-separated list of metadata columns to include")
    parser.add_argument("-o", "--output", help="Output file path")
    
    args = parser.parse_args()
    
    metadata_columns = args.columns.split(',')
    analyze_mash_distances(args.matrix, args.metadata, args.query, 
                         metadata_columns=metadata_columns, output_file=args.output)
