#!/bin/bash

# This script will take a sample ID and run hicap typing on the corresponding fasta file
sample_file=$1

# Check if no arguments are passed
if [[ -z $sample_file ]]; then
    echo "Usage: $0 <sample_IDs_file>"
    echo "++++++++++"
    echo "Make sure to: "
    echo "conda activate /home/himals/.conda/envs/hicap_dev/" 
    echo "before running the script."
    echo "++++++++++"
    exit 1
fi

# Create the fasta_files directory if it doesn't exist
mkdir -p fasta_files

# Loop through the list of sample IDs in the file 
while read sample_id; do
    # Get the path to the FASTA file
    fasta_path=$(mdu contigs --sample_id "$sample_id" | awk '{print $2}')
    
    # Copy the FASTA file to the fasta_files directory with the sample ID name
    cp "$fasta_path" "fasta_files/$sample_id.fasta"
done < "$sample_file"

# Run hicap typing on the FASTA files
mkdir -p output

# Execute the command for each FASTA file
parallel hicap --query_fp {} --output_dir output/ ::: fasta_files/*fasta

# Generate .tsv files for samples that didn't have any hits
# This is necessary because the hicap command doesn't generate a .tsv file if there are no hits
# This will cause the hicap_summary.tab file to be missing some samples
while read sample_id; do
    file_path="output/${sample_id}.tsv"
    if [[ ! -f "$file_path" ]]; then
        # The file doesn't exist, generate sample_id.tsv
        echo -e "#isolate\tpredicted_serotype\tattributes\tgenes_identified\tlocus_location\tregion_I_genes\tregion_II_genes\tregion_III_genes\tIS1016_hits" > "$file_path"
        echo -e "${sample_id}\tno hits to any cap locus gene found\tno hits to any cap locus gene found\tno hits to any cap locus gene found\tno hits to any cap locus gene found\tno hits to any cap locus gene found\tno hits to any cap locus gene found\tno hits to any cap locus gene found\tno hits to any cap locus gene found" >> "$file_path"
    fi
done < "$sample_file"

# Combine the output
summary_fps=(output/*tsv);
{ head -n1 "${summary_fps[0]}"; sed '/^#/d' "${summary_fps[@]}"; } > hicap_summary.tab

# Convert tsv to csv
sed '1s/^#//' hicap_summary.tab | csvtk tab2csv > hicap_summary.csv