#!/usr/bin/env python3
"""
aggregate_abritamr_summaries.py
===============================
Collate and aggregate abritamr summary files (summary_matches.txt and
summary_partials.txt) across multiple isolates and sequencing runs.

Features:
- Reads isolate list and run IDs from tab-delimited input file (e.g. runids.tab).
- Locates summary_matches.txt and summary_partials.txt in abritamr output dirs:
    <base_path>/<RUN_ID>/<ISOLATE>/abritamr/current/summary_[matches|partials].txt
- Dynamically discovers and aligns columns across all isolates, appending any new
  drug classes or resistance columns to the end of the output tables.
- Generates separate aggregated tables for matches and partials (TSV).
- Exports missing files log and comprehensive summary statistics.
- Parallel processing with multi-threading for fast execution.
"""

import argparse
import csv
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# -----------------------------------------------------------------------------
# Constants & Defaults
# -----------------------------------------------------------------------------
DEFAULT_BASE_PATH = "/home/mdu/data"
DEFAULT_MATCHES_FILE = "summary_matches.txt"
DEFAULT_PARTIALS_FILE = "summary_partials.txt"
DEFAULT_OUTPUT_DIR = "."
DEFAULT_PREFIX = "abritamr_aggregated"
DEFAULT_THREADS = 64
DEFAULT_FILL_VALUE = "-"
LOG_FORMAT = "[%(asctime)s] <%(levelname)s> %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"


# -----------------------------------------------------------------------------
# CLI Parser
# -----------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Aggregate abritamr summary_matches.txt and summary_partials.txt across multiple isolates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage Examples:
  # Basic run with input tab file and default base path:
  %(prog)s -i runids.tab -o ./results

  # Specify custom prefix and 100 threads:
  %(prog)s -i runids.tab -o ./results -p my_cohort -t 100

  # Custom base path, custom fill value for missing columns, and verbose logging:
  %(prog)s -i ids_run.tab -b /custom/data/path -o ./output -f "NA" -v

  # Specify custom column names in the input file:
  %(prog)s -i samples.tab --isolate-col SampleID --run-id-col SeqRun -o ./out
        """,
    )

    parser.add_argument(
        "-i", "--input-file",
        required=True,
        help="Path to input tab-delimited file containing ISOLATE and RUN_ID columns (e.g., runids.tab).",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to save output tables, reports, and logs (default: '{DEFAULT_OUTPUT_DIR}').",
    )
    parser.add_argument(
        "-p", "--prefix",
        default=DEFAULT_PREFIX,
        help=f"Prefix for output filenames (default: '{DEFAULT_PREFIX}').",
    )
    parser.add_argument(
        "-b", "--base-path",
        default=DEFAULT_BASE_PATH,
        help=f"Base path to sequence data directory (default: '{DEFAULT_BASE_PATH}').",
    )
    parser.add_argument(
        "-t", "--threads",
        type=int,
        default=DEFAULT_THREADS,
        help=f"Number of parallel worker threads (default: {DEFAULT_THREADS}).",
    )
    parser.add_argument(
        "-f", "--fill-value",
        default=DEFAULT_FILL_VALUE,
        help=f"String value to fill for missing/absent columns (default: '{DEFAULT_FILL_VALUE}').",
    )
    parser.add_argument(
        "-m", "--matches-file",
        default=DEFAULT_MATCHES_FILE,
        help=f"Filename of matches summary file (default: '{DEFAULT_MATCHES_FILE}').",
    )
    parser.add_argument(
        "-r", "--partials-file",
        default=DEFAULT_PARTIALS_FILE,
        help=f"Filename of partials summary file (default: '{DEFAULT_PARTIALS_FILE}').",
    )
    parser.add_argument(
        "-I", "--isolate-col",
        default=None,
        help="Column header name for isolate ID in input file (default: auto-detect 'ISOLATE', 'isolate', etc.).",
    )
    parser.add_argument(
        "-R", "--run-id-col",
        default=None,
        help="Column header name for run ID in input file (default: auto-detect 'RUN_ID', 'run_id', etc.).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging output.",
    )

    return parser.parse_args()


# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------
def setup_logging(output_dir: Path, prefix: str, verbose: bool) -> Path:
    """Set up logging to console and timestamped file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = output_dir / f"{prefix}_{timestamp}.log"

    log_level = logging.DEBUG if verbose else logging.INFO

    # Remove existing handlers if any
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    return log_file


# -----------------------------------------------------------------------------
# Input Parsing Logic
# -----------------------------------------------------------------------------
def load_isolate_manifest(
    input_file: Path,
    isolate_col_override: Optional[str] = None,
    run_id_col_override: Optional[str] = None,
) -> List[Tuple[str, str]]:
    """
    Load isolate and run ID pairs from a tab/comma-delimited input file.

    Returns:
        List of (isolate, run_id) tuples.
    """
    if not input_file.is_file():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    isolates_data: List[Tuple[str, str]] = []

    with open(input_file, "r", encoding="utf-8", errors="replace") as f:
        # Detect delimiter using first non-empty line
        sample_lines = [f.readline() for _ in range(5)]
        sample_text = "".join(sample_lines)
        if not sample_text.strip():
            raise ValueError(f"Input file {input_file} is empty.")

        f.seek(0)
        delimiter = "\t" if "\t" in sample_lines[0] else ("," if "," in sample_lines[0] else None)
        reader = csv.reader(f, delimiter=delimiter) if delimiter else csv.reader(f, delimiter="\t")

        header = None
        for row in reader:
            if not row or not any(c.strip() for c in row):
                continue
            if row[0].startswith("#") and not header:
                row[0] = row[0].lstrip("#").strip()
            header = [c.strip() for c in row]
            break

        if not header:
            raise ValueError(f"Could not find valid header in {input_file}")

        # Find isolate column
        isolate_col_idx = None
        if isolate_col_override:
            if isolate_col_override in header:
                isolate_col_idx = header.index(isolate_col_override)
            else:
                raise ValueError(f"Specified isolate column '{isolate_col_override}' not found in header: {header}")
        else:
            candidates = ["isolate", "isolate_id", "sample", "sample_id", "id", "isolate_name"]
            for idx, col in enumerate(header):
                if col.lower() in candidates:
                    isolate_col_idx = idx
                    break

        # Find run ID column
        run_id_col_idx = None
        if run_id_col_override:
            if run_id_col_override in header:
                run_id_col_idx = header.index(run_id_col_override)
            else:
                raise ValueError(f"Specified run ID column '{run_id_col_override}' not found in header: {header}")
        else:
            candidates = ["run_id", "runid", "run", "seq_run", "sequence_run", "illumina_run", "run_name"]
            for idx, col in enumerate(header):
                if col.lower() in candidates:
                    run_id_col_idx = idx
                    break

        if isolate_col_idx is None:
            raise ValueError(f"Could not auto-detect isolate column in header: {header}. Use --isolate-col to specify.")
        if run_id_col_idx is None:
            raise ValueError(f"Could not auto-detect run ID column in header: {header}. Use --run-id-col to specify.")

        logging.debug(f"Using column '{header[isolate_col_idx]}' (index {isolate_col_idx}) for ISOLATE")
        logging.debug(f"Using column '{header[run_id_col_idx]}' (index {run_id_col_idx}) for RUN_ID")

        for row_num, row in enumerate(reader, start=2):
            if not row or not any(c.strip() for c in row):
                continue
            if len(row) <= max(isolate_col_idx, run_id_col_idx):
                logging.warning(f"Line {row_num} has insufficient columns, skipping: {row}")
                continue
            isolate = row[isolate_col_idx].strip()
            run_id = row[run_id_col_idx].strip()
            if isolate and run_id:
                isolates_data.append((isolate, run_id))

    logging.info(f"Loaded {len(isolates_data)} isolate records from {input_file}")
    return isolates_data


# -----------------------------------------------------------------------------
# Summary File Parser
# -----------------------------------------------------------------------------
def parse_single_summary_file(file_path: Path) -> Tuple[bool, Dict[str, str], List[str]]:
    """
    Parse a single abritamr summary file (matches or partials).

    Returns:
        Tuple of (file_exists, {column_name: value}, list_of_ordered_columns)
    """
    if not file_path.is_file():
        return False, {}, []

    data: Dict[str, str] = {}
    discovered_order: List[str] = []

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f, delimiter="\t")
            header = None
            for row in reader:
                if not row or not any(field.strip() for field in row):
                    continue
                if header is None:
                    header = [h.strip() for h in row]
                    # Track non-isolate column names in discovery order
                    for h in header:
                        if h.lower() not in ("isolate", "#isolate", "isolate_id", "sample", "sample_id"):
                            if h and h not in discovered_order:
                                discovered_order.append(h)
                    continue

                # Data row
                row_values = [v.strip() for v in row]
                if len(row_values) < len(header):
                    row_values.extend([""] * (len(header) - len(row_values)))

                for col_name, val in zip(header, row_values):
                    if col_name.lower() in ("isolate", "#isolate", "isolate_id", "sample", "sample_id"):
                        continue
                    if val:
                        if col_name in data and data[col_name]:
                            # Combine multiple values if present
                            existing_vals = set(data[col_name].split(","))
                            new_vals = [v.strip() for v in val.split(",") if v.strip()]
                            for nv in new_vals:
                                if nv not in existing_vals:
                                    data[col_name] = f"{data[col_name]},{nv}"
                        else:
                            data[col_name] = val
        return True, data, discovered_order
    except Exception as e:
        logging.error(f"Error reading {file_path}: {e}")
        return False, {}, []


# -----------------------------------------------------------------------------
# Worker Processing Function
# -----------------------------------------------------------------------------
def process_isolate_files(
    isolate: str,
    run_id: str,
    base_path: Path,
    matches_filename: str,
    partials_filename: str,
) -> Dict[str, Any]:
    """
    Process both matches and partials summary files for a single isolate.
    """
    isolate_dir = base_path / run_id / isolate / "abritamr" / "current"
    matches_path = isolate_dir / matches_filename
    partials_path = isolate_dir / partials_filename

    matches_found, matches_data, matches_cols = parse_single_summary_file(matches_path)
    partials_found, partials_data, partials_cols = parse_single_summary_file(partials_path)

    return {
        "isolate": isolate,
        "run_id": run_id,
        "matches_found": matches_found,
        "matches_data": matches_data,
        "matches_cols": matches_cols,
        "matches_path": str(matches_path),
        "partials_found": partials_found,
        "partials_data": partials_data,
        "partials_cols": partials_cols,
        "partials_path": str(partials_path),
    }


# -----------------------------------------------------------------------------
# Parallel Aggregator
# -----------------------------------------------------------------------------
def aggregate_all_isolates(
    isolates_data: List[Tuple[str, str]],
    base_path: Path,
    matches_filename: str,
    partials_filename: str,
    threads: int,
) -> List[Dict[str, Any]]:
    """Process all isolates in parallel with a thread pool."""
    results: List[Dict[str, Any]] = []
    total = len(isolates_data)

    logging.info(f"Processing {total} isolates using {threads} threads...")

    completed_count = 0
    with ThreadPoolExecutor(max_workers=threads) as executor:
        future_map = {
            executor.submit(
                process_isolate_files,
                isolate,
                run_id,
                base_path,
                matches_filename,
                partials_filename,
            ): (isolate, run_id)
            for isolate, run_id in isolates_data
        }

        for future in as_completed(future_map):
            completed_count += 1
            isolate, run_id = future_map[future]
            try:
                res = future.result()
                results.append(res)
            except Exception as e:
                logging.error(f"Exception processing isolate {isolate} (Run: {run_id}): {e}")
                results.append({
                    "isolate": isolate,
                    "run_id": run_id,
                    "matches_found": False,
                    "matches_data": {},
                    "matches_cols": [],
                    "matches_path": str(base_path / run_id / isolate / "abritamr" / "current" / matches_filename),
                    "partials_found": False,
                    "partials_data": {},
                    "partials_cols": [],
                    "partials_path": str(base_path / run_id / isolate / "abritamr" / "current" / partials_filename),
                })

            if completed_count % 500 == 0 or completed_count == total:
                logging.info(f"Progress: {completed_count}/{total} isolates processed ({completed_count / total * 100:.1f}%)")

    # Sort results to match original input order
    input_order = {(isolate, run_id): idx for idx, (isolate, run_id) in enumerate(isolates_data)}
    results.sort(key=lambda r: input_order.get((r["isolate"], r["run_id"]), 0))

    return results


# -----------------------------------------------------------------------------
# Output Table Writing
# -----------------------------------------------------------------------------
def write_aggregated_table(
    results: List[Dict[str, Any]],
    data_key: str,
    found_key: str,
    cols_key: str,
    output_file: Path,
    fill_value: str,
) -> Tuple[List[str], int, int]:
    """
    Write aggregated results table for either matches or partials.

    Returns:
        Tuple of (all_discovered_columns, total_files_found, total_isolates_with_hits)
    """
    # Discover all distinct columns preserving discovery order
    discovered_columns: List[str] = []
    discovered_set: Set[str] = set()

    for r in results:
        for col in r[cols_key]:
            if col not in discovered_set:
                discovered_set.add(col)
                discovered_columns.append(col)

    # Standard fixed headers
    fieldnames = ["ISOLATE", "RUN_ID", "FILE_STATUS", "TOTAL_GENES_DETECTED"] + discovered_columns

    total_found = 0
    total_with_hits = 0

    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()

        for r in results:
            is_found = r[found_key]
            data = r[data_key]

            if is_found:
                total_found += 1

            # Count total genes found in this isolate
            genes_detected_count = 0
            if data:
                for col, val in data.items():
                    if val and val != fill_value:
                        genes = [g.strip() for g in val.split(",") if g.strip()]
                        genes_detected_count += len(genes)

            if genes_detected_count > 0:
                total_with_hits += 1

            row_dict: Dict[str, Any] = {
                "ISOLATE": r["isolate"],
                "RUN_ID": r["run_id"],
                "FILE_STATUS": "FOUND" if is_found else "MISSING",
                "TOTAL_GENES_DETECTED": genes_detected_count,
            }

            for col in discovered_columns:
                row_dict[col] = data.get(col, fill_value) if is_found else fill_value

            writer.writerow(row_dict)

    logging.info(f"Aggregated table written to: {output_file} (Columns: {len(fieldnames)})")
    return discovered_columns, total_found, total_with_hits


# -----------------------------------------------------------------------------
# Missing Files & Summary Report Writing
# -----------------------------------------------------------------------------
def write_missing_files_report(results: List[Dict[str, Any]], output_file: Path) -> int:
    """Write TSV log of isolates with missing summary files."""
    missing_count = 0
    fieldnames = [
        "ISOLATE",
        "RUN_ID",
        "MISSING_MATCHES",
        "MISSING_PARTIALS",
        "EXPECTED_MATCHES_PATH",
        "EXPECTED_PARTIALS_PATH",
    ]

    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()

        for r in results:
            missing_m = not r["matches_found"]
            missing_p = not r["partials_found"]
            if missing_m or missing_p:
                missing_count += 1
                writer.writerow({
                    "ISOLATE": r["isolate"],
                    "RUN_ID": r["run_id"],
                    "MISSING_MATCHES": "YES" if missing_m else "NO",
                    "MISSING_PARTIALS": "YES" if missing_p else "NO",
                    "EXPECTED_MATCHES_PATH": r["matches_path"],
                    "EXPECTED_PARTIALS_PATH": r["partials_path"],
                })

    logging.info(f"Missing files log written to: {output_file} ({missing_count} isolates with missing files)")
    return missing_count


def write_summary_report(
    output_file: Path,
    total_isolates: int,
    matches_stats: Tuple[List[str], int, int],
    partials_stats: Tuple[List[str], int, int],
    missing_count: int,
    args: argparse.Namespace,
) -> None:
    """Write human-readable summary report with metrics and discovered classes."""
    m_cols, m_found, m_hits = matches_stats
    p_cols, p_found, p_hits = partials_stats

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("ABRITAMR SUMMARY AGGREGATION REPORT\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Input file:   {args.input_file}\n")
        f.write(f"Base path:    {args.base_path}\n")
        f.write(f"Output dir:   {args.output_dir}\n")
        f.write(f"Threads:      {args.threads}\n\n")

        f.write("OVERALL ISOLATE METRICS:\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total isolates processed:             {total_isolates}\n")
        f.write(f"Isolates with all files present:      {total_isolates - missing_count}\n")
        f.write(f"Isolates with >=1 missing file:       {missing_count} ({(missing_count / total_isolates * 100) if total_isolates else 0:.2f}%)\n\n")

        f.write("SUMMARY_MATCHES METRICS:\n")
        f.write("-" * 40 + "\n")
        f.write(f"Files found:                          {m_found} / {total_isolates} ({(m_found / total_isolates * 100) if total_isolates else 0:.2f}%)\n")
        f.write(f"Files missing:                        {total_isolates - m_found}\n")
        f.write(f"Isolates with detected match hits:    {m_hits} ({(m_hits / m_found * 100) if m_found else 0:.2f}% of found)\n")
        f.write(f"Distinct resistance classes found:    {len(m_cols)}\n")
        if m_cols:
            f.write(f"Classes: {', '.join(m_cols)}\n")
        f.write("\n")

        f.write("SUMMARY_PARTIALS METRICS:\n")
        f.write("-" * 40 + "\n")
        f.write(f"Files found:                          {p_found} / {total_isolates} ({(p_found / total_isolates * 100) if total_isolates else 0:.2f}%)\n")
        f.write(f"Files missing:                        {total_isolates - p_found}\n")
        f.write(f"Isolates with detected partial hits:  {p_hits} ({(p_hits / p_found * 100) if p_found else 0:.2f}% of found)\n")
        f.write(f"Distinct resistance classes found:    {len(p_cols)}\n")
        if p_cols:
            f.write(f"Classes: {', '.join(p_cols)}\n")
        f.write("\n")
        f.write("=" * 70 + "\n")

    logging.info(f"Summary report written to: {output_file}")


# -----------------------------------------------------------------------------
# Main Entrypoint
# -----------------------------------------------------------------------------
def main() -> None:
    """Main execution function."""
    args = parse_args()

    input_path = Path(args.input_file).resolve()
    output_dir = Path(args.output_dir).resolve()
    base_path = Path(args.base_path).resolve()

    # Set up logging
    log_file = setup_logging(output_dir, args.prefix, args.verbose)

    logging.info("=" * 70)
    logging.info("ABRITAMR SUMMARY AGGREGATION STARTED")
    logging.info("=" * 70)
    logging.info(f"Input file:        {input_path}")
    logging.info(f"Base path:         {base_path}")
    logging.info(f"Output directory:  {output_dir}")
    logging.info(f"Prefix:            {args.prefix}")
    logging.info(f"Threads:           {args.threads}")
    logging.info(f"Fill value:        '{args.fill_value}'")
    logging.info(f"Matches file:      {args.matches_file}")
    logging.info(f"Partials file:     {args.partials_file}")
    logging.info(f"Log file:          {log_file}")

    try:
        # 1. Load isolates from input file
        isolates_data = load_isolate_manifest(
            input_file=input_path,
            isolate_col_override=args.isolate_col,
            run_id_col_override=args.run_id_col,
        )

        if not isolates_data:
            logging.error("No valid isolate records found in input file.")
            sys.exit(1)

        # 2. Parallel processing of all summary files
        results = aggregate_all_isolates(
            isolates_data=isolates_data,
            base_path=base_path,
            matches_filename=args.matches_file,
            partials_filename=args.partials_file,
            threads=args.threads,
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 3. Write aggregated matches table
        matches_tsv = output_dir / f"{args.prefix}_matches_{timestamp}.tsv"
        matches_stats = write_aggregated_table(
            results=results,
            data_key="matches_data",
            found_key="matches_found",
            cols_key="matches_cols",
            output_file=matches_tsv,
            fill_value=args.fill_value,
        )

        # 4. Write aggregated partials table
        partials_tsv = output_dir / f"{args.prefix}_partials_{timestamp}.tsv"
        partials_stats = write_aggregated_table(
            results=results,
            data_key="partials_data",
            found_key="partials_found",
            cols_key="partials_cols",
            output_file=partials_tsv,
            fill_value=args.fill_value,
        )

        # 5. Write missing files log
        missing_tsv = output_dir / f"{args.prefix}_missing_files_{timestamp}.tsv"
        missing_count = write_missing_files_report(results, missing_tsv)

        # 6. Write summary metrics report
        report_file = output_dir / f"{args.prefix}_summary_report_{timestamp}.txt"
        write_summary_report(
            output_file=report_file,
            total_isolates=len(isolates_data),
            matches_stats=matches_stats,
            partials_stats=partials_stats,
            missing_count=missing_count,
            args=args,
        )

        logging.info("=" * 70)
        logging.info("AGGREGATION SUMMARY")
        logging.info("=" * 70)
        logging.info(f"Total Isolates:       {len(isolates_data)}")
        logging.info(f"Matches Table:        {matches_tsv}")
        logging.info(f"Partials Table:       {partials_tsv}")
        logging.info(f"Missing Files Report: {missing_tsv}")
        logging.info(f"Summary Report:       {report_file}")
        logging.info("Done.")

    except Exception as e:
        logging.critical(f"Fatal error during execution: {e}", exc_info=args.verbose)
        sys.exit(1)


if __name__ == "__main__":
    main()

