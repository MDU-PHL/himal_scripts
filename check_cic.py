#!/usr/bin/env python3
import argparse
import pandas as pd
import glob
from pathlib import Path
import warnings
from tqdm import tqdm


# Add this after imports to suppress all warnings
warnings.filterwarnings('ignore')

def read_sample_ids(ids_file: Path) -> list:
    """Read sample IDs from the input file."""
    with open(ids_file) as f:
        return [line.strip() for line in f if line.strip()]

def check_cic_status(sample_id: str, distribute_tables: list, verbose: bool = False) -> str:
    """Check CiC status for a given sample ID across distribute tables."""
    sample_found = False
    
    for table_path in distribute_tables:
        try:
            if verbose:
                print(f"Checking file: {table_path}")
            
            # Read file with explicit encoding and handle whitespace
            df = pd.read_csv(table_path, sep='\t', encoding='utf-8', skipinitialspace=True)
            
            # Convert everything to string and handle NaN values
            df.iloc[:, 0] = df.iloc[:, 0].fillna('').astype(str).str.strip()
            sample_id = str(sample_id).strip()
            
            # First check if sample exists in the first column
            sample_row = df[df.iloc[:, 0] == sample_id]
            if not sample_row.empty:
                sample_found = True
                
                # Now check for CiC column
                cic_col = next((col for col in df.columns if col.lower() == 'cic'), None)
                if cic_col:
                    cic_value = str(sample_row[cic_col].iloc[0]).lower().strip()
                    if verbose:
                        print(f"Found sample with CiC value: {cic_value}")
                    return "Yes" if cic_value == "yes" else "No"
                else:
                    if verbose:
                        print(f"Sample found but no CiC column in {table_path}")
                    return "No"  # If no CiC column exists, treat as not a CiC sample
            else:
                if verbose:
                    print(f"Sample {sample_id} not found in {table_path}")
                
        except Exception as e:
            if verbose:
                print(f"Warning: Error processing {table_path}: {e}", file=sys.stderr)
            continue
    
    return "Not found"

def main():
    """Check CiC status for samples listed in the input file."""
    parser = argparse.ArgumentParser(
        description="Check CiC status for samples listed in the input file."
    )

    parser.add_argument(
        "ids_file",
        type=Path,
        help="Path to file containing sample IDs"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default="cic_results.csv",
        help="Path to output CSV file (default: cic_results.csv)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()

    # Validate input file
    if not args.ids_file.exists():
        print(f"Error: Input file {args.ids_file} not found", file=sys.stderr)
        sys.exit(1)

    # Get all distribute table files
    distribute_tables = glob.glob("/home/mdu/qc/*/*/distribute_table.txt*")
    if not distribute_tables:
        print("Error: No distribute tables found", file=sys.stderr)
        sys.exit(1)

    # Read sample IDs
    sample_ids = read_sample_ids(args.ids_file)
    if not sample_ids:
        print("Error: No sample IDs found in input file", file=sys.stderr)
        sys.exit(1)

    # Process each sample with progress bar
    results = []
    with tqdm(total=len(sample_ids), desc="Processing samples") as pbar:
        for sample_id in sample_ids:
            if args.verbose:
                print(f"\nProcessing: {sample_id}")
            status = check_cic_status(sample_id, distribute_tables, args.verbose)
            results.append({"Sample ID": sample_id, "CiC": status})
            pbar.update(1)

    # Save results
    df = pd.DataFrame(results)
    df.to_csv(args.output, index=False)
    print(f"\nResults saved to {args.output}")

if __name__ == "__main__":
    main()
    