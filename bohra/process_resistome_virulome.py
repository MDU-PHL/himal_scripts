#!/usr/bin/env python3

import argparse
import csv
import os

def read_file(file_path):
    """Reads the TSV file and returns header and data."""
    with open(file_path, newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter='\t')
        header = next(reader)
        data = [row for row in reader]
    return header, data

def get_isolate_factors(header, data, isolate):
    """Returns resistance/virulence factors for the specified isolate as a dictionary."""
    isolate_row = next((row for row in data if row[0] == isolate), None)
    if isolate_row:
        factors = {header[i]: isolate_row[i] for i in range(1, len(header)) if isolate_row[i]}
        return factors
    else:
        return {}

def get_unique_factors(header, data, isolate):
    """Finds and returns unique resistance/virulence factors for the specified isolate."""
    isolate_factors = get_isolate_factors(header, data, isolate)
    unique_factors = {}

    for column in isolate_factors:
        column_index = header.index(column)
        column_entries = [row[column_index] for row in data if row[column_index]]
        unique_entries = set(entry for entry in column_entries if column_entries.count(entry) == 1)

        if isolate_factors[column] in unique_entries:
            unique_factors[column] = isolate_factors[column]

    return unique_factors

def main():
    parser = argparse.ArgumentParser(description='Process isolate resistance/virulence information.')
    parser.add_argument('file', type=str, help='Path to the input TSV file')
    parser.add_argument('isolate', type=str, help='Isolate of interest')

    args = parser.parse_args()

    file_type = os.path.basename(args.file).split('.')[0]  # Extract file type (resistome or virulome)
    file_type = file_type.capitalize()  # Capitalize the file type for printing

    print(f"Reading data from file: {args.file}")
    header, data = read_file(args.file)

    print(f"Finding {file_type.lower()} for isolate: {args.isolate}")
    isolate_factors = get_isolate_factors(header, data, args.isolate)
    if not isolate_factors:
        print(f"No {file_type.lower()} found for isolate: {args.isolate}")
    else:
        print(f"All {file_type.lower()} for isolate {args.isolate}:")
        for column, factor in isolate_factors.items():
            print(f"  {column}: {factor}")

    print("---")
    print(f"Checking for unique {file_type.lower()} for isolate: {args.isolate}")
    unique_factors = get_unique_factors(header, data, args.isolate)
    if not unique_factors:
        print(f"No unique {file_type.lower()} for isolate: {args.isolate}")
    else:
        print(f"Unique {file_type.lower()} for isolate {args.isolate}:")
        unique_factor_names = [f"{column}: {factor}" for column, factor in unique_factors.items()]
        print(f"{file_type}: {', '.join(unique_factor_names)}")
        for column, factor in unique_factors.items():
            print(f"  {column}: {factor}")

if __name__ == "__main__":
    main()
