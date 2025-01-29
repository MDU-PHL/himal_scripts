#!/usr/bin/env python3

import pandas as pd
import numpy as np
from scipy.spatial.distance import squareform
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description='Convert a lower triangular matrix from a .txt file to a complete distance matrix.')
    parser.add_argument('input_file', type=str, help='Path to the input .txt file containing the lower triangular matrix.')
    parser.add_argument('--debug', action='store_true', help='Print debug information')
    return parser.parse_args()

def read_lower_triangular_matrix(file_path, debug=False):
    # Read all lines and clean them
    with open(file_path, 'r') as file:
        lines = [line.strip() for line in file.readlines() if line.strip()]
    
    if debug:
        print(f"Number of non-empty lines: {len(lines)}")
    
    # Extract sequence IDs
    seq_ids = []
    data = []
    
    n = len(lines)  # This will be the size of our matrix
    
    for i, line in enumerate(lines):
        # Split on any whitespace and filter empty strings
        parts = [x for x in line.split() if x]
        
        if debug and i < 5:  # Print first few lines for debugging
            print(f"Line {i}: {len(parts)} parts")
            print(f"Parts: {parts}")
        
        seq_ids.append(parts[0])
        row_values = []
        
        # For each row, we should only have i+1 values (including the ID)
        # So we only take the first i values after the ID
        for j in range(1, i+2):  # +2 because we want i+1 values and range is exclusive
            if j < len(parts):
                try:
                    row_values.append(float(parts[j]))
                except ValueError as e:
                    if debug:
                        print(f"Error converting value at line {i}, position {j}: {parts[j]}")
                    raise ValueError(f"Invalid number format at line {i+1}, position {j+1}: {parts[j]}")
        
        # Pad with NaN to match matrix size
        full_row = [np.nan] * i + row_values + [np.nan] * (n - i - len(row_values))
        
        if debug and i < 5:  # Print first few rows for debugging
            print(f"Row {i} length: {len(full_row)}")
            print(f"First few values: {full_row[:5]}")
        
        data.append(full_row)
    
    if debug:
        print(f"Number of sequence IDs: {len(seq_ids)}")
        print(f"Number of rows in data: {len(data)}")
        if data:
            print(f"Length of first row: {len(data[0])}")
    
    # Verify matrix dimensions
    if len(seq_ids) != len(data):
        raise ValueError(f"Matrix dimension mismatch. Expected {len(seq_ids)}x{len(seq_ids)} matrix, "
                        f"but got {len(data)} rows.")
    
    for i, row in enumerate(data):
        if len(row) != len(seq_ids):
            raise ValueError(f"Row {i} has length {len(row)}, expected {len(seq_ids)}.")
    
    # Create DataFrame
    df = pd.DataFrame(data, index=seq_ids, columns=seq_ids)
    
    # Extract lower triangular values
    lower_triangular_matrix = df.values[np.tril_indices(len(df), -1)]
    return df.index, lower_triangular_matrix

def main():
    args = parse_args()
    try:
        seq_ids, lower_triangular_matrix = read_lower_triangular_matrix(args.input_file, args.debug)
        distance_matrix = squareform(lower_triangular_matrix)
        complete_df = pd.DataFrame(distance_matrix, index=seq_ids, columns=seq_ids)
        
        print("\nComplete Distance Matrix:")
        print(complete_df)
    except Exception as e:
        print(f"Error processing matrix: {str(e)}")
        raise

if __name__ == "__main__":
    main()