#!/usr/bin/env python3
# filepath: filter_mlst_by_st.py
import pandas as pd
import argparse
import os

def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(description='Filter MLST results for a specific sequence type (ST)')
    parser.add_argument('-i', '--input', required=True, 
                        help='Path to combined MLST results TSV file')
    parser.add_argument('-s', '--st', required=True, type=int, 
                        help='Sequence type (ST) to filter for')
    
    args = parser.parse_args()
    
    # Read the combined MLST results
    print(f"Reading MLST results from {args.input}")
    mlst_df = pd.read_csv(args.input, sep='\t')
    
    # Check data type of ST column
    print("Data type of ST column:", mlst_df['ST'].dtype)
    print("\nUnique ST values:", mlst_df['ST'].unique())
    
    # Convert ST column to numeric, handling any non-numeric values
    mlst_df['ST'] = pd.to_numeric(mlst_df['ST'], errors='coerce')
    
    # Filter for specified ST
    st_df = mlst_df[mlst_df['ST'] == args.st]
    
    # Generate output path (same directory as input)
    input_dir = os.path.dirname(args.input)
    output_path = os.path.join(input_dir, f'ST_{args.st}_mlst_results.tsv')
    
    # Export filtered results to new TSV file
    st_df.to_csv(output_path, sep='\t', index=False)
    
    # Print summary
    print(f"\nFound {len(st_df)} samples with ST {args.st}")
    print(f"Results saved to {output_path}")

if __name__ == "__main__":
    main()