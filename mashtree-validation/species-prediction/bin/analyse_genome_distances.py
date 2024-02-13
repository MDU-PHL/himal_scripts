"""
analyse_genome_distances.py

Usage:
    python analyse_genome_distances.py <matrix_file> <query_sequence> <output_directory>

Arguments:
    matrix_file: The name of the file containing the genome distance matrix. 
                 This should be a tab-separated file with the first column as the index.
    query_sequence: The name of the query sequence. This should be a row in the matrix file.
    output_directory: The path to the directory where the output CSV file will be saved.

This script reads a genome distance matrix from a file, selects a query sequence, and performs various operations to analyze the distances to other genomes. The operations include selecting the top 10 closest genomes, finding the rank and distance of the seed genome (determined by removing the last part of the query sequence after the last underscore), finding the closest match and its distance, and checking if the species of the seed genome and the closest match are the same. The results are written to a CSV file in the specified output directory.

Example:
    python analyse_genome_distances.py matrix.tab Bacillus_anthracis_HDZK-BYSB7_60 /path/to/output/directory/
"""

import sys
import pandas as pd
import os
import re

if len(sys.argv) != 4:
    print(__doc__)
    sys.exit(1)

# Function to get species from genome name
def get_species(genome):
    return ' '.join(genome.split('_')[:2])

# Input file name, query sequence, and output directory path
matrix_file = sys.argv[1]
query_sequence = sys.argv[2]
output_directory = sys.argv[3]
seed_genome = '_'.join(query_sequence.split('_')[:-1])

# Read the tab separated file as a data frame
df = pd.read_csv(matrix_file, sep="\t", index_col=0)

df.index = df.index.str.strip()

# Select the columns that contain the query sequence
query_df = df.filter(regex=query_sequence)

# sort the query_df in ascending order of the values in the first column
query_df_sorted = query_df.sort_values(by=query_df.columns[0], ascending=True)

# Get a list of all row labels that match the regex
labels_to_drop = [label for label in query_df_sorted.index if re.match(rf'{query_sequence}.*', label)]

# Drop the rows with those labels
query_df_sorted_drop = query_df_sorted.drop(labels_to_drop, axis=0)

# Select the top 10 reference genomes
top_10 = query_df_sorted_drop[:10].index.tolist()

# Get the rank of the seed genome
rank_seed_genome = query_df_sorted_drop.index.tolist().index(seed_genome) + 1

# Get the distance to the seed genome
distance_seed_genome = query_df_sorted_drop.loc[seed_genome].iloc[0]

# Check if distance_seed_genome is NaN
if pd.isna(distance_seed_genome):
    distance_seed_genome = 'NaN computed'

# Get the species of the seed genome
species_seed_genome = get_species(seed_genome)

# Get the closest match
closest_match = query_df_sorted_drop.index[0]

# Get the distance to the closest match
distance_closest_match = query_df_sorted_drop.loc[closest_match].iloc[0]
distance_closest_match

# Check if distance_closest_match is NaN
if pd.isna(distance_closest_match):
    distance_closest_match = 'NaN computed'

# Get the species of the closest match
species_closest_match = get_species(closest_match)

# Check if the species match
check_species_match = 'Yes' if species_seed_genome == species_closest_match else 'No'

# Create a DataFrame for the output
output_df = pd.DataFrame({
    'Query sequence': [query_sequence],
    'Top 10 ranking': [';'.join(top_10)],
    'Rank of the seed genome': [rank_seed_genome],
    'Distance to the seed genome': [distance_seed_genome],
    'Species of the seed genome': [species_seed_genome],
    'Closest match': [closest_match],
    'Distance to the closest match': [distance_closest_match],
    'Species of the closest match': [species_closest_match],
    'check_species_match': [check_species_match]
})


# Write the DataFrame to a CSV file in the specified output directory
output_file = os.path.join(output_directory, f"{query_sequence}_output.csv")
output_df.to_csv(output_file, index=False)
