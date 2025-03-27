#!/usr/bin/env python3

import argparse
import os
import re
import pandas as pd
import sys
from pathlib import Path

def map_contigs_to_amrfinder(contig_path, sample_id):
    """
    Maps a contigs file path to its corresponding amrfinder.out path using sample_id as anchor.
    From: /home/xxx/xxxx/xxxx/<sample-id>/*/*.fa 
    To:   /home/xxx/xxxx/xxxx/<sample-id>/abritamr/current/amrfinder.out
    
    Args:
        contig_path (str): Path to contig file
        sample_id (str): Sample ID to use as anchor in the path
    
    Returns:
        str or None: Path to amrfinder.out file or None if sample_id not in path
    """
    # Check if sample_id is in the path
    if sample_id in contig_path:
        # Split path at sample_id
        parts = contig_path.split(sample_id)
        # Take everything up to and including sample_id
        base_dir = parts[0] + sample_id
        # Join with AMRFinder standard path
        amrfinder_path = os.path.join(base_dir, "abritamr", "current", "amrfinder.out")
        return amrfinder_path
    else:
        # If sample_id is not in path, try alternative approach - assume it's the directory name
        parts = contig_path.split('/')
        for i, part in enumerate(parts):
            if part == sample_id:
                # Found sample_id as directory name
                base_dir = '/'.join(parts[:i+1])
                amrfinder_path = os.path.join(base_dir, "abritamr", "current", "amrfinder.out")
                return amrfinder_path
        
        print(f"Warning: Could not locate '{sample_id}' in path: {contig_path}")
        return None

def search_gene_in_amrfinder(amrfinder_path, gene_name):
    """
    Searches for a gene pattern in an AMRFinder output file.
    Returns matching lines or None if no match or file not found.
    """
    if not os.path.isfile(amrfinder_path):
        return None
    
    matches = []
    try:
        with open(amrfinder_path, 'r') as f:
            # Skip header line
            next(f, None)
            for line in f:
                if re.search(gene_name, line, re.IGNORECASE):
                    matches.append(line.strip())
    except Exception as e:
        print(f"Error reading {amrfinder_path}: {e}")
        return None
    
    return matches if matches else None

def get_amrfinder_header(amrfinder_paths):
    """
    Get the header from the first available AMRFinder output file.
    """
    for path in amrfinder_paths:
        if os.path.isfile(path):
            try:
                with open(path, 'r') as f:
                    return f.readline().strip()
            except Exception:
                continue
    
    # Default header if no files are available
    return "Protein identifier\tContig id\tStart\tStop\tStrand\tGene symbol\tSequence name\tScope\tElement type\tElement subtype\tClass\tSubclass\tMethod\tTarget length\tReference sequence length\t% Coverage of reference sequence\t% Identity to reference sequence\tAlignment length\tAccession of closest sequence\tName of closest sequence\tHMM id\tHMM description"

def main():
    parser = argparse.ArgumentParser(
        description='Collate AMRFinder results for a specific gene across multiple samples',
        epilog='''
Examples:
  python collate_amrfinder.py -c contigs.tab -g NDM -o results/
  python collate_amrfinder.py --contigs-file samples.tab --gene-name KPC --output-dir ./output
  
Note:
  This script expects a contigs.tab file without header, with sample_id in the first column
  and path to contig file in the second column. It will convert contig paths to AMRFinder
  output paths and search for the specified gene pattern in each file.
  
  The script produces two outputs:
  1. amrfinder.tab - Mapping between sample_id and AMRFinder output file path
  2. amrfinder.out.collated - Collated results of gene matches across all samples
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('-c', '--contigs-file', required=True, 
                      help='Path to contigs.tab file with sample_id and contig paths')
    parser.add_argument('-g', '--gene-name', required=True,
                      help='Gene name pattern to search for (case insensitive)')
    parser.add_argument('-o', '--output-dir', default='.',
                      help='Output directory for result files (default: current directory)')
    
    args = parser.parse_args()
    
    # Check if input file exists
    if not os.path.isfile(args.contigs_file):
        sys.exit(f"Error: Contigs file '{args.contigs_file}' does not exist.")
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Define output files
    amrfinder_tab = os.path.join(args.output_dir, "amrfinder.tab")
    amrfinder_collated = os.path.join(args.output_dir, "amrfinder.out.collated")
    
    try:
        # Read contigs.tab file
        contigs_data = []
        with open(args.contigs_file, 'r') as f:
            for line in f:
                fields = line.strip().split('\t')
                if len(fields) >= 2:
                    contigs_data.append((fields[0], fields[1]))
        
        if not contigs_data:
            sys.exit(f"Error: No valid data found in '{args.contigs_file}'")
        
        # Map contigs to AMRFinder paths and save to amrfinder.tab
        amrfinder_paths = []
        with open(amrfinder_tab, 'w') as f:
            for sample_id, contig_path in contigs_data:
                amrfinder_path = map_contigs_to_amrfinder(contig_path, sample_id)
                if amrfinder_path:
                    f.write(f"{sample_id}\t{amrfinder_path}\n")
                    amrfinder_paths.append((sample_id, amrfinder_path))
                else:
                    print(f"Warning: Could not map {contig_path} to AMRFinder path for sample {sample_id}")
        
        print(f"Created {amrfinder_tab} with {len(amrfinder_paths)} entries")
        
        # Get header from the first available AMRFinder file
        header = get_amrfinder_header([p[1] for p in amrfinder_paths])
        
        # Create collated output file with results for the gene
        with open(amrfinder_collated, 'w') as f:
            # Write header with sample_id as first column
            f.write(f"sample_id\t{header}\n")
            
            # Process each sample
            samples_with_match = 0
            samples_without_match = 0
            
            for sample_id, amrfinder_path in amrfinder_paths:
                matches = search_gene_in_amrfinder(amrfinder_path, args.gene_name)
                
                if matches:
                    # Write all matching lines
                    for match in matches:
                        f.write(f"{sample_id}\t{match}\n")
                    samples_with_match += 1
                    print(f"Found {len(matches)} matches for gene '{args.gene_name}' in sample {sample_id}")
                else:
                    # Write NA line
                    tab_count = header.count('\t')
                    na_fields = ['NA'] * tab_count
                    na_line = '\t'.join(na_fields)
                    f.write(f"{sample_id}\t{na_line}\n")
                    samples_without_match += 1
                    print(f"No matches for gene '{args.gene_name}' in sample {sample_id}")
        
        print(f"\nSummary:")
        print(f"- Total samples processed: {len(amrfinder_paths)}")
        print(f"- Samples with matches: {samples_with_match}")
        print(f"- Samples without matches: {samples_without_match}")
        print(f"- Results saved to {amrfinder_collated}")
        
    except Exception as e:
        sys.exit(f"Error: {str(e)}")

if __name__ == "__main__":
    main()