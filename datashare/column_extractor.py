#!/usr/bin/env python3
"""
Script to extract columns from one file and add them to another file based on matching keys.
"""

import argparse
import sys
import csv
from typing import Dict, List, Tuple, Set, Optional, Any, TextIO


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract columns from one file and add them to another based on a common key.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Add columns 3,4 from donor.csv to recipient.tsv where recipient column 0 matches donor column 2
  python column_extractor.py -1 recipient.tsv -2 donor.csv -k1 0 -k2 2 -c 3,4 -o result.tsv -d1 tab -d2 comma
  
  # Add column 1 from genes.csv to expression.tsv where expression column 'Gene_ID' matches genes column 'ID'
  python column_extractor.py -1 expression.tsv -2 genes.csv -k1 Gene_ID -k2 ID -c Description -o result.csv -d1 tab -d2 comma --headers
  """
    )
    
    parser.add_argument("-1", "--file1", required=True, help="Path to the recipient file (file to add columns to)")
    parser.add_argument("-2", "--file2", required=True, help="Path to the donor file (file to extract columns from)")
    parser.add_argument("-k1", "--key1", required=True, help="Column in file1 to use as mapping key (0-based index or header name)")
    parser.add_argument("-k2", "--key2", required=True, help="Column in file2 to use as mapping key (0-based index or header name)")
    parser.add_argument("-c", "--columns", required=True, help="Comma-separated list of columns to extract from file2 (0-based indices or header names)")
    parser.add_argument("-o", "--output", required=True, help="Path to save the output file")
    parser.add_argument("-d1", "--delimiter1", default="tab", choices=["tab", "comma", "space", "semicolon", "custom"],
                        help="Delimiter used in file1 (default: tab)")
    parser.add_argument("-d2", "--delimiter2", default="tab", choices=["tab", "comma", "space", "semicolon", "custom"],
                        help="Delimiter used in file2 (default: tab)")
    parser.add_argument("--custom-delim1", help="Custom delimiter for file1 if delimiter1 is 'custom'")
    parser.add_argument("--custom-delim2", help="Custom delimiter for file2 if delimiter2 is 'custom'")
    parser.add_argument("--output-delimiter", default="same-as-file1", 
                       choices=["tab", "comma", "space", "semicolon", "custom", "same-as-file1"],
                       help="Delimiter to use in the output file (default: same as file1)")
    parser.add_argument("--custom-output-delim", help="Custom delimiter for output if output-delimiter is 'custom'")
    parser.add_argument("--headers", action="store_true", help="Indicate that both files have headers")
    
    return parser.parse_args()


def get_delimiter(delim_option: str, custom_delim: Optional[str] = None) -> str:
    """Convert delimiter option to actual delimiter character."""
    delimiters = {
        "tab": "\t",
        "comma": ",",
        "space": " ",
        "semicolon": ";",
        "custom": custom_delim
    }
    
    if delim_option == "custom" and custom_delim is None:
        raise ValueError("Custom delimiter option selected but no custom delimiter provided")
    
    return delimiters[delim_option]


def parse_column_indices(columns_str: str, headers: Optional[List[str]] = None) -> List[int]:
    """Parse column indices from comma-separated string. Convert header names to indices if headers provided."""
    columns = columns_str.split(",")
    
    if headers:
        # Create mapping of header name to index
        header_map = {name: idx for idx, name in enumerate(headers)}
        parsed_indices = []
        
        for col in columns:
            col = col.strip()
            if col in header_map:
                parsed_indices.append(header_map[col])
            else:
                try:
                    parsed_indices.append(int(col))
                except ValueError:
                    raise ValueError(f"Column '{col}' not found in headers and is not a valid integer index")
        return parsed_indices
    else:
        # No headers, all columns should be integer indices
        try:
            return [int(col.strip()) for col in columns]
        except ValueError:
            raise ValueError("Column indices must be integers when not using headers")


def read_file_with_csv(file_path: str, delimiter: str) -> List[List[str]]:
    """Read a delimited file using csv module and return rows as lists."""
    with open(file_path, 'r', newline='') as f:
        reader = csv.reader(f, delimiter=delimiter)
        return [row for row in reader]


def extract_data_from_file2(
    file2_path: str, 
    delimiter2: str, 
    key2_idx: int, 
    columns_to_extract: List[int]
) -> Dict[str, List[str]]:
    """
    Extract data from file2 and return a mapping from key to extracted columns.
    
    Args:
        file2_path: Path to file2
        delimiter2: Delimiter used in file2
        key2_idx: Index of the key column in file2
        columns_to_extract: List of column indices to extract from file2
    
    Returns:
        Dictionary mapping keys to lists of extracted values
    """
    data_map = {}
    rows = read_file_with_csv(file2_path, delimiter2)
    
    for row in rows:
        if key2_idx >= len(row):
            continue  # Skip rows that don't have the key column
        
        key = row[key2_idx]
        values = []
        
        for col_idx in columns_to_extract:
            if col_idx < len(row):
                values.append(row[col_idx])
            else:
                values.append("")  # Handle missing columns
        
        data_map[key] = values
    
    return data_map


def merge_files(
    file1_path: str,
    file2_data: Dict[str, List[str]],
    key1_idx: int,
    delimiter1: str,
    output_path: str,
    output_delimiter: str,
    has_headers: bool,
    extracted_column_names: Optional[List[str]] = None
) -> Tuple[int, int, Set[str]]:
    """
    Merge file1 with extracted data from file2 and write to output file.
    
    Args:
        file1_path: Path to file1
        file2_data: Dictionary mapping keys to extracted values from file2
        key1_idx: Index of the key column in file1
        delimiter1: Delimiter used in file1
        output_path: Path to save the output file
        output_delimiter: Delimiter to use in the output file
        has_headers: Whether the files have headers
        extracted_column_names: Names of the extracted columns (for header row)
    
    Returns:
        Tuple of (total_rows, mapped_rows, set of unmapped keys)
    """
    rows = read_file_with_csv(file1_path, delimiter1)
    if not rows:
        return 0, 0, set()
    
    mapped_count = 0
    unmapped_keys = set()
    total_rows = len(rows) - (1 if has_headers else 0)
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f, delimiter=output_delimiter)
        
        # Handle header row if present
        if has_headers and rows:
            header_row = rows[0]
            if extracted_column_names:
                writer.writerow(header_row + extracted_column_names)
            else:
                writer.writerow(header_row + [f"column_{i}" for i in range(len(list(file2_data.values())[0]) if file2_data else 0)])
            
            start_idx = 1
        else:
            start_idx = 0
        
        # Process data rows
        for i in range(start_idx, len(rows)):
            row = rows[i]
            if key1_idx < len(row):
                key = row[key1_idx]
                if key in file2_data:
                    writer.writerow(row + file2_data[key])
                    mapped_count += 1
                else:
                    writer.writerow(row + [""] * (len(list(file2_data.values())[0]) if file2_data else 0))
                    unmapped_keys.add(key)
            else:
                # Handle rows that don't have the key column
                writer.writerow(row + [""] * (len(list(file2_data.values())[0]) if file2_data else 0))
    
    return total_rows, mapped_count, unmapped_keys


def main() -> int:
    """Main function to extract and merge columns."""
    try:
        args = parse_args()
        
        # Get actual delimiters
        delimiter1 = get_delimiter(args.delimiter1, args.custom_delim1)
        delimiter2 = get_delimiter(args.delimiter2, args.custom_delim2)
        
        # Determine output delimiter
        if args.output_delimiter == "same-as-file1":
            output_delimiter = delimiter1
        else:
            output_delimiter = get_delimiter(args.output_delimiter, args.custom_output_delim)
        
        # Read headers if specified
        file1_headers = None
        file2_headers = None
        
        if args.headers:
            with open(args.file1, 'r', newline='') as f:
                reader = csv.reader(f, delimiter=delimiter1)
                file1_headers = next(reader, None)
                
            with open(args.file2, 'r', newline='') as f:
                reader = csv.reader(f, delimiter=delimiter2)
                file2_headers = next(reader, None)
        
        # Parse key indices
        key1_idx = int(args.key1) if not args.headers or args.key1.isdigit() else file1_headers.index(args.key1)
        key2_idx = int(args.key2) if not args.headers or args.key2.isdigit() else file2_headers.index(args.key2)
        
        # Parse columns to extract
        columns_to_extract = parse_column_indices(args.columns, file2_headers if args.headers else None)
        
        # Get column names for headers in output
        extracted_column_names = None
        if args.headers and file2_headers:
            extracted_column_names = [file2_headers[idx] for idx in columns_to_extract if idx < len(file2_headers)]
        
        # Extract data from file2
        file2_data = extract_data_from_file2(args.file2, delimiter2, key2_idx, columns_to_extract)
        
        # Merge files and write output
        total_rows, mapped_rows, unmapped_keys = merge_files(
            args.file1, file2_data, key1_idx, delimiter1, 
            args.output, output_delimiter, args.headers, extracted_column_names
        )
        
        # Print summary
        print(f"Total rows processed: {total_rows}")
        # Calculate percentages with conditional logic outside the f-string
        mapped_percentage = (mapped_rows/total_rows*100) if total_rows > 0 else 0
        unmapped_percentage = (len(unmapped_keys)/total_rows*100) if total_rows > 0 else 0
        
        print(f"Rows with mapped keys: {mapped_rows} ({mapped_percentage:.2f}%)")
        print(f"Rows with unmapped keys: {len(unmapped_keys)} ({unmapped_percentage:.2f}%)")        
        
        if unmapped_keys and len(unmapped_keys) <= 10:
            print(f"Unmapped keys: {', '.join(sorted(unmapped_keys))}")
        elif unmapped_keys:
            print(f"First 10 unmapped keys: {', '.join(sorted(list(unmapped_keys)[:10]))}")
            print(f"...and {len(unmapped_keys) - 10} more")
        
        print(f"Output saved to: {args.output}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())