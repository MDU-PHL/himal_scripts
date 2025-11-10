#!/usr/bin/env python3
"""
Generate download.sh and index.html files for FASTQ files in a directory.

This script scans a directory for FASTQ.gz files and creates:
1. download.sh - wget commands for downloading files
2. index.html - HTML links for browsing files
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List


def setup_logging() -> logging.Logger:
    """Set up logging with custom format [YYYY-MM-DD HH:MM:SS] - LEVEL: message."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    
    # Create custom formatter
    class CustomFormatter(logging.Formatter):
        def format(self, record):
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            return f"[{timestamp}] - {record.levelname}: {record.getMessage()}"
    
    handler.setFormatter(CustomFormatter())
    logger.addHandler(handler)
    
    return logger


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Generate download.sh and index.html files for FASTQ files in a directory.',
        epilog='Example: %(prog)s -d /home/user/public_html/tmp/abc123xyz/',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '-d', '--directory',
        type=str,
        required=True,
        metavar='PATH',
        help='Path to the directory containing FASTQ.gz files (e.g., /home/<user>/public_html/tmp/xxxxxxxxxxxxxxxxxx/)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output (DEBUG level logging)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 1.0.0'
    )
    
    return parser.parse_args()


def extract_user_and_path(directory_path: str, logger: logging.Logger) -> tuple:
    """
    Extract username and relative path from public_html directory path.
    
    Args:
        directory_path: Full path to the directory
        logger: Logger instance
        
    Returns:
        Tuple of (username, relative_path) or (None, None) if extraction fails
    """
    try:
        path_parts = Path(directory_path).parts
        
        # Find public_html in the path
        if 'public_html' not in path_parts:
            logger.error("Path does not contain 'public_html' directory")
            return None, None
        
        # Extract username (parent directory of public_html)
        public_html_idx = path_parts.index('public_html')
        if public_html_idx < 2:
            logger.error("Cannot extract username from path")
            return None, None
        
        username = path_parts[public_html_idx - 1]
        
        # Extract relative path after public_html
        relative_parts = path_parts[public_html_idx + 1:]
        relative_path = '/'.join(relative_parts)
        
        logger.debug(f"Extracted username: {username}, relative path: {relative_path}")
        return username, relative_path
        
    except Exception as e:
        logger.error(f"Failed to extract user and path: {e}")
        return None, None


def scan_fastq_files(directory: str, logger: logging.Logger) -> List[str]:
    """
    Scan directory for all FASTQ.gz files.
    
    Args:
        directory: Path to the directory to scan
        logger: Logger instance
        
    Returns:
        Sorted list of FASTQ.gz filenames
    """
    logger.info(f"Scanning directory: {directory}")
    
    try:
        dir_path = Path(directory)
        
        if not dir_path.exists():
            logger.error(f"Directory does not exist: {directory}")
            return []
        
        if not dir_path.is_dir():
            logger.error(f"Path is not a directory: {directory}")
            return []
        
        # Find all .fastq.gz files
        fastq_files = sorted([f.name for f in dir_path.glob('*.fastq.gz')])
        
        logger.info(f"Found {len(fastq_files)} FASTQ.gz files")
        logger.debug(f"Files: {fastq_files}")
        
        return fastq_files
        
    except Exception as e:
        logger.error(f"Error scanning directory: {e}")
        return []


def generate_download_script(directory: str, username: str, relative_path: str, 
                            fastq_files: List[str], logger: logging.Logger) -> bool:
    """
    Generate download.sh file with wget commands.
    
    Args:
        directory: Path to the output directory
        username: Username extracted from path
        relative_path: Relative path after public_html
        fastq_files: List of FASTQ filenames
        logger: Logger instance
        
    Returns:
        True if successful, False otherwise
    """
    output_file = Path(directory) / 'download.sh'
    logger.info(f"Generating download script: {output_file}")
    
    try:
        with open(output_file, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("# Download script for FASTQ files\n")
            f.write(f"# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for filename in fastq_files:
                url = f"https://bioinformatics.mdu.unimelb.edu.au/~{username}/{relative_path}/{filename}"
                f.write(f"wget --continue {url}\n")
        
        # Make the script executable
        os.chmod(output_file, 0o755)
        
        logger.info(f"Successfully created download.sh with {len(fastq_files)} wget commands")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create download.sh: {e}")
        return False


def generate_index_html(directory: str, fastq_files: List[str], logger: logging.Logger) -> bool:
    """
    Generate index.html file with file links.
    
    Args:
        directory: Path to the output directory
        fastq_files: List of FASTQ filenames
        logger: Logger instance
        
    Returns:
        True if successful, False otherwise
    """
    output_file = Path(directory) / 'index.html'
    logger.info(f"Generating index file: {output_file}")
    
    try:
        with open(output_file, 'w') as f:
            f.write("<!DOCTYPE html>\n")
            f.write("<html>\n")
            f.write("<head>\n")
            f.write("    <title>FASTQ Files</title>\n")
            f.write("    <meta charset='UTF-8'>\n")
            f.write("</head>\n")
            f.write("<body>\n")
            f.write("    <h1>FASTQ Files</h1>\n")
            f.write(f"    <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>\n")
            f.write("    <ul>\n")
            
            for filename in fastq_files:
                f.write(f"        <li><a href='{filename}'>{filename}</a></li>\n")
            
            f.write("    </ul>\n")
            f.write("</body>\n")
            f.write("</html>\n")
        
        logger.info(f"Successfully created index.html with {len(fastq_files)} file links")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create index.html: {e}")
        return False


def main():
    """Main function to orchestrate the script execution."""
    # Parse arguments
    args = parse_arguments()
    
    # Setup logging
    logger = setup_logging()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
    
    logger.info("Starting download link generation script")
    logger.info(f"Target directory: {args.directory}")
    
    # Normalize directory path
    directory = os.path.abspath(os.path.expanduser(args.directory))
    
    # Extract username and relative path
    username, relative_path = extract_user_and_path(directory, logger)
    if not username or relative_path is None:
        logger.error("Failed to extract username and path from directory")
        sys.exit(1)
    
    # Scan for FASTQ files
    fastq_files = scan_fastq_files(directory, logger)
    if not fastq_files:
        logger.warning("No FASTQ.gz files found in directory")
        sys.exit(1)
    
    # Generate download script
    download_success = generate_download_script(directory, username, relative_path, 
                                                fastq_files, logger)
    
    # Generate index HTML
    html_success = generate_index_html(directory, fastq_files, logger)
    
    # Report results
    if download_success and html_success:
        logger.info("Successfully generated both download.sh and index.html")
        logger.info(f"Output files location: {directory}")
        sys.exit(0)
    else:
        logger.error("Failed to generate one or more output files")
        sys.exit(1)


if __name__ == '__main__':
    main()