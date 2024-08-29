import pandas as pd
import argparse

def merge_csv_files(dates_machines_file, salmonella_counts_file, output_file):
    # Read the CSV files
    dates_machines_df = pd.read_csv(dates_machines_file)
    salmonella_counts_df = pd.read_csv(salmonella_counts_file)

    # Merge the dataframes on 'RUN_ID', using outer join to include all RUN_IDs
    merged_df = pd.merge(dates_machines_df, salmonella_counts_df, on='RUN_ID', how='outer')

    # Write the merged dataframe to the output CSV file
    merged_df.to_csv(output_file, index=False)

    print(f"Merged CSV file has been written to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Merge two CSV files by RUN_ID, leaving columns blank for missing RUN_IDs.")
    parser.add_argument('dates_machines_file', type=str, help="Path to the 2223_dates_machines.csv file.")
    parser.add_argument('salmonella_counts_file', type=str, help="Path to the salmonella_counts-2223.csv file.")
    parser.add_argument('output_file', type=str, help="Path to the output merged CSV file.")

    args = parser.parse_args()

    merge_csv_files(args.dates_machines_file, args.salmonella_counts_file, args.output_file)

if __name__ == "__main__":
    main()