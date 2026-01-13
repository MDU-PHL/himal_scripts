#!/usr/bin/env python3
"""
Generate download.sh and index.html files for files in a directory.

This script scans a directory for files with specified extensions and creates:
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
        description='Generate download.sh and index.html files for files in a directory.',
        epilog='Example: %(prog)s -d /home/user/public_html/tmp/abc123xyz/ -e .fastq.gz .fasta',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '-d', '--directory',
        type=str,
        required=True,
        metavar='PATH',
        help='Path to the directory containing files (e.g., /home/<user>/public_html/tmp/xxxxxxxxxxxxxxxxxx/)'
    )
    
    parser.add_argument(
        '-e', '--extensions',
        type=str,
        nargs='+',
        default=['.fastq.gz'],
        metavar='EXT',
        help='File extensions to search for (default: .fastq.gz). Can specify multiple extensions (e.g., -e .fastq.gz .fasta .bam)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output (DEBUG level logging)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 1.1.0'
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


def scan_files(directory: str, extensions: List[str], logger: logging.Logger) -> List[str]:
    """
    Scan directory for all files with specified extensions.
    
    Args:
        directory: Path to the directory to scan
        extensions: List of file extensions to search for
        logger: Logger instance
        
    Returns:
        Sorted list of matching filenames
    """
    logger.info(f"Scanning directory: {directory}")
    logger.info(f"Looking for extensions: {', '.join(extensions)}")
    
    try:
        dir_path = Path(directory)
        
        if not dir_path.exists():
            logger.error(f"Directory does not exist: {directory}")
            return []
        
        if not dir_path.is_dir():
            logger.error(f"Path is not a directory: {directory}")
            return []
        
        # Find all files matching any of the extensions
        all_files = []
        for ext in extensions:
            # Ensure extension starts with a dot
            if not ext.startswith('.'):
                ext = '.' + ext
            pattern = f'*{ext}'
            matching_files = [f.name for f in dir_path.glob(pattern)]
            all_files.extend(matching_files)
            logger.debug(f"Found {len(matching_files)} files matching {pattern}")
        
        # Remove duplicates and sort
        unique_files = sorted(set(all_files))
        
        logger.info(f"Found {len(unique_files)} files total")
        logger.debug(f"Files: {unique_files}")
        
        return unique_files
      
    except Exception as e:
        logger.error(f"Error scanning directory: {e}")
        return []


def generate_download_script(directory: str, username: str, relative_path: str, 
                            files: List[str], logger: logging.Logger) -> bool:
    """
    Generate download.sh file with wget commands.
    
    Args:
        directory: Path to the output directory
        username: Username extracted from path
        relative_path: Relative path after public_html
        files: List of filenames
        logger: Logger instance
        
    Returns:
        True if successful, False otherwise
    """
    output_file = Path(directory) / 'download.sh'
    logger.info(f"Generating download script: {output_file}")
    
    try:
        with open(output_file, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("# Download script for files\n")
            f.write(f"# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for filename in files:
                url = f"https://bioinformatics.mdu.unimelb.edu.au/~{username}/{relative_path}/{filename}"
                f.write(f"wget --continue {url}\n")
        
        # Make the script executable
        os.chmod(output_file, 0o755)
        
        logger.info(f"Successfully created download.sh with {len(files)} wget commands")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create download.sh: {e}")
        return False


def generate_index_html(directory: str, files: List[str], logger: logging.Logger) -> bool:
    """
    Generate index.html file with file links.
    
    Args:
        directory: Path to the output directory
        files: List of filenames
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
            f.write("    <title>Files</title>\n")
            f.write("    <meta charset='UTF-8'>\n")
            f.write("</head>\n")
            f.write("<body>\n")
            f.write("    <h1>Files</h1>\n")
            f.write(f"    <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>\n")
            f.write("    <ul>\n")
            
            for filename in files:
                f.write(f"        <li><a href='{filename}'>{filename}</a></li>\n")
            
            f.write("    </ul>\n")
            f.write("</body>\n")
            f.write("</html>\n")
        
        logger.info(f"Successfully created index.html with {len(files)} file links")
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
    
    # Normalise directory path
    directory = os.path.abspath(os.path.expanduser(args.directory))
    
    # Extract username and relative path
    username, relative_path = extract_user_and_path(directory, logger)
    if not username or relative_path is None:
        logger.error("Failed to extract username and path from directory")
        sys.exit(1)
    
    # Scan for files
    files = scan_files(directory, args.extensions, logger)
    if not files:
        logger.warning(f"No files found with extensions: {', '.join(args.extensions)}")
        sys.exit(1)
    
    # Generate download script
    download_success = generate_download_script(directory, username, relative_path, 
                                                files, logger)
    
    # Generate index HTML
    html_success = generate_index_html(directory, files, logger)
    
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