#!/usr/bin/env python3

import argparse
import csv

def read_file(file_path):
    """Reads the TSV file and returns header and data."""
    with open(file_path, newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter='\t')
        header = next(reader)
        data = [row for row in reader]
    return header, data

def get_isolate_plasmids(header, data, isolate):
    """Returns plasmids for the specified isolate as a dictionary."""
    isolate_row = next((row for row in data if row[0] == isolate), None)
    if isolate_row:
        plasmids = {header[i]: isolate_row[i] for i in range(1, len(header)) if isolate_row[i]}
        return plasmids
    else:
        return {}

def get_unique_plasmids(header, data, isolate):
    """Finds and returns unique plasmids for the specified isolate."""
    isolate_plasmids = get_isolate_plasmids(header, data, isolate)
    unique_plasmids = {}
    
    for column in isolate_plasmids:
        column_index = header.index(column)
        non_empty_entries = [row[column_index] for row in data if row[column_index].startswith("Contig")]

        if len(non_empty_entries) == 1:
            unique_plasmids[column] = isolate_plasmids[column]

    return unique_plasmids


    return unique_plasmids

def main():
    parser = argparse.ArgumentParser(description='Process isolate plasmid information.')
    parser.add_argument('file', type=str, help='Path to the input TSV file')
    parser.add_argument('isolate', type=str, help='Isolate of interest')

    args = parser.parse_args()

    print(f"Reading data from file: {args.file}")
    header, data = read_file(args.file)

    print(f"Finding plasmids for isolate: {args.isolate}")
    isolate_plasmids = get_isolate_plasmids(header, data, args.isolate)
    if not isolate_plasmids:
        print(f"No plasmids found for isolate: {args.isolate}")
    else:
        print(f"All plasmids for isolate {args.isolate}:")
        for column, plasmid in isolate_plasmids.items():
            print(f"  {column}: {plasmid}")

    print("---")
    print(f"Checking for unique plasmids for isolate: {args.isolate}")
    unique_plasmids = get_unique_plasmids(header, data, args.isolate)
    if not unique_plasmids:
        print(f"No unique plasmids for isolate: {args.isolate}")
    else:
        print(f"Unique plasmids for isolate {args.isolate}:")
        unique_plasmid_names = list(unique_plasmids.keys())
        print(f"Plasmids: {', '.join(unique_plasmid_names)}")
        for column, plasmid in unique_plasmids.items():
            print(f"  {column}: {plasmid}")

if __name__ == "__main__":
    main()
