#!/usr/bin/env python3
"""
Match phylogenetic tree tip labels with metadata file entries.

This script reads a phylogenetic tree file and a metadata file, then creates
a new column in the metadata that matches the tree tip labels by cleaning
and matching the identifiers.
"""

import argparse
import csv
import logging
import os
import sys
from datetime import datetime
from typing import List, Dict, Tuple, Optional

# Setup logging format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%d-%m-%Y %H:%M:%S'
)
logger = logging.getLogger(__name__)


def read_tree_file(tree_file: str) -> List[str]:
    """
    Read phylogenetic tree file and extract tip labels.
    
    Args:
        tree_file: Path to the tree file (Newick format)
        
    Returns:
        List of tip labels from the tree
        
    Raises:
        FileNotFoundError: If tree file doesn't exist
        Exception: For other file reading errors
    """
    try:
        logger.info(f"Reading tree file: {tree_file}")
        
        if not os.path.exists(tree_file):
            raise FileNotFoundError(f"Tree file not found: {tree_file}")
            
        with open(tree_file, 'r', encoding='utf-8') as f:
            tree_content = f.read().strip()
            
        # Extract tip labels from Newick format
        # Remove branch lengths and internal node labels
        import re
        
        # Find all sequences that look like tip labels
        # Pattern matches: word characters, dots, dashes, underscores until comma, colon, or parenthesis
        pattern = r'([A-Za-z0-9._-]+)(?=[:,\)])'
        potential_tips = re.findall(pattern, tree_content)
        
        # Filter out numeric values (likely branch lengths)
        tip_labels = []
        for tip in potential_tips:
            # Skip if it's purely numeric (branch length)
            if not tip.replace('.', '').replace('-', '').isdigit():
                tip_labels.append(tip)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_tips = []
        for tip in tip_labels:
            if tip not in seen:
                seen.add(tip)
                unique_tips.append(tip)
                
        logger.info(f"Found {len(unique_tips)} unique tip labels in tree")
        return unique_tips
        
    except FileNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error reading tree file: {str(e)}")
        raise


def read_metadata_file(metadata_file: str) -> Tuple[List[str], List[List[str]]]:
    """
    Read metadata CSV file.
    
    Args:
        metadata_file: Path to the metadata CSV file
        
    Returns:
        Tuple of (headers, data_rows)
        
    Raises:
        FileNotFoundError: If metadata file doesn't exist
        Exception: For other file reading errors
    """
    try:
        logger.info(f"Reading metadata file: {metadata_file}")
        
        if not os.path.exists(metadata_file):
            raise FileNotFoundError(f"Metadata file not found: {metadata_file}")
            
        headers = []
        data_rows = []
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            # Try to detect delimiter
            sample = f.read(1024)
            f.seek(0)
            
            delimiter = ','
            if sample.count('\t') > sample.count(','):
                delimiter = '\t'
                
            reader = csv.reader(f, delimiter=delimiter)
            headers = next(reader)
            
            for row in reader:
                data_rows.append(row)
                
        logger.info(f"Read metadata with {len(headers)} columns and {len(data_rows)} rows")
        return headers, data_rows
        
    except FileNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error reading metadata file: {str(e)}")
        raise


def clean_identifier(identifier: str) -> str:
    """
    Clean identifier by removing common suffixes and extra characters.
    
    Args:
        identifier: Raw identifier string
        
    Returns:
        Cleaned identifier
    """
    # Common suffixes to remove
    suffixes_to_remove = [
        '_trim', '_trimmed', '_other_extra_ids', '_extra', '_final',
        '_clean', '_processed', '_filtered', '_consensus', '_contigs'
    ]
    
    cleaned = identifier
    
    # Remove common suffixes
    for suffix in suffixes_to_remove:
        if cleaned.endswith(suffix):
            cleaned = cleaned[:-len(suffix)]
            
    # Remove trailing numbers if they look like version numbers
    import re
    cleaned = re.sub(r'_v?\d+$', '', cleaned)
    cleaned = re.sub(r'\.\d+$', '', cleaned)
    
    return cleaned


def find_best_match(tip_label: str, metadata_ids: List[str]) -> Optional[str]:
    """
    Find the best matching metadata ID for a tree tip label.
    
    Args:
        tip_label: Tree tip label to match
        metadata_ids: List of metadata identifiers
        
    Returns:
        Best matching metadata ID or None if no match found
    """
    cleaned_tip = clean_identifier(tip_label)
    
    # Try exact match first
    if cleaned_tip in metadata_ids:
        return cleaned_tip
        
    # Try partial matches
    for meta_id in metadata_ids:
        cleaned_meta = clean_identifier(meta_id)
        
        # Check if cleaned versions match
        if cleaned_tip == cleaned_meta:
            return meta_id
            
        # Check if one is contained in the other
        if cleaned_tip in cleaned_meta or cleaned_meta in cleaned_tip:
            return meta_id
            
    return None


def match_tree_metadata(tree_tips: List[str], headers: List[str], 
                       data_rows: List[List[str]], column_index: int) -> Tuple[List[str], List[List[str]]]:
    """
    Match tree tips with metadata and create new column.
    
    Args:
        tree_tips: List of tree tip labels
        headers: Metadata headers
        data_rows: Metadata data rows
        column_index: Index of column to match against
        
    Returns:
        Tuple of (new_headers, new_data_rows)
    """
    logger.info("Starting matching process")
    
    # Extract metadata IDs from specified column
    metadata_ids = [row[column_index] for row in data_rows if len(row) > column_index]
    
    # Create mapping from metadata IDs to tree tip labels
    id_to_tip = {}
    matched_count = 0
    
    for tip in tree_tips:
        best_match = find_best_match(tip, metadata_ids)
        if best_match:
            id_to_tip[best_match] = tip
            matched_count += 1
            
    logger.info(f"Successfully matched {matched_count} out of {len(tree_tips)} tree tips")
    
    # Add new column to headers
    new_headers = headers + ['tree_tip_label']
    
    # Add new column to data rows
    new_data_rows = []
    for row in data_rows:
        if len(row) > column_index:
            metadata_id = row[column_index]
            tree_tip = id_to_tip.get(metadata_id, '')
            new_row = row + [tree_tip]
        else:
            new_row = row + ['']
        new_data_rows.append(new_row)
        
    return new_headers, new_data_rows


def write_output_file(output_file: str, headers: List[str], data_rows: List[List[str]]):
    """
    Write the matched metadata to output file.
    
    Args:
        output_file: Path to output file
        headers: Column headers
        data_rows: Data rows
        
    Raises:
        Exception: For file writing errors
    """
    try:
        logger.info(f"Writing output to: {output_file}")
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(data_rows)
            
        logger.info(f"Successfully wrote {len(data_rows)} rows to output file")
        
    except Exception as e:
        logger.error(f"Error writing output file: {str(e)}")
        raise


def main():
    """Main function to run the matching process."""
    parser = argparse.ArgumentParser(
        description='Match phylogenetic tree tip labels with metadata file entries',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -m metadata.csv -t tree.dnd -c 0 -o matched_metadata.csv
  %(prog)s --metadata data.tsv --tree phylo.nwk --column sample_id --output result.csv
  
The script will:
1. Read the phylogenetic tree and extract tip labels
2. Read the metadata file
3. Clean and match identifiers between tree tips and metadata
4. Create a new column 'tree_tip_label' in the metadata
5. Write the updated metadata to the output file
        """
    )
    
    parser.add_argument(
        '-m', '--metadata',
        required=True,
        help='Path to metadata CSV/TSV file'
    )
    
    parser.add_argument(
        '-t', '--tree',
        required=True,
        help='Path to phylogenetic tree file (Newick format)'
    )
    
    parser.add_argument(
        '-c', '--column',
        default='0',
        help='Column in metadata to match with tree tips (default: 0 for first column, or column name)'
    )
    
    parser.add_argument(
        '-o', '--output',
        default='matched_metadata.csv',
        help='Output file path (default: matched_metadata.csv)'
    )
    
    args = parser.parse_args()
    
    try:
        logger.info("Starting tree-metadata matching process")
        
        # Read tree file
        tree_tips = read_tree_file(args.tree)
        
        # Read metadata file
        headers, data_rows = read_metadata_file(args.metadata)
        
        # Determine column index
        try:
            column_index = int(args.column)
        except ValueError:
            # Column name provided, find index
            if args.column in headers:
                column_index = headers.index(args.column)
            else:
                raise ValueError(f"Column '{args.column}' not found in metadata headers: {headers}")
        
        # Validate column index
        if column_index < 0 or column_index >= len(headers):
            raise ValueError(f"Column index {column_index} out of range (0-{len(headers)-1})")
            
        logger.info(f"Using column '{headers[column_index]}' (index {column_index}) for matching")
        
        # Match tree tips with metadata
        new_headers, new_data_rows = match_tree_metadata(tree_tips, headers, data_rows, column_index)
        
        # Write output file
        write_output_file(args.output, new_headers, new_data_rows)
        
        logger.info("Process completed successfully")
        
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Invalid argument: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()