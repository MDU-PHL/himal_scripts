import argparse
import subprocess
import csv
import re
from datetime import datetime
from tqdm import tqdm

def get_sequence_info(run_id):
    try:
        # Run the command and capture the output
        result = subprocess.run(['mdu', 'qcjob', '-j', run_id], capture_output=True, text=True)
        output = result.stdout

        # Extract the sequence path from the output
        match = re.search(r'which is/was running in (.+)', output)
        if match:
            sequence_path = match.group(1)
            # Extract the sequencer and date from the path
            path_parts = sequence_path.split('/')
            sequencer = path_parts[4]
            date_str = path_parts[5][:6]
            date = datetime.strptime(date_str, '%y%m%d').strftime('%b %d %Y')
            return run_id, sequence_path, sequencer, date
        else:
            print(f"Run ID {run_id} not found in the output.")
            return run_id, None, None, None
    except Exception as e:
        print(f"Error processing run ID {run_id}: {e}")
        return run_id, None, None, None

def main():
    parser = argparse.ArgumentParser(description="Process run IDs and create a CSV file with sequencing information.")
    parser.add_argument('run_ids_file', type=str, help="Path to the run_ids.txt file.")
    parser.add_argument('output_csv', type=str, help="Path to the output CSV file.")

    args = parser.parse_args()

    # Read the run IDs from the file
    with open(args.run_ids_file, 'r') as file:
        run_ids = [line.strip() for line in file]

    # Prepare the results list
    results = []

    print("Processing run IDs...")
    # Process each run ID with a progress bar
    for run_id in tqdm(run_ids, desc="Processing"):
        info = get_sequence_info(run_id)
        if info[1] is not None:
            results.append(info)

    # Write the results to the CSV file
    with open(args.output_csv, 'w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(['RUN_ID', 'sequence_path', 'sequencer', 'date'])
        writer.writerows(results)

    print(f"Results have been written to {args.output_csv}")

if __name__ == "__main__":
    main()