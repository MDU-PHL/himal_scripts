import os
import csv
import argparse

"""
This script processes a list of run IDs from a file named 'run-ids.txt'.
For each run ID, it checks for the presence of the string "Salmonella" in a specific CSV file.
If the file is not found, it logs the missing file and records "FileNotFound" as the count.
If there is a permission error, it logs the error and records "PermissionError" as the count.
The results are exported to a CSV file named 'salmonella_counts.csv'.

Steps:
1. Read the run IDs from 'run-ids.txt'.
2. For each run ID, construct the file path based on the year extracted from the run ID.
3. Check if the file exists and count occurrences of "Salmonella".
4. Log any missing files or permission errors.
5. Write the results to 'salmonella_counts.csv'.
"""

# Function to count occurrences of "Salmonella" in a file
def count_salmonella(file_path):
    try:
        with open(file_path, 'r') as file:
            return sum(1 for line in file if 'Salmonella' in line)
    except FileNotFoundError:
        return 'FileNotFound'
    except PermissionError:
        return 'PermissionError'

def main(run_ids_file, report_log_file, output_csv_file):
    # Read the run IDs from the file
    with open(run_ids_file, 'r') as file:
        run_ids = [line.strip() for line in file]

    # Prepare the results list
    results = []

    # Open the report log file
    with open(report_log_file, 'w') as log_file:
        # Process each run ID
        for run_id in run_ids:
            year = run_id[1:5]
            file_path = f'/home/mdu/qc/{year}/{run_id}/standard_bacteria_qc.csv'
            count = count_salmonella(file_path)
            
            if count == 'FileNotFound':
                log_file.write(f'File not found: {file_path}\n')
            elif count == 'PermissionError':
                log_file.write(f'Permission denied: {file_path}\n')
            
            results.append((run_id, count))

    # Write the results to the CSV file
    with open(output_csv_file, 'w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(['RUN_ID', 'Salmonella Count'])
        writer.writerows(results)

    print(f'Results have been written to {output_csv_file}')
    print(f'Report log has been written to {report_log_file}')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process run IDs and count Salmonella occurrences.')
    parser.add_argument('--run_ids_file', type=str, default='run-ids.txt', help='Path to the run-ids.txt file')
    parser.add_argument('--report_log_file', type=str, default='report_log.txt', help='Path to the report log file')
    parser.add_argument('--output_csv_file', type=str, default='salmonella_counts.csv', help='Path to the output CSV file')

    args = parser.parse_args()
    main(args.run_ids_file, args.report_log_file, args.output_csv_file)