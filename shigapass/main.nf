#!/usr/bin/env nextflow
nextflow.enable.dsl=2
version = '1.0'

process SETUP_DIRECTORIES {
    tag { "${genome_id}" }
    
    input:
    tuple val(genome_id), path(contig_path)
    
    output:
    tuple val(genome_id), path("${genome_id}/${genome_id}_contigs.txt"), path("${genome_id}/${genome_id}.fa")
    
    script:
    """
    mkdir -p ${genome_id}
    cp ${contig_path} ${genome_id}/${genome_id}.fa
    echo "${genome_id}.fa" > ${genome_id}/${genome_id}_contigs.txt
    """
}

process RUN_SHIGAPASS {
    tag { "${genome_id}" }
    
    // publishDir "${params.output_dir}", mode: 'copy', overwrite: true
    
    conda params.conda_env
    
    cpus 1
    memory '4 GB'
    time '2 h'
    
    // errorStrategy 'retry'
    // maxRetries 1
    
    input:
    tuple val(genome_id), path(contig_list), path(contig_file)
    
    script:
    """
    # Create output directory first
    mkdir -p ${params.output_dir}/${genome_id}

    /home/himals/3_resources/tools/shigapass/ShigaPass/SCRIPT/ShigaPass.sh \
        -l ${contig_list} \
        -o ${params.output_dir}/${genome_id} \
        -p /home/himals/3_resources/tools/shigapass/ShigaPass/SCRIPT/ShigaPass_DataBases
    """
}

workflow {
    // Create channel from input contigs file
    Channel
        .fromPath(params.contigs_file)
        .splitCsv(sep: '\t')
        .map { row -> tuple(row[0], file(row[1])) }
        .set { contigs_ch }
    
    // Setup directories and contig list files
    setup_results = SETUP_DIRECTORIES(contigs_ch)
    
    // Run ShigaPass
    RUN_SHIGAPASS(setup_results)
}