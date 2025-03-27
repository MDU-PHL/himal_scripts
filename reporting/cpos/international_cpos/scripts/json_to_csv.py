import click
import json
import csv
from pathlib import Path

@click.command()
@click.argument('input_json', type=click.Path(exists=True))
@click.argument('output_csv', type=click.Path())
@click.option('--verbose', '-v', is_flag=True, help='Print verbose output')
def extract_metadata(input_json, output_csv, verbose):
    """Extract metadata from JSON file and save to CSV.
    
    INPUT_JSON: Path to input JSON file
    OUTPUT_CSV: Path to output CSV file
    """
    if verbose:
        click.echo(f"Reading from {input_json}")
    
    # Read JSON file
    with open(input_json) as f:
        data = []
        for line in f:
            data.append(json.loads(line))
    
    # Extract relevant fields
    csv_data = []
    for entry in data:
        row = {
            'accession': entry.get('accession', ''),
            'bioprojectAccession': entry.get('assemblyInfo', {}).get('bioprojectAccession', ''),
            'biosampleAccession': entry.get('assemblyInfo', {}).get('biosample', {}).get('accession', ''),
            'geoLocName': entry.get('assemblyInfo', {}).get('biosample', {}).get('geoLocName', '')
        }
        csv_data.append(row)
    
    # Write to CSV
    with open(output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['accession', 'bioprojectAccession', 'biosampleAccession', 'geoLocName'])
        writer.writeheader()
        writer.writerows(csv_data)
    
    if verbose:
        click.echo(f"Wrote {len(csv_data)} entries to {output_csv}")

if __name__ == '__main__':
    extract_metadata()