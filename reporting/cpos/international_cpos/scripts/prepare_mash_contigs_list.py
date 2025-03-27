#!/usr/bin/env python3

import pandas as pd
import glob
import os
import argparse

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Create a contigs list file for mashtree analysis')
    parser.add_argument('-i', '--input', required=True, 
                        help='Input TSV file with MLST results (e.g., ST_X_mlst_results.tsv)')
    parser.add_argument('-c', '--column', default='sample',
                        help='Column name containing sample identifiers. Default: "sample"')
    parser.add_argument('-o', '--output', required=True, 
                        help='Output file name for contigs list')
    parser.add_argument('-p', '--path', required=True, 
                        help='Path to directory containing genome assemblies. For ncbi datasets, this is usually till the "genome_directory/ncbi_dataset/data/" directory')
    parser.add_argument('--pattern', default="*/{sample}*", 
                        help='Pattern for finding contig files. Use {sample} as a placeholder. Default: "*/{sample}*"')
    
    args = parser.parse_args()
    
    # Read the MLST results
    mlst_df = pd.read_csv(args.input, sep='\t')
    
    # Extract sample values
    samples = mlst_df[args.column].tolist()
    
    # Prepare contigs list
    contig_paths = []
    for sample in samples:
        # Find matching contig file using the provided pattern
        pattern_with_sample = args.pattern.format(sample=sample)
        full_pattern = os.path.join(args.path, pattern_with_sample)
        matching_files = glob.glob(full_pattern)
        if matching_files:
            contig_paths.extend(matching_files)
        else:
            print(f"Warning: No matching files found for sample {sample} with pattern {full_pattern}")
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Write contig paths to output file
    with open(args.output, 'w') as f:
        for path in contig_paths:
            f.write(f"{path}\n")
    
    print(f"Found {len(samples)} samples")
    print(f"Found {len(contig_paths)} contig files")
    print(f"Contig list saved to {args.output}")

if __name__ == "__main__":
    main()