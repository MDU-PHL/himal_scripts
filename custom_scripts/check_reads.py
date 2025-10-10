#!/usr/bin/env python3
"""
File Size Analyser Script

This script analyses file sizes in a directory, generates summary statistics,
saves results to CSV, and creates a histogram visualization.

Author: Himal Shrestha
Date: 2025-10-10
"""

import os
import glob
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import argparse
import logging
from datetime import datetime
import sys

# Suppress matplotlib font debug messages
logging.getLogger('matplotlib.font_manager').setLevel(logging.WARNING)


def setup_logging():
    """Set up logging configuration with timestamp format."""
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)


def get_file_sizes(directory, logger):
    """
    Get file sizes from a directory pattern.
    
    Args:
        directory (str): Directory pattern to search
        logger: Logger instance
        
    Returns:
        dict: Dictionary mapping filenames to sizes in bytes
    """
    logger.info(f"Scanning directory pattern: {directory}")
    file_sizes = {}
    
    for file_path in glob.glob(directory):
        if os.path.isfile(file_path):
            try:
                file_size = os.path.getsize(file_path)
                file_sizes[os.path.basename(file_path)] = file_size
                logger.debug(f"Found file: {os.path.basename(file_path)} ({file_size} bytes)")
            except OSError as e:
                logger.warning(f"Could not get size for {file_path}: {e}")
    
    logger.info(f"Found {len(file_sizes)} files")
    return file_sizes

def summarize_file_sizes(file_sizes, logger):
    """
    Calculate summary statistics for file sizes.
    
    Args:
        file_sizes (dict): Dictionary of filename to size mappings
        logger: Logger instance
        
    Returns:
        dict: Summary statistics
    """
    logger.info("Calculating summary statistics")
    sizes = list(file_sizes.values())
    
    if not sizes:
        logger.warning("No files found - all statistics will be zero")
        return {
            'total_size': 0,
            'num_files': 0,
            'avg_size': 0,
            'max_size': 0,
            'min_size': 0,
            'median_size': 0
        }
    
    total_size = sum(sizes)
    num_files = len(sizes)
    avg_size = total_size / num_files
    max_size = max(sizes)
    min_size = min(sizes)
    median_size = np.median(sizes)
    
    logger.info(f"Statistics calculated for {num_files} files")
    
    return {
        'total_size': total_size,
        'num_files': num_files,
        'avg_size': avg_size,
        'max_size': max_size,
        'min_size': min_size,
        'median_size': median_size
    }

def human_readable_size(size, decimal_places=2):
    """
    Convert bytes to human readable format.
    
    Args:
        size (int): Size in bytes
        decimal_places (int): Number of decimal places
        
    Returns:
        str: Human readable size string
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.{decimal_places}f} {unit}"
        size /= 1024.0
    return f"{size:.{decimal_places}f} PB"


def save_file_sizes_to_csv(file_sizes, output_csv, logger):
    """
    Save file sizes to CSV file.
    
    Args:
        file_sizes (dict): Dictionary of filename to size mappings
        output_csv (str): Output CSV file path
        logger: Logger instance
    """
    logger.info(f"Saving file sizes to CSV: {output_csv}")
    
    if not file_sizes:
        logger.warning("No file sizes to save")
        # Create empty CSV with headers
        df = pd.DataFrame(columns=['File', 'Size (bytes)', 'Size (human readable)'])
    else:
        df = pd.DataFrame(list(file_sizes.items()), columns=['File', 'Size (bytes)'])
        df['Size (human readable)'] = df['Size (bytes)'].apply(human_readable_size)
        df = df.sort_values('Size (bytes)', ascending=False)  # Sort by size descending
    
    try:
        df.to_csv(output_csv, index=False)
        logger.info(f"Successfully saved {len(df)} records to {output_csv}")
    except Exception as e:
        logger.error(f"Failed to save CSV file: {e}")
        raise

def plot_file_sizes_histogram(file_sizes, run_id, output_plot, logger):
    """
    Create and save simple histogram of file sizes.
    
    Args:
        file_sizes (dict): Dictionary of filename to size mappings
        run_id (str): Run identifier for the plot title
        output_plot (str): Output plot file path
        logger: Logger instance
    """
    logger.info(f"Creating histogram plot: {output_plot}")
    
    sizes = list(file_sizes.values())
    
    if not sizes:
        logger.warning("No file sizes to plot")
        return
    
    # Create simple histogram
    plt.figure(figsize=(10, 6))
    plt.hist(sizes, bins=20, color='skyblue', edgecolor='black')
    plt.xlabel('File Size (bytes)')
    plt.ylabel('Number of Files')
    plt.title(f'File Size Distribution - {run_id}')
    plt.grid(True, alpha=0.3)
    
    try:
        plt.savefig(output_plot, dpi=150, bbox_inches='tight')
        logger.info(f"Successfully saved plot to {output_plot}")
    except Exception as e:
        logger.error(f"Failed to save plot: {e}")
        raise
    finally:
        plt.close()


def print_summary(summary, logger):
    """
    Print summary statistics to console.
    
    Args:
        summary (dict): Summary statistics dictionary
        logger: Logger instance
    """
    logger.info("Printing summary statistics")
    
    print("\n" + "="*50)
    print("SUMMARY OF FILE SIZES")
    print("="*50)
    print(f"Total size:    {human_readable_size(summary['total_size'])} ({summary['total_size']:,} bytes)")
    print(f"Number of files: {summary['num_files']:,}")
    
    if summary['num_files'] > 0:
        print(f"Average size:  {human_readable_size(summary['avg_size'])} ({summary['avg_size']:.0f} bytes)")
        print(f"Median size:   {human_readable_size(summary['median_size'])} ({summary['median_size']:.0f} bytes)")
        print(f"Largest file:  {human_readable_size(summary['max_size'])} ({summary['max_size']:,} bytes)")
        print(f"Smallest file: {human_readable_size(summary['min_size'])} ({summary['min_size']:,} bytes)")
    print("="*50)


def validate_arguments(args, logger):
    """
    Validate command line arguments.
    
    Args:
        args: Parsed arguments object
        logger: Logger instance
        
    Returns:
        bool: True if arguments are valid
    """
    logger.info("Validating command line arguments")
    
    # Check if output directory exists, create if it doesn't
    if not os.path.exists(args.output_dir):
        logger.info(f"Creating output directory: {args.output_dir}")
        try:
            os.makedirs(args.output_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create output directory {args.output_dir}: {e}")
            return False
    
    # Check if output directory is writable
    if not os.access(args.output_dir, os.W_OK):
        logger.error(f"Output directory is not writable: {args.output_dir}")
        return False
    
    logger.info("Arguments validated successfully")
    return True


def main():
    """Main function to run the file size analyser."""
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description='Analyse file sizes in a directory and generate summary statistics',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyse files for run M2025-12345 with default settings
  python check_reads.py M2025-12345
  
  # Analyse with custom directory pattern
  python check_reads.py M2025-12345 --directory "/path/to/files/*"
  
  # Specify custom output files and directory
  python check_reads.py M2025-12345 \\
    --output-csv "my_summary.csv" \\
    --output-plot "my_histogram.png" \\
    --output-dir "./results"
  
  # Analyse with custom directory pattern (no run_id substitution)
  python check_reads.py custom_run \\
    --directory "/specific/path/to/files/*" \\
    --output-dir "./results"

File Pattern Matching:
  The directory argument supports glob patterns:
  - "*" matches any characters
  - "?" matches single character  
  - "**" matches directories recursively
  - Use quotes to prevent shell expansion

Output Files:
  - CSV contains: filename, size in bytes, human-readable size
  - PNG contains: histogram with statistics overlay
  - Both files are sorted/organised for easy analysis
        """
    )
    
    # Required arguments
    parser.add_argument(
        'run_id',
        help='Run identifier (used in default paths and plot title)'
    )
    
    # Optional arguments
    parser.add_argument(
        '--directory', '-d',
        default=None,
        help='Directory pattern to search for files (default: /home/mdu/reads/{run_id}/*/).'
             ' Supports glob patterns like *, ?, **'
    )
    
    parser.add_argument(
        '--output-csv', '-c',
        default=None,
        help='Output CSV file path (default: file_sizes_summary_{run_id}.csv)'
    )
    
    parser.add_argument(
        '--output-plot', '-p',
        default=None,
        help='Output plot file path (default: file_sizes_histogram_{run_id}.png)'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        default='.',
        help='Output directory for generated files (default: current working directory)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging (debug level)'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set up logging
    logger = setup_logging()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("="*60)
    logger.info("FILE SIZE ANALYSER STARTED")
    logger.info("="*60)
    logger.info(f"Run ID: {args.run_id}")
    
    # Set defaults based on run_id
    if args.directory is None:
        args.directory = f'/home/mdu/reads/{args.run_id}/*/*'
    
    if args.output_csv is None:
        args.output_csv = f'file_sizes_summary_{args.run_id}.csv'
    
    if args.output_plot is None:
        args.output_plot = f'file_sizes_histogram_{args.run_id}.png'
    
    # Make output paths absolute within output directory
    args.output_csv = os.path.join(args.output_dir, os.path.basename(args.output_csv))
    args.output_plot = os.path.join(args.output_dir, os.path.basename(args.output_plot))
    
    logger.info(f"Directory pattern: {args.directory}")
    logger.info(f"Output directory: {args.output_dir}")
    logger.info(f"Output CSV: {args.output_csv}")
    logger.info(f"Output plot: {args.output_plot}")
    
    try:
        # Validate arguments
        if not validate_arguments(args, logger):
            sys.exit(1)
        
        # Get file sizes
        file_sizes = get_file_sizes(args.directory, logger)
        
        if not file_sizes:
            logger.warning("No files found matching the directory pattern")
        
        # Calculate summary statistics
        summary = summarize_file_sizes(file_sizes, logger)
        
        # Print summary to console
        print_summary(summary, logger)
        
        # Save results to CSV
        save_file_sizes_to_csv(file_sizes, args.output_csv, logger)
        
        # Create and save histogram
        plot_file_sizes_histogram(file_sizes, args.run_id, args.output_plot, logger)
        
        logger.info("="*60)
        logger.info("FILE SIZE ANALYSER COMPLETED SUCCESSFULLY")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        logger.error("="*60)
        logger.error("FILE SIZE ANALYSER FAILED")
        logger.error("="*60)
        sys.exit(1)


if __name__ == '__main__':
    main()

