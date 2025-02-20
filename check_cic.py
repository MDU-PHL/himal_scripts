#!/usr/bin/env python3
import typer
import pandas as pd
import glob
from pathlib import Path
from typing import Optional
import warnings

# Add this after imports to suppress all warnings
warnings.filterwarnings('ignore')

app = typer.Typer()

def read_sample_ids(ids_file: Path) -> list:
    """Read sample IDs from the input file."""
    with open(ids_file) as f:
        return [line.strip() for line in f if line.strip()]


def check_cic_status(sample_id: str, distribute_tables: list, verbose: bool = False) -> str:
    """Check CiC status for a given sample ID across distribute tables."""
    sample_found = False
    
    for table_path in distribute_tables:
        try:
            # Add debug output only if verbose
            if verbose:
                typer.echo(f"Checking file: {table_path}")
            
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
                        typer.echo(f"Found sample with CiC value: {cic_value}")
                    return "Yes" if cic_value == "yes" else "No"
                else:
                    if verbose:
                        typer.echo(f"Sample found but no CiC column in {table_path}")
                    return "No"  # If no CiC column exists, treat as not a CiC sample
            else:
                if verbose:
                    typer.echo(f"Sample {sample_id} not found in {table_path}")
                
        except Exception as e:
            if verbose:
                typer.echo(f"Warning: Error processing {table_path}: {e}", err=True)
            continue
    
    return "Not found"

@app.command()
def main(
    ids_file: Path = typer.Argument(..., help="Path to file containing sample IDs"),
    output_file: Path = typer.Option("cic_results.csv", help="Path to output CSV file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
):
    """Check CiC status for samples listed in the input file."""
    # Validate input file
    if not ids_file.exists():
        typer.echo(f"Error: Input file {ids_file} not found", err=True)
        raise typer.Exit(1)

    # Get all distribute table files
    distribute_tables = glob.glob("/home/mdu/qc/*/*/distribute_table.txt*")
    if not distribute_tables:
        typer.echo("Error: No distribute tables found", err=True)
        raise typer.Exit(1)

    # Read sample IDs
    sample_ids = read_sample_ids(ids_file)
    if not sample_ids:
        typer.echo("Error: No sample IDs found in input file", err=True)
        raise typer.Exit(1)

    # Process each sample
    results = []
    with typer.progressbar(sample_ids, label="Processing samples") as progress:
        for sample_id in progress:
            status = check_cic_status(sample_id, distribute_tables, verbose)
            results.append({"Sample ID": sample_id, "CiC": status})

    # Save results
    df = pd.DataFrame(results)
    df.to_csv(output_file, index=False)
    typer.echo(f"Results saved to {output_file}")
    
if __name__ == "__main__":
    app()