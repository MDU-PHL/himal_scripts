#!/usr/bin/env python3
"""
Script to create SRA metadata for Oxford Nanopore Technology (ONT) data.

This script generates an SRA metadata file for NCBI submissions from ONT sequencing data.
It uses BioSample information and matches it with ONT fastq files.
"""

import argparse
import csv
import glob
import logging
import os
import sys
from datetime import datetime


def setup_logging():
    """Configure logging with custom format."""
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(message)s',
        datefmt='%Y-%m-%d [%H:%M:%S] LOG:'
    )
    return logging.getLogger()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Create SRA metadata for ONT data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  python create_ont_sra_metadata.py \\
    -b ont_BioSampleObjects.txt \\
    -f /path/to/fastq/files \\
    -t "WGS of Mycobacterium tuberculosis from ONT reads" \\
    -o ont_sra_metadata.tab \\
    -d "Rapid Barcoding Kit (SQK-RBK004), Flow cell: R9.4.1"

The script will:
1. Read biosample accessions from BioSampleObjects.txt
2. Find matching ONT fastq files
3. Create an SRA metadata file with required columns
        """
    )
    
    parser.add_argument("-b", "--biosample", required=True,
                        help="Path to BioSampleObjects.txt file")
    
    parser.add_argument("-f", "--fastq_dir", required=True,
                        help="Directory containing ONT fastq files")
    
    parser.add_argument("-t", "--title", required=True,
                        help="Title for the SRA submission")
    
    parser.add_argument("-o", "--output", default="ont_sra_metadata.tab",
                        help="Output file name (default: ont_sra_metadata.tab)")
    
    parser.add_argument("-p", "--platform", default="OXFORD_NANOPORE",
                        help="Sequencing platform (default: OXFORD_NANOPORE)")
    
    parser.add_argument("-i", "--instrument", default="GridION",
                        help="Instrument model (default: GridION)")
    
    parser.add_argument("-d", "--design", default="ONT sequencing",
                        help="Design description (default: ONT sequencing)")
    
    return parser.parse_args()


def load_biosample_data(biosample_file, logger):
    """
    Load data from BioSampleObjects.txt file.
    
    Args:
        biosample_file: Path to BioSampleObjects.txt
        logger: Logger object for output
        
    Returns:
        Dictionary mapping ausmduid_ont to biosample accession
    """
    mappings = {}
    try:
        with open(biosample_file, 'r') as file:
            reader = csv.DictReader(file, delimiter='\t')
            for row in reader:
                # Extract the ausmduid_ont and accession
                ausmduid_ont = row.get('ausmduid_ont')
                accession = row.get('Accession')
                if ausmduid_ont and accession:
                    mappings[ausmduid_ont] = accession
    except Exception as e:
        logger.error(f"Error loading biosample file: {str(e)}")
        sys.exit(1)
        
    logger.info(f"Loaded {len(mappings)} ID mappings from {os.path.basename(biosample_file)}")
    return mappings


def find_matching_fastq_files(fastq_dir, ausmduid_ont, logger):
    """
    Find fastq.gz files matching the ausmduid_ont pattern.
    
    Args:
        fastq_dir: Directory containing fastq files
        ausmduid_ont: Sample ID to match
        logger: Logger object for output
        
    Returns:
        List of matching fastq filenames
    """
    # Define pattern for matching files
    pattern = os.path.join(fastq_dir, f"{ausmduid_ont}*.fastq.gz")
    matching_files = glob.glob(pattern)
    
    if not matching_files:
        logger.warning(f"No fastq files found for {ausmduid_ont}")
        return []
        
    # Return just the filenames, not the full paths
    return [os.path.basename(f) for f in matching_files]


def create_sra_metadata(args, logger):
    """
    Create SRA metadata file for ONT data.
    
    Args:
        args: Command line arguments
        logger: Logger object for output
        
    Returns:
        None
    """
    # Load biosample data
    biosample_mappings = load_biosample_data(args.biosample, logger)
    
    # Define metadata headers
    headers = [
        "biosample_accession", "library_ID", "title", "library_strategy", 
        "library_source", "library_selection", "library_layout", "platform",
        "instrument_model", "design_description", "filetype", "filename"
    ]
    
    # Create output file
    try:
        with open(args.output, 'w', newline='') as out_file:
            writer = csv.writer(out_file, delimiter='\t')
            writer.writerow(headers)
            
            # Process each biosample
            for ausmduid_ont, accession in biosample_mappings.items():
                # Find matching fastq files
                fastq_files = find_matching_fastq_files(args.fastq_dir, ausmduid_ont, logger)
                
                # Skip if no files found
                if not fastq_files:
                    continue
                
                # Log each file being processed
                for filename in fastq_files:
                    logger.info(f"Processing {filename} for {ausmduid_ont}")
                    
                    # Create metadata row
                    row = [
                        accession,              # biosample_accession
                        ausmduid_ont,           # library_ID
                        args.title,             # title
                        "WGS",                  # library_strategy
                        "GENOMIC",              # library_source
                        "RANDOM",               # library_selection
                        "single",               # library_layout
                        args.platform,          # platform
                        args.instrument,        # instrument_model
                        args.design,            # design_description
                        "fastq",                # filetype
                        filename                # filename
                    ]
                    
                    writer.writerow(row)
                    
        logger.info(f"SRA metadata successfully written to {args.output}")
        
    except Exception as e:
        logger.error(f"Error creating SRA metadata file: {str(e)}")
        sys.exit(1)


def main():
    """Main function."""
    # Set up logging
    logger = setup_logging()
    
    # Parse command line arguments
    args = parse_arguments()
    
    # Create SRA metadata
    create_sra_metadata(args, logger)


if __name__ == "__main__":
    main()