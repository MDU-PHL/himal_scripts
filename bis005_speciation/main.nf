#!/usr/bin/env nextflow
nextflow.enable.dsl=2

process CHECK_DATABASES {
    
    output:
    stdout
    
    script:
    """
    # Check if databases exist
    if [ ! -d "${params.gtdb_db}" ]; then
        echo "ERROR: GTDB database not found at ${params.gtdb_db}. Please make sure the database is in the correct path."
        exit 1
    fi
    
    if [ ! -d "${params.pluspf_db}" ]; then
        echo "ERROR: PlusPF database not found at ${params.pluspf_db}. Please make sure the database is in the correct path."
        exit 1
    fi
    
    echo "Databases found successfully"
    """
}

process CHECK_SCRIPTS {
    
    output:
    stdout
    
    script:
    """
    # Check if scripts exist
    if [ ! -f "${params.spekki_report_script}" ]; then
        echo "ERROR: spekki_report.py script not found at ${params.spekki_report_script}. Please make sure the script is in the correct path."
        exit 1
    fi
    
    if [ ! -f "${params.mduify_spekki_script}" ]; then
        echo "ERROR: mduify_spekki.py script not found at ${params.mduify_spekki_script}. Please make sure the script is in the correct path."
        exit 1
    fi
    
    echo "Scripts found successfully"
    """
}

process SETUP_DIRECTORIES {
    tag { "${mdu_id}" }
    
    input:
    tuple val(mdu_id), path(r1), path(r2)
    
    output:
    tuple val(mdu_id), path(r1), path(r2), path("${mdu_id}")
    
    script:
    """
    mkdir -p ${mdu_id}
    """
}

process KRAKEN2_GTDB {
    tag { "${mdu_id}" }
    
    publishDir "${params.output_dir}", mode: 'copy', overwrite: true
    
    conda params.kraken2_env
    
    cpus 16
    memory '8 GB'
    time '2 h'
    
    input:
    tuple val(mdu_id), path(r1), path(r2), path(sample_dir)
    
    output:
    tuple val(mdu_id), path(sample_dir), path("${sample_dir}/kraken2_gtdb.tab")
    
    script:
    """
    kraken2 --paired ${r1} ${r2} --threads ${task.cpus} --report ${sample_dir}/kraken2_gtdb.tab --output - --memory-mapping --db ${params.gtdb_db} 2> /dev/null
    """
}

process KRAKEN2_PLUSPF {
    tag { "${mdu_id}" }
    
    publishDir "${params.output_dir}", mode: 'copy', overwrite: true
    
    conda params.kraken2_env
    
    cpus 16
    memory '8 GB'
    time '2 h'
    
    input:
    tuple val(mdu_id), path(r1), path(r2), path(sample_dir)
    
    output:
    tuple val(mdu_id), path(sample_dir), path("${sample_dir}/kraken2_pluspf.tab")
    
    script:
    """
    kraken2 --paired ${r1} ${r2} --threads ${task.cpus} --report ${sample_dir}/kraken2_pluspf.tab --output - --memory-mapping --db ${params.pluspf_db} 2> /dev/null
    """
}

process RUN_SPEKKI {
    tag { "${mdu_id}" }
    
    publishDir "${params.output_dir}", mode: 'copy', overwrite: true
    
    conda params.spekki_env
    
    cpus 1
    memory '4 GB'
    time '1 h'
    
    input:
    tuple val(mdu_id), path(sample_dir), path(gtdb_report), path(pluspf_report)
    
    output:
    tuple val(mdu_id), path(sample_dir), path("${sample_dir}/spekki.tab")
    
    script:
    """
    cd ${sample_dir}
    mdu-spekki ${mdu_id} --pluspf_kraken2 kraken2_pluspf.tab --kgtdb_kraken2 kraken2_gtdb.tab > spekki.tab
    """
}

process SPEKKI_REPORT {
    tag { "${mdu_id}" }
    
    publishDir "${params.output_dir}", mode: 'copy', overwrite: true
    
    conda params.spekki_env
    
    cpus 1
    memory '2 GB'
    time '30 min'
    
    input:
    tuple val(mdu_id), path(sample_dir), path(spekki_tab)
    
    output:
    tuple val(mdu_id), path("${sample_dir}/spekki_report.csv")
    
    script:
    """
    cd ${sample_dir}
    ${params.spekki_report_script} -s spekki.tab
    """
}

process MDUIFY_SPEKKI {
    tag { "MDUIFY_${params.run_id}" }
    
    publishDir "${params.output_dir}", mode: 'copy', overwrite: true
    
    conda params.mdudatagen_env
    
    cpus 1
    memory '4 GB'
    time '30 min'
    
    input:
    tuple val(group_id), path(files, stageAs: "?/*")
    
    output:
    path("${params.run_id}_speciation.xlsx")
    
    script:
    """
    # Debug - check what's available
    echo "Files in working directory:"
    find . -type f | sort
    
    ${params.mduify_spekki_script} --input_files */spekki_report.csv --runid ${params.run_id}
    """
}

workflow {
    // Check databases and scripts exist
    CHECK_DATABASES()
    CHECK_SCRIPTS()
    
    // Create channel from reads file - modified for 3 column format
    Channel
        .fromPath(params.reads_file)
        .splitCsv(sep: '\t')
        .map { row -> 
            // Check if file paths exist and are not null
            def r1_file = row[1] ? file(row[1]) : null
            def r2_file = row[2] ? file(row[2]) : null
            
            if (!r1_file || !r2_file) {
                error "Invalid file paths in reads.tab for ${row[0]}: R1=${row[1]}, R2=${row[2]}"
            }
            
            tuple(row[0], r1_file, r2_file)
        }
        .set { reads_ch }
    
    // Setup directories
    setup_results = SETUP_DIRECTORIES(reads_ch)
    
    // Run Kraken2 with GTDB and PlusPF in parallel
    kraken2_gtdb_results = KRAKEN2_GTDB(setup_results)
    kraken2_pluspf_results = KRAKEN2_PLUSPF(setup_results)
    
    // Combine the results from both Kraken2 processes
    // Join by mdu_id to combine gtdb and pluspf results
    combined_kraken_results = kraken2_gtdb_results
        .join(kraken2_pluspf_results)
        .map { mdu_id, sample_dir1, gtdb_report, sample_dir2, pluspf_report ->
            tuple(mdu_id, sample_dir1, gtdb_report, pluspf_report)
        }
    
    // Run Spekki
    spekki_results = RUN_SPEKKI(combined_kraken_results)
    
    // Generate Spekki report
    spekki_report_results = SPEKKI_REPORT(spekki_results)
    
    // Group results by a single key to pass all files to one process
    spekki_report_results
        .map { mdu_id, report_csv -> 
            // Use a fake grouping key 'all' to collect everything
            return tuple("all", report_csv)
        }
        .groupTuple()
        .set { grouped_results }
    
    // Define MDUIFY_SPEKKI to accept grouped tuple
    MDUIFY_SPEKKI(grouped_results)
}