# International CPO Investigation Guide

 This guide outlines a systematic approach to investigate potential international transmission events using genomic epidemiology.

## Setup and Data Collection

1. **Identify target CPO genes and sequence types**
   - Navigate to [NCBI Pathogen Detection Portal](https://www.ncbi.nlm.nih.gov/pathogens/)
   - Search for your pathogen of interest
   - Apply filters: Select CPO genes → Choose locations
   - Download genome accession numbers as a text file 

Note: This guide was prepared while investigating *Klebsiella pneumoniae* carrying KPC-3 gene. You may find file name references specific to this investigation. You can simply replace these with your own file names depending on your pathogen of interest.

2. **Download genome sequences**
   ```sh
   ca ncbi_datasets
   
   # Create accession list file
   nano accession_kpc3_pathogen_detection.txt
   
   # Download genomes in dehydrated format
   datasets download genome accession --dehydrated --inputfile accession_kpc3_pathogen_detection.txt --include genome 
   
   # Extract and rehydrate
   unzip ncbi_dataset.zip -d kpneumo_kpc3_pathogen_detection
   datasets rehydrate --directory kpneumo_kpc3_pathogen_detection
   ```

3. **Extract metadata**
   ```sh
   # Convert JSONL metadata to CSV
   python json_to_csv.py \
     kpneumo_kpc3_pathogen_detection/ncbi_dataset/data/assembly_data_report.jsonl \
     kpneumo_kpc3_pathogen_detection.csv
   
   # Verify data
   wc -l kpneumo_kpc3_pathogen_detection.csv
   csvtk pretty kpneumo_kpc3_pathogen_detection.csv | head -n 5
   ```

## Sequence Analysis

4. **Run MLST analysis**
   ```sh
   ca nextflow
   nextflow run nextflow_mlst.nf -resume
   
   # Check results
   csvtk -t pretty results/combined_mlst_results.tsv
   ```

5. **Filter isolates by sequence type**
   ```sh
   # Replace 101 with your ST of interest
   python filter_mlst_by_st.py --input combined_mlst_results.tsv --st 101
   # Output will be saved as ST_101_mlst_results.tsv
   ```

## Phylogenetic Analysis

6. **Prepare for mashtree analysis**
   ```sh
   mkdir mashtree_analysis
   
   # Prepare NCBI samples
   python prepare_mash_contigs_list.py \
     -i results/ST_101_mlst_results.tsv \
     -o mashtree_analysis/contigs_list.txt \
     -p kpneumo_kpc3_pathogen_detection/ncbi_dataset/data
   ```

7. **Add MDU samples (if applicable)**
   ```sh
   # Create list of MDU IDs
   nano mashtree_analysis/ids.txt
   
   # Get contigs for MDU samples
   mdu contigs --idfile mashtree_analysis/ids.txt -a shovill > mashtree_analysis/contigs.tab
   
   # Copy contigs to analysis directory
   python copy_contigs.py -i mashtree_analysis/contigs.tab -o mashtree_analysis --extension .fa --verbose 
   
   # Add MDU contigs to list
   ls mashtree_analysis/*fa >> mashtree_analysis/contigs_list.txt
   
   # Verify total number of samples
   wc -l mashtree_analysis/contigs_list.txt
   ```

8. **Run mashtree analysis**
   ```sh
   ca /home/bisognor/.conda/envs/mashtree
   
   # Adjust genome size as needed for your organism
   mashtree --file-of-files contigs_list.txt --genomesize 5500000 --outmatrix matrix.tab --outtree tree.dnd
   ```

## Visualization and Interpretation

9. **Generate ASCII tree visualization**
   The script generates an ASCII tree visualization of the phylogenetic tree. This can be useful for quick visualization in the terminal and for copying sample IDs for further analysis. 
   ```sh
   python /home/himals/3_resources/github-repos/himal_scripts/bohra/ascii_tree.py \
     -f mashtree_analysis/tree_kpc3_pathogen_detection.dnd
   ```

10. **Filter metadata and identify closest genomes using mash-distance matrix**
    First, filter the metadata to include only the genomes in the matrix. Information for the MDU isolates need to be manually added to the metadata file before running the `analyze_mash.py` script.
    ```sh
    # Filter metadata for genomes in analysis
    python filter_metadata.py \
      -c mashtree_analysis/contigs_list_kpc3_pathogen_detection.txt \
      -m kpneumo_kpc3_pathogen_detection.csv \
      -o mashtree_analysis/filtered_kpneumo_kpc3_pathogen_detection.csv
    
    # Manually add metadata for MDU samples to the filtered metadata file

    # Find closest genomes to query sample
    # Replace <sample-id> with your sample of interest
    python /home/himals/3_resources/github-repos/himal_scripts/bohra/analyze_mash.py \
      -m mashtree_analysis/matrix_kpc3_pathogen_detection.tab \
      --query <sample-id> \
      --metadata mashtree_analysis/filtered_kpneumo_kpc3_pathogen_detection.csv \
      --columns geoLocName
    ```

11. **Generate better-quality tree using `ggtree`**
    ```sh
    ca my_renv
    
    # Replace <sample-id,sample-id2..> with your samples of interest
    Rscript /home/himals/3_resources/github-repos/himal_scripts/bohra/ggtree_annotate.R \
      -i tree_kpc3_pathogen_detection.dnd \
      -f <sample-id,sample-id2..> \
      -o phylo_tree_kpc3_pathogen_detection_annotated.png \
      -a filtered_kpneumo_kpc3_pathogen_detection.csv \
      -c country --align --color_column country --match_column filename
    ```

12. **Summarize findings for reporting**
    - Identify the closest genomic matches to your query isolate
    - Note the geographic distribution of related isolates
    - Determine potential transmission patterns based on phylogeny

Happy investigating! 🕵️‍♂️
