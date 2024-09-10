import pandas as pd
import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Merge cluster files and create a final clustered file.")
    parser.add_argument('--clust-default', '-c', type=str, default='clusters_default.csv', help='Path to the default clusters CSV file (default: clusters_default.csv)')
    parser.add_argument('--clust-gubbins', '-u', type=str, default='clusters_gubbins.csv', help='Path to the Gubbins clusters CSV file (default: clusters_gubbins.csv)')
    parser.add_argument('--output', '-o', type=str, default='clusters_final.csv', help='Name of the output CSV file (default: clusters_final.csv)')

    args = parser.parse_args()

    # Load the CSV files into dataframes
    df_default = pd.read_csv(args.clust_default)
    df_gubbins = pd.read_csv(args.clust_gubbins)

    # Remove the Reference row
    df_default = df_default[df_default['Seq_ID'] != 'Reference']
    df_gubbins = df_gubbins[df_gubbins['Seq_ID'] != 'Reference']

    # Initialize the final dataframe
    df_final = pd.DataFrame()
    df_final['Seq_ID'] = df_default['Seq_ID']
    df_final['Tx:50'] = df_gubbins['Tx:50']
    df_final['Tx:10'] = df_default['Tx:10']
    
    # Generate SNP-cluster column
    def generate_snp_cluster(row):
        tx50 = row['Tx:50']
        tx10 = row['Tx:10']
        count_tx50 = df_final[df_final['Tx:50'] == tx50].shape[0]
        count_tx10 = df_final[df_final['Tx:10'] == tx10].shape[0]
        tx50_cluster = 'UC' if count_tx50 == 1 else tx50
        tx10_cluster = 'UC' if count_tx10 == 1 else tx10
        return f"{tx50_cluster}.{tx10_cluster}"

    df_final['SNP-cluster (50 SNP. 10 SNP)'] = df_final.apply(generate_snp_cluster, axis=1)

    # Save the final dataframe to a CSV file
    df_final.to_csv(args.output, index=False)

if __name__ == "__main__":
    main()
