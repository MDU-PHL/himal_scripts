import argparse
import csv
import glob
import logging
import os
import sys
from datetime import datetime
from pathlib import Path


def setup_logging():
    """Setup logging with custom format [YYYY-MM-DD HH:MM:SS] - LEVEL: message"""
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] - %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)


def find_shigapass_files(results_dir):
    """
    Find all ShigaPass_summary.csv files in results/*/ShigaPass_summary.csv pattern
    
    Args:
        results_dir (str): Path to results directory
        
    Returns:
        list: List of paths to ShigaPass_summary.csv files
    """
    logger = logging.getLogger(__name__)
    
    pattern = os.path.join(results_dir, "*", "ShigaPass_summary.csv")
    files = glob.glob(pattern)
    
    logger.info(f"Found {len(files)} ShigaPass_summary.csv files")
    for file in files:
        logger.debug(f"Found file: {file}")
    
    return files


def parse_shigapass_file(file_path):
    """
    Parse a single ShigaPass_summary.csv file
    
    Args:
        file_path (str): Path to the ShigaPass_summary.csv file
        
    Returns:
        list: List of dictionaries containing parsed data
    """
    logger = logging.getLogger(__name__)
    
    try:
        with open(file_path, 'r') as f:
            # Use semicolon as delimiter
            reader = csv.DictReader(f, delimiter=';')
            data = list(reader)
            
        logger.info(f"Parsed {len(data)} records from {file_path}")
        return data
        
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return []
    except Exception as e:
        logger.error(f"Error parsing file {file_path}: {str(e)}")
        return []


def concatenate_results(shigapass_files):
    """
    Concatenate all ShigaPass results into a single dataset
    
    Args:
        shigapass_files (list): List of paths to ShigaPass_summary.csv files
        
    Returns:
        list: Combined list of all records
    """
    logger = logging.getLogger(__name__)
    
    all_data = []
    
    for file_path in shigapass_files:
        logger.info(f"Processing file: {file_path}")
        data = parse_shigapass_file(file_path)
        all_data.extend(data)
    
    logger.info(f"Total records concatenated: {len(all_data)}")
    return all_data


def write_output_file(data, output_file):
    """
    Write concatenated data to tab-delimited output file
    
    Args:
        data (list): List of dictionaries containing all records
        output_file (str): Path to output file
    """
    logger = logging.getLogger(__name__)
    
    if not data:
        logger.warning("No data to write")
        return
    
    try:
        # Get fieldnames from the first record
        fieldnames = list(data[0].keys())
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
            writer.writeheader()
            writer.writerows(data)
        
        logger.info(f"Successfully wrote {len(data)} records to {output_file}")
        
    except Exception as e:
        logger.error(f"Error writing output file {output_file}: {str(e)}")
        sys.exit(1)


def main():
    """Main function to orchestrate the parsing and concatenation"""
    parser = argparse.ArgumentParser(
        description='Parse ShigaPASS results and concatenate into a single tab-delimited file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s -r /path/to/results
  %(prog)s --results-dir /path/to/results --output custom_output.tab
  %(prog)s -r ./results -o combined_shigapass.tab

Input Format:
  ShigaPASS files should be semicolon-delimited CSV files with headers:
  Name;rfb;rfb_hits,(%%);MLST;fliC;CRISPR;ipaH;Predicted_Serotype;Predicted_FlexSerotype;Comments

Output Format:
  Tab-delimited file with all records from input files concatenated
        '''
    )
    
    parser.add_argument(
        '-r', '--results-dir',
        required=True,
        help='Path to results directory containing */ShigaPass_summary.csv files'
    )
    
    parser.add_argument(
        '-o', '--output',
        default='shigaPASS_summary.tab',
        help='Output file name (default: shigaPASS_summary.tab). Will be created in the results directory'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging (debug level)'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Validate results directory
    if not os.path.isdir(args.results_dir):
        logger.error(f"Results directory does not exist: {args.results_dir}")
        sys.exit(1)
    
    # Set output file path (in results directory if not absolute path)
    if not os.path.isabs(args.output):
        output_file = os.path.join(args.results_dir, args.output)
    else:
        output_file = args.output
    
    logger.info(f"Starting ShigaPASS results parsing")
    logger.info(f"Results directory: {args.results_dir}")
    logger.info(f"Output file: {output_file}")
    
    # Find all ShigaPass files
    shigapass_files = find_shigapass_files(args.results_dir)
    
    if not shigapass_files:
        logger.warning("No ShigaPass_summary.csv files found")
        sys.exit(1)
    
    # Parse and concatenate results
    all_data = concatenate_results(shigapass_files)
    
    if not all_data:
        logger.warning("No data found in any files")
        sys.exit(1)
    
    # Write output file
    write_output_file(all_data, output_file)
    
    logger.info("ShigaPASS parsing completed successfully")


if __name__ == '__main__':
    main()