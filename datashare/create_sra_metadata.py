#!/usr/bin/env python3
"""
Script to create SRA_metadata_acc.tab for NCBI upload

Usage:
    python create_sra_metadata.py \
        --search_csv path/to/search_ausmduid.csv \
        --biosample_txt path/to/BioSampleObjects.txt \
        --fastq_path path/to/fastq/reads \
        --title "Your bioproject title" \
        --instrument_csv path/to/instrument_ids.csv \
        --output path/to/SRA_metadata_acc.tab

Arguments:
    --search_csv, -s : Path to search_ausmduid.csv file
    --biosample_txt, -b : Path to BioSampleObjects.txt from NCBI
    --fastq_path, -f : Path to fastq reads directory
    --title, -t : Title from the BIOPROJECT
    --instrument_csv, -i : Path to instrument_ids.csv conversion file
    --output, -o : Output file path (default: SRA_metadata_acc.tab)
"""

import argparse
import csv
import glob
import os
import sys


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Create SRA_metadata_acc.tab for NCBI upload")
    parser.add_argument("--search_csv", "-s", required=True, help="Path to search_ausmduid.csv")
    parser.add_argument("--biosample_txt", "-b", required=True, help="Path to BioSampleObjects.txt")
    parser.add_argument("--fastq_path", "-f", required=True, help="Path to fastq reads directory, e.g., /home/himals/public_html/tmp/XMBOKXHDRNBH2K7BM3AEJIMQ6/")
    parser.add_argument("--title", "-t", required=True, help="Title from the BIOPROJECT, e.g., 'WGS of Escherichia/Shigella species'")
    parser.add_argument("--instrument_csv", "-i", required=True, help="Path to instrument_ids.csv")
    parser.add_argument("--output", "-o", default="SRA_metadata_acc.tab", help="Output file path (default: SRA_metadata_acc.tab)")
    return parser.parse_args()


def load_search_data(search_csv_path):
    """Load data from search_ausmduid.csv file."""
    search_data = {}
    try:
        with open(search_csv_path, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                ausmduid = row.get('ausmduid')
                if ausmduid:
                    search_data[ausmduid] = row
        return search_data
    except Exception as e:
        sys.exit(f"Error loading search_ausmduid.csv: {str(e)}")


def load_biosample_data(biosample_txt_path):
    """Load data from BioSampleObjects.txt file."""
    biosample_data = {}
    try:
        with open(biosample_txt_path, 'r') as file:
            reader = csv.DictReader(file, delimiter='\t')
            for row in reader:
                spuid = row.get('SPUID')
                if spuid:
                    biosample_data[spuid] = row
        return biosample_data
    except Exception as e:
        sys.exit(f"Error loading BioSampleObjects.txt: {str(e)}")


def load_instrument_data(instrument_csv_path):
    """Load instrument conversion data."""
    instrument_data = {}
    try:
        with open(instrument_csv_path, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                sequencer_id = row.get('SEQUENCER_ID')
                model = row.get('instrument_model')
                if sequencer_id and model:
                    instrument_data[sequencer_id] = model
        return instrument_data
    except Exception as e:
        sys.exit(f"Error loading instrument_ids.csv: {str(e)}")


def find_fastq_files(fastq_path, ausmduid):
    """Find R1 and R2 fastq files for a given ausmduid."""
    r1_pattern = os.path.join(fastq_path, f"{ausmduid}*R1*")
    r2_pattern = os.path.join(fastq_path, f"{ausmduid}*R2*")
    
    r1_files = glob.glob(r1_pattern)
    r2_files = glob.glob(r2_pattern)
    
    r1_file = r1_files[0] if r1_files else "not found"
    r2_file = r2_files[0] if r2_files else "not found"
    
    # Extract just the filenames, not the full paths
    if r1_file != "not found":
        r1_file = os.path.basename(r1_file)
    if r2_file != "not found":
        r2_file = os.path.basename(r2_file)
    
    return r1_file, r2_file


def create_sra_metadata(args):
    """Create SRA metadata file."""
    search_data = load_search_data(args.search_csv)
    biosample_data = load_biosample_data(args.biosample_txt)
    instrument_data = load_instrument_data(args.instrument_csv)
    
    # Define metadata headers
    headers = [
        "biosample_accession", "library_ID", "title", "library_strategy",
        "library_source", "library_selection", "library_layout", "platform",
        "instrument_model", "design_description", "filetype", "filename", "filename2"
    ]
    
    try:
        with open(args.output, 'w', newline='') as out_file:
            writer = csv.writer(out_file, delimiter='\t')
            writer.writerow(headers)
            
            # Process each biosample
            for ausmduid, biosample in biosample_data.items():
                if ausmduid not in search_data:
                    print(f"Warning: {ausmduid} found in BioSampleObjects.txt but not in search_ausmduid.csv")
                    continue
                
                search_record = search_data[ausmduid]
                
                # Get biosample accession
                accession = biosample.get('Accession', '')
                
                # Get instrument model
                sequencer_id = search_record.get('SEQUENCER_ID', '')
                instrument_model = instrument_data.get(sequencer_id, 'not available')
                
                # Find fastq files
                r1_file, r2_file = find_fastq_files(args.fastq_path, ausmduid)
                
                # Create metadata row
                row = [
                    accession,                  # biosample_accession
                    ausmduid,                   # library_ID
                    args.title,                 # title
                    "WGS",                      # library_strategy
                    "GENOMIC",                  # library_source
                    "RANDOM",                   # library_selection
                    "PAIRED",                   # library_layout
                    "ILLUMINA",                 # platform
                    instrument_model,           # instrument_model
                    "150bp PE Nextera library", # design_description
                    "fastq",                    # filetype
                    r1_file,                    # filename
                    r2_file                     # filename2
                ]
                
                writer.writerow(row)
        
        print(f"SRA metadata successfully created: {args.output}")
    
    except Exception as e:
        sys.exit(f"Error creating SRA metadata file: {str(e)}")


def main():
    """Main function."""
    args = parse_args()
    create_sra_metadata(args)


if __name__ == "__main__":
    main()