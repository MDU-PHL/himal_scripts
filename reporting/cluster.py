#!/usr/bin/env python3
import argparse
from sklearn.cluster import AgglomerativeClustering
import pandas as pd
import numpy as np
import sys

def main():
    parser = argparse.ArgumentParser(description="Cluster sequences based on distance matrix.")
    parser.add_argument('--distances', type=str, default='report/distances.tab', help='Path to the distances.tab file (default: report/distances.tab)')
    parser.add_argument('--thresholds', type=str, default='1,2,5,10,20', help='Comma-separated list of distance thresholds for clustering (default: 1,2,5,10,20)')
    parser.add_argument('--output', type=str, default='clusters.csv', help='Name of the output CSV file (default: clusters.csv)')

    # If no arguments are provided, display the help message
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    # Parse the thresholds into a list of integers
    thresholds = list(map(int, args.thresholds.split(',')))

    mat = []
    isos = []

    with open(args.distances, 'r') as f:
        lines = f.read().strip().split('\n')
        for line in lines[1:]:
            row = line.split('\t')[1:]
            isos.append(line.split('\t')[0])
            mat.append(row)

    result = pd.DataFrame()
    X = np.array(mat, dtype=object)

    for n in thresholds:
        clustering = AgglomerativeClustering(n_clusters=None, metric='precomputed', linkage='single', distance_threshold=n).fit(X)
        df = pd.DataFrame(data={'Seq_ID': isos, f'Tx:{n}': clustering.labels_})
        if result.empty:
            result = df
        else:
            result = result.merge(df)

    result.to_csv(args.output, index=False)

if __name__ == "__main__":
    main()
