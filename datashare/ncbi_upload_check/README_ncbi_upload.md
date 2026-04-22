# ncbi_upload_check.py

> Before you submit thousands of isolate sequences to the NCBI Sequence Read Archive, you need to know which ones are already there, otherwise this will create duplicate records which is not desirable. This script solves that problem: it checks a list of sample IDs against the NCBI BioSample database in parallel, respects the API rate limits.

---

## Table of Contents

1. [Overview](#overview)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Credentials Setup](#credentials-setup)
5. [Quick Start](#quick-start)
6. [Usage Reference](#usage-reference)
7. [Output Files](#output-files)
8. [Rate Limiting Explained](#rate-limiting-explained)
9. [Detailed Mode](#detailed-mode)
10. [Common Issues](#common-issues)

---

## Overview

`ncbi_upload_check.py` queries the [NCBI BioSample](https://www.ncbi.nlm.nih.gov/biosample/)
database to determine whether a list of sample identifiers (e.g. AUSMDU
accessions) have already been deposited.  Key features:

| Feature | Detail |
|---------|--------|
| **Thread-safe rate limiter** | Token-bucket algorithm; never exceeds 3 req/s (anonymous) or 10 req/s (API key) regardless of `--jobs` value |
| **Exponential back-off** | Transient network errors retried up to 5× with doubling delay |
| **XML-based parsing** | Fetches structured XML from Entrez — reliably extracts all metadata fields |
| **Secure credentials** | Email and API key read from environment variables or an INI config file — never from CLI arguments or log files |
| **Progress bar** | `tqdm` progress bar with live found/not-found counters |
| **Detailed mode** | Extended metadata TSV + raw XML records saved per sample |

---

## Requirements

- Python ≥ 3.10
- [`biopython`](https://biopython.org/) — Entrez E-utilities client
- [`tqdm`](https://tqdm.github.io/) — progress bar

All other dependencies (`argparse`, `concurrent.futures`, `xml.etree`, etc.)
are part of the Python standard library.

---

## Installation

```bash
# Create a dedicated environment
conda create -n ncbi-check python=3.11 biopython tqdm -y
conda activate ncbi-check

# Or use the bionf_env conda environment
conda activate /home/himals/.conda/envs/bioinf_env
```

---

## Credentials Setup

> **Security note:** Email and API key are **never** passed as command-line
> arguments.  This prevents them appearing in process listings (`ps aux`),
> shell history, or log files.

Credentials are resolved in this priority order:

### Option 1 : Environment variables (recommended)

Add to your `~/.bashrc` or `~/.bash_profile`:

```bash
export NCBI_EMAIL="you@institution.edu.au"
export NCBI_API_KEY="your_api_key_here"
```

Then reload:

```bash
source ~/.bashrc
```

### Option 2 : INI config file

Create `~/.ncbi_config` (the default path):

```ini
[ncbi]
email   = you@institution.edu.au
api_key = your_api_key_here
```

Restrict file permissions so no other user can read it:

```bash
chmod 600 ~/.ncbi_config
```

Use a non-default config path with `-c`:

```bash
python ncbi_upload_check.py -i ids.txt -c /path/to/my.cfg
```

> **Get a free NCBI API key** at <https://www.ncbi.nlm.nih.gov/account/>  
> An API key raises the rate limit from 3 to 10 requests/second.

---

## Quick Start

```bash
# 1. Set credentials (once, in your shell profile)
export NCBI_EMAIL="you@institution.edu.au"
export NCBI_API_KEY="your_key"

# 2. Run with a small test batch first
head -n 5 ausmdu_ids.txt > sample_test.txt
python ncbi_upload_check.py -i sample_test.txt -o test_results -v

# 3. Full run with API key (10 req/s → cap workers at 10)
python ncbi_upload_check.py -i ausmdu_ids.txt -o ncbi_results -j 10

# 4. Full run with extended metadata for validation document
python ncbi_upload_check.py -i ausmdu_ids.txt -o ncbi_results -j 10 --detailed
```

---

## Usage Reference

```
python ncbi_upload_check.py [-h] [OPTIONS]
```

### Input / Output

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--input` | `-i` | `ids.txt` | Text file with one sample ID per line |
| `--output-dir` | `-o` | `ncbi_check_results` | Directory for all output files |
| `--found-file` | `-f` | `found_biosamples.tsv` | TSV of found samples (relative to `--output-dir`) |
| `--found-ids-file` | `-F` | `found_ids.txt` | Plain-text list of found IDs (relative to `--output-dir`) |
| `--not-found-file` | `-n` | `not_found_ids.txt` | Plain-text list of IDs not found |
| `--log-file` | `-l` | `ncbi_check.log` | Log file (relative to `--output-dir`) |

### NCBI / Entrez

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--config` | `-c` | `~/.ncbi_config` | INI config file for credentials |
| `--database` | `-d` | `biosample` | Entrez database to query |

### Parallelism / Retry

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--jobs` | `-j` | `8` | Worker threads (auto-capped at rate limit) |
| `--retries` | `-r` | `5` | Max retries per ID on transient errors |
| `--retry-delay` | `-R` | `2.0` | Base back-off delay in seconds; doubles each retry |

### Output Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--detailed` | — | off | Save extended TSV + raw XML records |
| `--verbose` | `-v` | off | Enable DEBUG-level logging |

---

## Output Files

All files land in `--output-dir` (default: `ncbi_check_results/`):

```
ncbi_check_results/
├── found_biosamples.tsv        # structured metadata for found IDs
├── found_ids.txt               # plain list of found IDs (for pipeline use)
├── not_found_ids.txt           # plain list of IDs not found
├── ncbi_check.log              # full timestamped log
└── raw_records/                # only with --detailed
    ├── AUSMDU12345.xml
    └── ...
```

### `found_biosamples.tsv` columns

| Column | Source |
|--------|--------|
| `AUSMDU_ID` | Input ID |
| `BioSample_ID` | NCBI BioSample accession (e.g. `SAMN…`) |
| `SRA_ID` | SRA run accession (e.g. `SRR…`) |
| `Organism` | Organism name |
| `Strain` | Strain designation |
| `Collection_Date` | Collection date |
| `Geographic_Location` | Country / region |
| `Isolation_Source` | Clinical source |
| `Genotype` | Genotype attribute |
| `Host` | Host organism |
| `Host_Disease` | Disease attribute |
| `Accession` | BioSample accession (repeated for join convenience) |

### Additional columns in `detailed_found_biosamples.tsv` (with `--detailed`)

| Column | Source |
|--------|--------|
| `Lat_Lon` | GPS coordinates |
| `Sample_Type` | Sample type attribute |
| `BioProject` | Linked BioProject accession |
| `Submitter` | Submitting organisation |
| `Status` | BioSample release status |

---

## Rate Limiting Explained

NCBI enforces the following limits on the Entrez E-utilities API:

| Credential | Limit |
|------------|-------|
| Anonymous / email only | **3 requests/second** |
| With API key | **10 requests/second** |

Each sample requires **two requests** (one `esearch` + one `efetch`), so the
effective throughput is:

| Scenario | Effective samples/second |
|----------|-------------------------|
| No API key | ~1.5 |
| With API key | ~5 |

The script enforces these limits via a **token-bucket rate limiter** shared
across all worker threads.  Worker count is automatically capped:

```
workers = min(--jobs, rate_limit)
```

This means passing `-j 64` with no API key silently runs 3 workers. The
maximum that will not trigger HTTP 429 errors.  This is intentional: more
threads would not increase throughput, only contention.

---

## Detailed Mode

`--detailed` activates two extras:

1. **Extended metadata TSV** (`detailed_found_biosamples.tsv`) with the five
   additional fields shown above, including `BioProject`, `Submitter`, and
   `Status`.  These fields are parsed directly from the Entrez BioSample XML
   record using structured XPath queries, not fragile regex on text output.

2. **Raw XML records** saved to `raw_records/<ID>.xml` for every found sample.
   Useful for auditing parsed values or extracting additional fields not yet
   covered by the parser.

---

## Common Issues

### `TypeError: a bytes-like object is required, not 'str'`

Caused by older versions of Biopython returning `bytes` from `efetch` in XML
mode.  Fixed in the current version by decoding the response before string
operations:

```python
raw_text = _raw.decode("utf-8") if isinstance(_raw, bytes) else _raw
```

Upgrade Biopython if you see this in an older environment:

```bash
pip install --upgrade biopython
```

### Inconsistent results across runs

Almost always a rate-limit violation when using too many parallel workers (the
original bash script with 64 parallel `esearch` calls was the source of this).
Verify the log for `HTTP 429` or `attempt N/5 failed` warnings.  Run with
`-v` to see per-ID debug traces.  Ensure `NCBI_API_KEY` is set if checking
more than a few hundred IDs.

### `NCBI email is required when an API key is set`

Set `NCBI_EMAIL` alongside `NCBI_API_KEY`:

```bash
export NCBI_EMAIL="you@institution.edu.au"
```

### Config file not picked up

Check permissions and path expansion:

```bash
ls -la ~/.ncbi_config          # should exist and be readable only by you
python ncbi_upload_check.py -i ids.txt -c ~/.ncbi_config -v
# DEBUG log will confirm whether the file was read
```

### `esearch returned no hits` for IDs that are in NCBI

The search term is passed verbatim to the BioSample text search.  Confirm the
ID format matches what NCBI expects.  Use the NCBI web interface to test one
failing ID manually before reporting a bug.

---

## Example Log Output

```
[2026-04-22 13:30:00] <INFO> ════════════════════════════════════════════════════════════
[2026-04-22 13:30:00] <INFO> NCBI BioSample Upload Check
[2026-04-22 13:30:00] <INFO> ════════════════════════════════════════════════════════════
[2026-04-22 13:30:00] <INFO> Input file      : ausmdu_ids.txt
[2026-04-22 13:30:00] <INFO> Output dir      : /home/user/ncbi_check_results
[2026-04-22 13:30:00] <INFO> Database        : biosample
[2026-04-22 13:30:00] <INFO> Email           : set (withheld from log)
[2026-04-22 13:30:00] <INFO> API key         : set (withheld from log)
[2026-04-22 13:30:00] <INFO> Rate limit      : 10 req/s (API key active)
[2026-04-22 13:30:00] <INFO> Workers active  : 10
[2026-04-22 13:30:00] <INFO> Sample IDs      : 500 to check
[2026-04-22 13:30:01] <INFO> FOUND     AUSMDU12345          → BioSample: SAMN12345678  SRA: SRR9876543
[2026-04-22 13:30:01] <INFO> NOT FOUND AUSMDU99999
...
[2026-04-22 13:31:42] <INFO> ════════════════════════════════════════════════════════════
[2026-04-22 13:31:42] <INFO> SUMMARY
[2026-04-22 13:31:42] <INFO>   Total IDs checked  : 500
[2026-04-22 13:31:42] <INFO>   Found in NCBI      : 342  (68.4%)
[2026-04-22 13:31:42] <INFO>   Not found          : 158  (31.6%)
[2026-04-22 13:31:42] <INFO> ════════════════════════════════════════════════════════════
[2026-04-22 13:31:42] <INFO> Done.
```
