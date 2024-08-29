import os
import argparse
from datetime import datetime

def find_directories(base_path, months, output_file):
    # List to store matching directories
    matching_dirs = []

    # Convert month names to month numbers
    month_numbers = {datetime.strptime(month, "%B").month for month in months}

    # Iterate through the directories in the base path
    for entry in os.scandir(base_path):
        if entry.is_dir():
            # Get the modification time of the directory
            mod_time = datetime.fromtimestamp(entry.stat().st_mtime)
            if mod_time.month in month_numbers:
                matching_dirs.append(entry.name)

    # Write the matching directories to the output file
    with open(output_file, 'w') as file:
        for dir_name in matching_dirs:
            file.write(f"{dir_name}\n")

    print(f"Matching directories have been written to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Find directories dated in specified months within a directory path.")
    parser.add_argument('base_path', type=str, help="The base directory path to search within.")
    parser.add_argument('--months', type=str, nargs='+', default=['June', 'July'], help="The months to search for in directory modification dates.")
    parser.add_argument('--output', type=str, default='dir_<dates>.txt', help="The output file to write the results to.")

    args = parser.parse_args()

    print(f"Searching for directories in {args.base_path} modified in {', '.join(args.months)}...")
    find_directories(args.base_path, args.months, args.output)
    print("Search completed.")

if __name__ == "__main__":
    main()