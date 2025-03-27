# Step-by-Step Guide for CPO Mob Typer Analysis

## Purpose
This analysis identifies and characterises mobile genetic elements associated with carbapenemase-producing organism (CPO) isolates, helping to understand transmission and resistance mechanisms.

## Step 1: Create Contigs Table
```sh
# Create a file with your isolate IDs
nano ids.txt
# Paste your isolate IDs (one per line)

# Generate contigs table using MDU database
mdu contigs --idfile ids.txt -a shovill > contigs.tab
```

## Step 2: Collate AMR Gene Information

```sh
# Run the collation script to extract AMR gene information
# Replace 'ndm' with your target CPO gene (e.g., kpc, oxa-48, vim)
python collate_amrfinder.py -c contigs.tab -g ndm -o output_directory
```
*This step extracts AMRfinder results for isolates containing your target gene and saves the output in the specified directory.*
Generates two files: 
- `amrfinder.out.collated`: Collated AMR gene information 
- `amrfinder.tab`: similar to `contigs.tab` but with path to AMRfinder output file to each sample 

## Step 3: Prepare Mob Typer Input
```sh
# Examine the collated AMRfinder output
csvtk -t pretty output_directory/amrfinder.out.collated

# Map AMR gene information to contig files
# This creates the input table needed for the mob_typer pipeline
python map_abritamr_contigs.py \
    -a output_directory/amrfinder.out.collated \
    -c contigs.tab \
    -o NDM-1_abritamr_contig_info.tab
```
*This step links AMR gene information with the corresponding contig files, creating a mapping table for the nextflow pipeline.*

## Step 4: Run Mob Typer Pipeline
```sh
# Activate nextflow environment
ca nextflow

# Run the mob_typer pipeline
nextflow run main.nf -resume
```
*This pipeline:*
- *Extracts contigs containing the target resistance genes*
- *Analyzes these contigs with mob_typer to identify plasmid characteristics*
- *Compiles results into summary files*

## Step 5: Examine Results
```sh
# View the mob_typer summary results
# Replace <gene> with your target gene name (e.g., NDM-1)
csvtk pretty results/<gene>_mobtyper_summary.csv
```
*The summary provides details on:*
- *Plasmid incompatibility types*
- *Mobility classifications*
- *Relaxase types*
- *Mating pair formation systems*
- *Host range predictions*

## Interpretation Tips
- **Inc types**: Identifies plasmid incompatibility groups (indicates which plasmids cannot co-exist)
- **Mobility**: Indicates whether the plasmid is conjugative, mobilizable, or non-mobilizable
- **MPF type**: Mating pair formation system (T4SS type)
- **Host range**: Predicted bacterial species range capable of maintaining the plasmid

## Next Steps
- Compare plasmid types across isolates from different sources/locations
- Identify predominant plasmid types carrying specific CPO genes
- Correlate with epidemiological data to track transmission events

Happy investigating! 🧬🔍