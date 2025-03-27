#!/usr/bin/env nextflow
nextflow.enable.dsl=2
version = '1.0'

// download genomes and run MLST
// takes accession numbers from a file and downloads the genomes using ncbi-datasets
// runs MLST on the downloaded genomes

process DOWNLOAD_GENOME {
    tag { "${accession}" }
    
    publishDir "${params.output_dir}", mode: 'copy', pattern: "genomes/${accession}/*"
    
    conda '/home/mdu/conda/envs/ncbi_datasets'
    
    cpus 1
    memory '4 GB'
    time '1 h'
    
    errorStrategy { sleep(Math.pow(2, task.attempt) * 200 as long); return 'retry' }
    maxRetries 3
    
    input:
    val(accession)

    output:
    tuple val(accession), path("genomes/${accession}/*{fna,fna.gz}"), emit: genome_file
    
    script:
    """
    # Download the genome
    datasets download genome accession ${accession} --no-progressbar
    
    # Unzip and organize
    unzip -q ncbi_dataset.zip -d ${accession}
    
    # Create directory structure
    mkdir -p genomes/${accession}
    
    # Copy genome files
    cp ${accession}/ncbi_dataset/data/*/* genomes/${accession}/
       
    # Cleanup temporary files
    rm -rf ${accession} ncbi_dataset.zip
    """
}

process RUN_MLST {
    tag { "${accession}" }
    
    publishDir "${params.output_dir}/mlst", mode: 'copy'
    
    conda params.mlst_conda_env
    
    cpus 1
    memory '4 GB'
    time '1 h'
    
    errorStrategy 'retry'
    maxRetries 3
    
    input:
    tuple val(accession), path(genome_file)

    output:
    tuple val(accession), path("${accession}_mlst.tab")

    script:
    """
    # Handle both compressed and uncompressed files
    if [[ "${genome_file}" == *.gz ]]; then
        # For compressed files
        gunzip -c ${genome_file} > input.fna
    else
        # For uncompressed files
        cp ${genome_file} input.fna
    fi
    
    # Run MLST on the prepared input file
    mlst --quiet --blastdb "${params.mlst_blastdb}" --datadir "${params.mlst_datadir}" \
         --nopath input.fna --exclude ecoli > tmp.tab
    
    # Process the output file
    sed 's/input.fna/${accession}/g' tmp.tab > ${accession}_mlst.tab
    
    # Cleanup
    rm tmp.tab input.fna
    """
}

process COMBINE_MLST_RESULTS {
    publishDir "${params.output_dir}", mode: 'copy'
    
    input:
    path(mlst_files)
    
    output:
    path("combined_mlst_results.tsv")
    
    script:
    """
    # Create header
    echo -e "sample\tscheme\tST\tloci1\tloci2\tloci3\tloci4\tloci5\tloci6\tloci7" > combined_mlst_results.tsv
    
    # Combine all files without headers
    for file in ${mlst_files}; do
        cat \$file >> combined_mlst_results.tsv
    done
    """
}

workflow {
    // Read accessions from the file
    accessions = Channel
        .fromPath('unique_accession_italy.txt')
        .splitText()
        .map { it.trim() }
        .filter { it.length() > 0 }
    
    // Download genomes
    download_results = DOWNLOAD_GENOME(accessions)
    
    // Run MLST on downloaded genomes
    mlst_results = RUN_MLST(download_results.genome_file)
    
    // Combine all MLST results
    COMBINE_MLST_RESULTS(mlst_results.map { it[1] }.collect())
}