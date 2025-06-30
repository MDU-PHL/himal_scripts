#!/usr/bin/env python3

import argparse
import os
import glob

def find_reads(reads_dir, run_id, sample_id):
    """Find read files for a given sample ID"""
    if run_id:
        # Search in specific run directory
        base_path = os.path.join(reads_dir, run_id, sample_id)
        # base_path = os.path.join(reads_dir, run_id) #, sample_id) # for cases where sample_id is not a directory
    else:
        # Search in all run directories
        base_path = os.path.join(reads_dir, "*", sample_id)
    
    # Handle both standard Illumina naming and trim naming patterns
    r1_patterns = [f"{sample_id}*_R1_001.fastq.gz", f"{sample_id}*_1.trim.fastq.gz"]
    r2_patterns = [f"{sample_id}*_R2_001.fastq.gz", f"{sample_id}*_2.trim.fastq.gz"]
    
    r1_files = []
    r2_files = []
    
    for pattern in r1_patterns:
        r1_files.extend(glob.glob(os.path.join(base_path, pattern)))
    for pattern in r2_patterns:
        r2_files.extend(glob.glob(os.path.join(base_path, pattern)))
    
    if r1_files and r2_files:
        return r1_files[0], r2_files[0]
    return None, None

def main():
    parser = argparse.ArgumentParser(description='Create reads.tab file from sample IDs')
    parser.add_argument('-i', '--ids', required=True, help='File containing sample IDs')
    parser.add_argument('-d', '--dir', help='Base directory containing reads (default: /home/mdu/reads)', default='/home/mdu/reads')
    parser.add_argument('-r', '--run', help='Specific run ID to search in (optional)')
    parser.add_argument('-o', '--output', default='reads.tab', help='Output filename (default: reads.tab)')
    
    args = parser.parse_args()
    
    # Read sample IDs
    with open(args.ids) as f:
        sample_ids = [line.strip() for line in f if line.strip()]
    
    # Create output file
    with open(args.output, 'w') as out:
        for sample_id in sample_ids:
            r1, r2 = find_reads(args.dir, args.run, sample_id)
            if r1 and r2:
                out.write(f"{sample_id}\t{r1}\t{r2}\n")
            else:
                print(f"Warning: Could not find reads for sample {sample_id}")

if __name__ == '__main__':
    main()