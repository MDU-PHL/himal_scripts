"""
Extract cgMLST cluster history from sample JSON files into CSV format.

Parses a sample JSON repository (such as ngmaster / Pathogenwatch cgMLST results)
for specific sample IDs supplied in a text file or all available samples, extracting
the latest and historical cgMLST cluster assignments (cgT) along with their respective
dates. Supports both fast in-memory loading (standard json) and low-memory streaming
(via ijson if installed) for large datasets.
"""

import argparse
import csv
from datetime import datetime
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Optional streaming parser for ultra-large JSON files
try:
    import ijson  # type: ignore

    HAS_IJSON = True
except ImportError:
    HAS_IJSON = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOG_FORMAT = "[%(asctime)s] <%(levelname)s> %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt=LOG_DATEFMT)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Argument Parsing
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Extract cgMLST cluster results from a sample JSON file to CSV.\n"
            "Extracts current and historical cluster assignments (cgT) and dates\n"
            "for sample IDs specified in an IDs file, or for all samples in the JSON."
        ),
        epilog=(
            "Examples:\n"
            "  # Extract cgMLST clusters for IDs in ids.txt to output.csv:\n"
            "  python extract_cgmlst_clusters.py -j samples.json -i ids.txt -o output.csv\n\n"
            "  # Extract all samples in the JSON file:\n"
            "  python extract_cgmlst_clusters.py -j samples.json -o all_clusters.csv\n\n"
            "  # Save missing IDs and enable verbose logging:\n"
            "  python extract_cgmlst_clusters.py -j samples.json -i ids.txt -o output.csv \\\n"
            "      -m missing_ids.txt -v\n\n"
            "Output Format:\n"
            "  - Single entry:   ID,latest_cgT,date\n"
            "  - Multiple:       ID,latest_cgT,date,previous_cgT,previous_date,previous_cgT_2,previous_date_2,...\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    io_group = parser.add_argument_group("Input / Output Options")
    io_group.add_argument(
        "-j",
        "--json-file",
        required=True,
        metavar="FILE",
        help="Path to the input JSON file (e.g. mdu_samples.json).",
    )
    io_group.add_argument(
        "-i",
        "--id-file",
        default=None,
        metavar="FILE",
        help="Path to text file containing target IDs (one ID per line). If omitted, processes all samples.",
    )
    io_group.add_argument(
        "-o",
        "--output-csv",
        default="cgmlst_clusters.csv",
        metavar="FILE",
        help="Path to output CSV file (default: cgmlst_clusters.csv).",
    )
    io_group.add_argument(
        "-m",
        "--missing-file",
        default=None,
        metavar="FILE",
        help="Optional path to write IDs from --id-file that were not found in the JSON file.",
    )
    io_group.add_argument(
        "-k",
        "--keep-missing",
        action="store_true",
        help="Include missing IDs in the output CSV with empty cluster/date values.",
    )

    perf_group = parser.add_argument_group("Performance & Logging")
    perf_group.add_argument(
        "-s",
        "--stream",
        action="store_true",
        help="Force streaming mode using ijson if installed (recommended for multi-gigabyte JSON files).",
    )
    perf_group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose DEBUG logging.",
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Logic Functions
# ---------------------------------------------------------------------------


def load_target_ids(ids_path: str) -> Tuple[List[str], Set[str]]:
    """
    Load target sample IDs from a text file.

    Maintains original line order while providing a set for O(1) membership testing.

    Args:
        ids_path: Path to text file containing one ID per line.

    Returns:
        Tuple of (ordered_id_list, id_set).
    """
    ordered_ids: List[str] = []
    seen: Set[str] = set()

    with open(ids_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            clean_id = line.strip()
            if not clean_id or clean_id.startswith("#"):
                continue
            if clean_id not in seen:
                seen.add(clean_id)
                ordered_ids.append(clean_id)

    logger.info("Loaded %d unique target IDs from %s", len(ordered_ids), ids_path)
    return ordered_ids, seen


def parse_date_key(date_str: str) -> Any:
    """
    Parse a date string for chronological sorting.

    Attempts standard ISO formats (YYYY-MM-DD), falling back to raw string.

    Args:
        date_str: String representation of a date.

    Returns:
        A sortable object (datetime or str).
    """
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
    return date_str


def extract_cluster_history(sample_dict: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Extract cluster history sorted from newest to oldest.

    Args:
        sample_dict: Dictionary containing sample metadata and clusters.

    Returns:
        List of (date, cluster_id) tuples ordered chronologically descending (latest first).
    """
    raw_clusters = sample_dict.get("clusters")
    if not isinstance(raw_clusters, dict) or not raw_clusters:
        # Fallback if no clusters dict is present, check current date
        fallback_date = (
            str(sample_dict.get("current") or sample_dict.get("date_updated") or "")
        )
        return [(fallback_date, "")] if fallback_date else []

    # Sort cluster dates descending (newest first)
    sorted_date_keys = sorted(
        raw_clusters.keys(), key=lambda d: parse_date_key(str(d)), reverse=True
    )

    history: List[Tuple[str, str]] = []
    for d in sorted_date_keys:
        cluster_val = raw_clusters[d]
        cluster_str = "" if cluster_val is None else str(cluster_val)
        history.append((str(d), cluster_str))

    return history


def process_json_in_memory(
    json_path: str,
    target_ids_set: Optional[Set[str]],
) -> Dict[str, Dict[str, Any]]:
    """
    Load JSON file into memory and extract relevant sample data.

    Args:
        json_path: Path to the JSON file.
        target_ids_set: Set of IDs to filter for, or None to extract all.

    Returns:
        Dictionary of {sample_id: sample_data}.
    """
    logger.info("Loading JSON file into memory: %s", json_path)
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(
            f"Expected top-level JSON object (dict), found {type(data).__name__}"
        )

    matched_samples: Dict[str, Dict[str, Any]] = {}
    if target_ids_set is not None:
        for sample_id in target_ids_set:
            if sample_id in data:
                matched_samples[sample_id] = data[sample_id]
    else:
        matched_samples = data

    logger.info(
        "Extracted %d sample records from total %d entries in JSON",
        len(matched_samples),
        len(data),
    )
    return matched_samples


def process_json_stream(
    json_path: str,
    target_ids_set: Optional[Set[str]],
) -> Dict[str, Dict[str, Any]]:
    """
    Stream large JSON file using ijson to minimise memory usage.

    Args:
        json_path: Path to the JSON file.
        target_ids_set: Set of IDs to filter for, or None to extract all.

    Returns:
        Dictionary of {sample_id: sample_data}.
    """
    if not HAS_IJSON:
        raise RuntimeError("Streaming mode requested but 'ijson' is not installed.")

    logger.info("Streaming JSON file via ijson: %s", json_path)
    matched_samples: Dict[str, Dict[str, Any]] = {}
    total_scanned = 0

    with open(json_path, "rb") as f:
        for sample_id, sample_data in ijson.kvitems(f, ""):
            total_scanned += 1
            if total_scanned % 50000 == 0:
                logger.debug("Scanned %d entries from JSON stream...", total_scanned)

            if target_ids_set is None or sample_id in target_ids_set:
                matched_samples[sample_id] = sample_data

            if target_ids_set is not None and len(matched_samples) == len(
                target_ids_set
            ):
                logger.debug(
                    "All %d target IDs discovered early. Halting stream.",
                    len(target_ids_set),
                )
                break

    logger.info(
        "Streaming complete. Extracted %d sample records (scanned %d total)",
        len(matched_samples),
        total_scanned,
    )
    return matched_samples


def build_csv_headers(max_entries: int) -> List[str]:
    """
    Construct CSV header columns based on maximum history entries.

    Format:
      - 1 entry:  ID,latest_cgT,date
      - 2 entries: ID,latest_cgT,date,previous_cgT,previous_date
      - 3+ entries: ID,latest_cgT,date,previous_cgT,previous_date,previous_cgT_2,previous_date_2,...

    Args:
        max_entries: Maximum number of cluster date entries observed.

    Returns:
        List of column header names.
    """
    headers = ["ID", "latest_cgT", "date"]
    if max_entries <= 1:
        return headers

    headers.extend(["previous_cgT", "previous_date"])
    for i in range(2, max_entries):
        headers.extend([f"previous_cgT_{i}", f"previous_date_{i}"])

    return headers


def format_csv_row(
    sample_id: str,
    history: List[Tuple[str, str]],
    max_entries: int,
) -> List[str]:
    """
    Build a single CSV row corresponding to build_csv_headers.

    Args:
        sample_id: The sample ID string.
        history: List of (date, cluster_id) tuples (newest first).
        max_entries: Total number of history slots across the table.

    Returns:
        List of string values for the CSV row.
    """
    row: List[str] = [sample_id]

    if history:
        latest_date, latest_cgt = history[0]
        row.extend([latest_cgt, latest_date])
    else:
        row.extend(["", ""])

    for slot_idx in range(1, max_entries):
        if slot_idx < len(history):
            prev_date, prev_cgt = history[slot_idx]
            row.extend([prev_cgt, prev_date])
        else:
            row.extend(["", ""])

    return row


def write_csv_results(
    output_path: str,
    samples_data: Dict[str, Dict[str, Any]],
    ordered_ids: Optional[List[str]],
    keep_missing: bool = False,
) -> int:
    """
    Write extracted cluster history to CSV file.

    Args:
        output_path: Path for the destination CSV.
        samples_data: Mapping of sample_id to raw sample dictionary.
        ordered_ids: Optional list specifying row ordering.
        keep_missing: Whether to output empty rows for requested IDs not found.

    Returns:
        Number of rows written.
    """
    # Parse history for all available samples
    histories: Dict[str, List[Tuple[str, str]]] = {
        sid: extract_cluster_history(sdata) for sid, sdata in samples_data.items()
    }

    # Determine maximum number of entries to construct appropriate columns
    max_entries = 1
    for h in histories.values():
        if len(h) > max_entries:
            max_entries = len(h)

    headers = build_csv_headers(max_entries)

    # Determine sequence of sample IDs to write
    if ordered_ids is not None:
        ids_to_write = [
            sid for sid in ordered_ids if sid in histories or keep_missing
        ]
    else:
        ids_to_write = sorted(histories.keys())

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for sid in ids_to_write:
            hist = histories.get(sid, [])
            row = format_csv_row(sid, hist, max_entries)
            writer.writerow(row)

    logger.info("Successfully wrote %d records to %s", len(ids_to_write), output_path)
    return len(ids_to_write)


# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------


def main() -> None:
    """Main CLI execution flow."""
    args = parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    logger.info("Starting cgMLST cluster extraction")
    logger.info("JSON file:       %s", args.json_file)
    logger.info("IDs file:        %s", args.id_file or "None (extract all)")
    logger.info("Output CSV:      %s", args.output_csv)
    logger.info("Missing file:    %s", args.missing_file or "None")
    logger.info("Keep missing:    %s", args.keep_missing)

    if not os.path.isfile(args.json_file):
        logger.error("JSON input file does not exist: %s", args.json_file)
        sys.exit(1)

    ordered_target_ids: Optional[List[str]] = None
    target_ids_set: Optional[Set[str]] = None

    if args.id_file:
        if not os.path.isfile(args.id_file):
            logger.error("IDs file does not exist: %s", args.id_file)
            sys.exit(1)
        ordered_target_ids, target_ids_set = load_target_ids(args.id_file)

    # Determine execution parser: streaming vs in-memory
    use_stream = args.stream
    if not use_stream and HAS_IJSON:
        # Automatically use streaming if file exceeds 500 MB
        file_size_bytes = os.path.getsize(args.json_file)
        if file_size_bytes > 500 * 1024 * 1024:
            logger.info(
                "Large JSON file detected (%.2f MB). Enabling streaming mode via ijson.",
                file_size_bytes / (1024 * 1024),
            )
            use_stream = True

    try:
        if use_stream:
            samples_data = process_json_stream(args.json_file, target_ids_set)
        else:
            samples_data = process_json_in_memory(args.json_file, target_ids_set)
    except Exception as exc:
        logger.error("Failed to parse JSON file: %s", exc)
        sys.exit(1)

    # Check for missing IDs if an IDs file was provided
    if target_ids_set is not None:
        missing_ids = [sid for sid in ordered_target_ids or [] if sid not in samples_data]
        found_count = len(ordered_target_ids or []) - len(missing_ids)
        logger.info(
            "ID match summary: %d found, %d missing (total queried: %d)",
            found_count,
            len(missing_ids),
            len(ordered_target_ids or []),
        )

        if missing_ids:
            logger.warning(
                "%d IDs were not found in %s", len(missing_ids), args.json_file
            )
            if args.missing_file:
                with open(args.missing_file, "w", encoding="utf-8") as mf:
                    for mid in missing_ids:
                        mf.write(f"{mid}\n")
                logger.info("Wrote %d missing IDs to %s", len(missing_ids), args.missing_file)
    else:
        logger.info("Processed all %d samples from JSON", len(samples_data))

    try:
        rows_written = write_csv_results(
            output_path=args.output_csv,
            samples_data=samples_data,
            ordered_ids=ordered_target_ids,
            keep_missing=args.keep_missing,
        )
    except Exception as exc:
        logger.error("Failed writing CSV output: %s", exc)
        sys.exit(1)

    logger.info("Extraction complete. Output saved to %s (%d rows)", args.output_csv, rows_written)
    logger.info("Done.")


if __name__ == "__main__":
    main()

