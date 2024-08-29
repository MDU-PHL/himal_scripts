#!/usr/bin/env nextflow
nextflow.enable.dsl=2
version = '1.0'


process RUN_SNIPPY {
    tag { isolate }
    
    publishDir "${params.output_dir}/${run_id}/${isolate}", mode: 'copy'
    
    // conda (params.enable_conda ? '/home/mdu/conda/envs/bohra-snippy' : null)

    conda params.conda_env
    
    // Add resource management
    cpus 64
    memory '32 GB'
    time '12 h'
    
    input:
    tuple val(isolate), val(run_id), val(read1), val(read2)

    output:
    tuple val(isolate), val(run_id), path("snippy")

    script:
    """
    echo "PATH: $PATH"
    echo "Conda env: $CONDA_DEFAULT_ENV"
    which snippy || echo "snippy not found in PATH"
    snippy --version || echo "snippy command failed"
    echo "Running Snippy for isolate: ${isolate}, run_id: ${run_id}"
    snippy  --cpus ${task.cpus} --outdir snippy --ref ${params.ref} --R1 ${read1} --R2 ${read2}
    """
}

process CALCULATE_INSERT_SIZE {
    tag { isolate }
    
    publishDir "${params.output_dir}/${run_id}/${isolate}", mode: 'copy'
    
    // conda (params.enable_conda ? '/home/mdu/conda/envs/bohra-snippy' : null)
    
    conda params.conda_env

    cpus 8
    memory '8 GB'
    time '30 m'

    input:
    tuple val(isolate), val(run_id), path(snippy_dir)

    output:
    tuple val(isolate), val(run_id), path("${isolate}_${run_id}_insert_size.tab")

    script:
    """
    echo "Calculating insert size for isolate: ${isolate}, run_id: ${run_id}"
    samtools stats ${snippy_dir}/snps.bam | grep 'insert size average' | cut -f 3 > ${isolate}_${run_id}_insert_size.tab
    """
}

process COLLATE_INSERT_SIZES {
    publishDir params.output_dir, mode: 'copy'

    input:
    path insert_size_files

    output:
    path "average_insert_size.tab"

    script:
    """
    echo "Collating insert sizes"
    echo -e "ISOLATE\tRUN_ID\tAVERAGE_INSERT_SIZE" > average_insert_size.tab
    for file in ${insert_size_files}; do
        filename=\$(basename \$file)
        isolate=\$(echo \$filename | cut -d'_' -f1)
        run_id=\$(echo \$filename | cut -d'_' -f2)
        avg_size=\$(cat \$file)
        echo -e "\${isolate}\t\${run_id}\t\${avg_size}" >> average_insert_size.tab
    done
    """
}

workflow {
    isolate_runid_ch = Channel.fromPath(params.isolate_runid)
        .splitCsv(header: true, sep: '\t')
        .map { row -> tuple(row.ISOLATE, row.RUN_ID) }

    reads_info_ch = Channel.fromPath(params.reads_info)
        .splitCsv(header: false, sep: '\t')
        .map { row -> tuple(row[0], row[1], row[2], row[3]) }

    run_snippy_ch = isolate_runid_ch.join(reads_info_ch)

    snippy_results = RUN_SNIPPY(run_snippy_ch)

    insert_sizes = CALCULATE_INSERT_SIZE(snippy_results)

    COLLATE_INSERT_SIZES(insert_sizes.map { it -> it[2] }.collect())
}

