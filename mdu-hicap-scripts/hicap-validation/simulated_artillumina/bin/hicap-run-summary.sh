#!/bin/bash

# Generate .tsv files for samples that didn't have any hits
# This is necessary because the hicap command doesn't generate a .tsv file if there are no hits
# This will cause the hicap_summary.tab file to be missing some samples


# Check if the correct number of arguments is provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <fasta_directory>"
    echo "++++++++++"
    echo "Make sure to: "
    echo "conda activate hicap_dev" 
    echo "before running the script."
    echo "++++++++++"
    exit 1
fi

# Get the start time
start_time=$(date +%s)

## Run the hicap command
mkdir -p hicap_results
parallel hicap --query_fp {} --output_dir hicap_results/ ::: $1/*.fa

ls $1 > fasta_files.txt

while read sample_id; do
    sample_id_tsv=${sample_id/.fa/.tsv}
    file_path="hicap_results/${sample_id_tsv}"
    if [[ ! -f "$file_path" ]]; then
        # The file doesn't exist, generate sample_id.tsv
        echo -e "#isolate\tpredicted_serotype\tattributes\tgenes_identified\tlocus_location\tregion_I_genes\tregion_II_genes\tregion_III_genes\tIS1016_hits" > "$file_path"
        echo -e "${sample_id_tsv/.tsv}\tno hits to any cap locus gene found\tno hits to any cap locus gene found\tno hits to any cap locus gene found\tno hits to any cap locus gene found\tno hits to any cap locus gene found\tno hits to any cap locus gene found\tno hits to any cap locus gene found\tno hits to any cap locus gene found" >> "$file_path"
    fi
done < "fasta_files.txt"

# Combine the hicap_results
summary_fps=(hicap_results/*tsv);
{ head -n1 "${summary_fps[0]}"; sed '/^#/d' "${summary_fps[@]}"; } > hicap_summary.tab

# Convert tsv to csv
sed '1s/^#//' hicap_summary.tab | csvtk tab2csv > hicap_summary.csv

# Get the end time
end_time=$(date +%s)

# Calculate the time elapsed
time_elapsed=$((end_time - start_time))

echo "Time elapsed: $time_elapsed seconds"

# Print a success message
echo "Run ended"