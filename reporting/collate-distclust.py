#!/usr/bin/env python3
import argparse
import pandas as pd
import sys

def main():
    parser = argparse.ArgumentParser(description="Collate four CSV files into an Excel sheet.")
    parser.add_argument('-s', '--snps-distance', type=str, default='report.snps/distances.tab', help='Path to the SNPs distances CSV file (default: report.snps/distances.tab)')
    parser.add_argument('-g', '--gubbins-distance', type=str, default='report.gubbins/distances.tab', help='Path to the Gubbins distances CSV file (default: report.gubbins/distances.tab)')
    parser.add_argument('-c', '--clust-default', type=str, default='clusters_default.csv', help='Path to the default clusters CSV file (default: clusters_default.csv)')
    parser.add_argument('-u', '--clust-gubbins', type=str, default='clusters_gubbins.csv', help='Path to the Gubbins clusters CSV file (default: clusters_gubbins.csv)')
    parser.add_argument('-o', '--output', type=str, default='summary_distclust.xlsx', help='Name of the output Excel file (default: summary_distclust.xlsx)')
    parser.add_argument('-p', '--prefix', type=str, help='Optional prefix to add to the output file name')

    # If no arguments are provided, display the help message
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    # Load the CSV files into dataframes
    df_snps = pd.read_csv(args.snps_distance, sep='\t')
    df_gubbins = pd.read_csv(args.gubbins_distance, sep='\t')
    df_clust_default = pd.read_csv(args.clust_default)
    df_clust_gubbins = pd.read_csv(args.clust_gubbins)

    # Create a writer object for the Excel file
    output_file = args.output
    if args.prefix:
        output_file = f"{args.prefix}_{output_file}"
        
    with pd.ExcelWriter(output_file) as writer:
        df_snps.to_excel(writer, sheet_name='SNPs Distance', index=False)
        df_clust_default.to_excel(writer, sheet_name='Clusters Default', index=False)
        df_gubbins.to_excel(writer, sheet_name='Gubbins Distance', index=False)
        df_clust_gubbins.to_excel(writer, sheet_name='Clusters Gubbins', index=False)

if __name__ == "__main__":
    main()

