"""
NCBI BioSample Upload Check

Check whether a list of sample IDs (e.g., AUSMDU accessions) are already
deposited in the NCBI BioSample database.  Queries are sent via the NCBI
Entrez E-utilities API with a thread-safe token-bucket rate limiter so the
3 req/s (anonymous) or 10 req/s (API-key) ceiling is respected even under
high parallelism.  Transient failures are retried with exponential back-off.

Results are written to:
  - a TSV of found biosamples (structured, downstream-ready)
  - a plain-text list of IDs not found
  - a detailed log file for audit and troubleshooting
  - (optionally) raw Entrez text records in a subdirectory for deep inspection
"""

import argparse
import concurrent.futures
import configparser
import csv
import logging
import os
import sys
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from Bio import Entrez
from tqdm import tqdm

# ─────────────────────────────────── constants ────────────────────────────────

RATE_LIMIT_NO_KEY: int = 3       # max requests/second without an API key
RATE_LIMIT_WITH_KEY: int = 10    # max requests/second with an API key

# Environment variable names for credentials
ENV_EMAIL: str = "NCBI_EMAIL"
ENV_API_KEY: str = "NCBI_API_KEY"
DEFAULT_CONFIG: str = "~/.ncbi_config"

DEFAULT_INPUT: str = "ids.txt"
DEFAULT_OUTPUT_DIR: str = "ncbi_check_results"
DEFAULT_JOBS: int = 8
DEFAULT_MAX_RETRIES: int = 5
DEFAULT_RETRY_DELAY: float = 2.0
DEFAULT_DATABASE: str = "biosample"

BIOSAMPLE_FIELDS: list[str] = [
    "AUSMDU_ID",
    "BioSample_ID",
    "SRA_ID",
    "Organism",
    "Strain",
    "Collection_Date",
    "Geographic_Location",
    "Isolation_Source",
    "Genotype",
    "Host",
    "Host_Disease",
    "Accession",
]

BIOSAMPLE_FIELDS_DETAILED: list[str] = BIOSAMPLE_FIELDS + [
    "Lat_Lon",
    "Sample_Type",
    "BioProject",
    "Submitter",
    "Status",
]

# ──────────────────────────────────── helpers ─────────────────────────────────


class TqdmLoggingHandler(logging.Handler):
    """Route log records through ``tqdm.write`` so progress bars stay intact."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            tqdm.write(self.format(record))
            self.flush()
        except Exception:
            self.handleError(record)


class TokenBucketRateLimiter:
    """Thread-safe token-bucket rate limiter.

    Tokens accumulate at *rate* per second up to *capacity*.  Each call to
    ``acquire()`` consumes one token; if none are available the call blocks
    until a token is ready.
    """

    def __init__(self, rate: float, capacity: float | None = None) -> None:
        self.rate = rate
        self.capacity = capacity if capacity is not None else float(rate)
        self._tokens: float = self.capacity
        self._last_refill: float = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until one request token is available."""
        while True:
            with self._lock:
                now = time.monotonic()
                self._tokens = min(
                    self.capacity,
                    self._tokens + (now - self._last_refill) * self.rate,
                )
                self._last_refill = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
            time.sleep(0.05)


# ──────────────────────────────────── parse_args ──────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check whether sample IDs (e.g., AUSMDU accessions) are already "
            "deposited in the NCBI BioSample database, while strictly honouring "
            "the Entrez API rate limit (3 req/s without key; 10 req/s with key)."
        ),
        epilog=(
            "Credentials (email / API key) are NEVER passed as CLI arguments.\n"
            "Supply them via environment variables or a config file:\n"
            "\n"
            "  Environment variables (recommended):\n"
            f"    export {ENV_EMAIL}=you@example.com\n"
            f"    export {ENV_API_KEY}=YOUR_KEY\n"
            "\n"
            "  Config file (INI format, checked after env vars):\n"
            f"    Default path: {DEFAULT_CONFIG}\n"
            "    [ncbi]\n"
            "    email   = you@example.com\n"
            "    api_key = YOUR_KEY\n"
            "\n"
            "  Override config file path: -c /path/to/your.cfg\n"
            "\n"
            "Examples:\n"
            "  python ncbi_upload_check.py -i ausmdu_ids.txt\n"
            "  python ncbi_upload_check.py -i ids.txt -j 10 -o results --detailed -v\n"
            "  python ncbi_upload_check.py -i ids.txt -c ~/my_ncbi.cfg\n"
            "\n"
            "Rate limits:\n"
            "  Without API key : 3  requests/s  (NCBI default)\n"
            "  With    API key : 10 requests/s\n"
            "\n"
            "Get a free NCBI API key at: https://www.ncbi.nlm.nih.gov/account/\n"
            "\n"
            "Worker threads are automatically capped to the applicable rate limit\n"
            "so you will never trigger HTTP 429 errors regardless of -j value.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    io_grp = parser.add_argument_group("Input / Output")
    io_grp.add_argument(
        "-i", "--input",
        default=DEFAULT_INPUT, metavar="FILE",
        help=f"Text file with one sample ID per line (default: {DEFAULT_INPUT}).",
    )
    io_grp.add_argument(
        "-o", "--output-dir",
        default=DEFAULT_OUTPUT_DIR, metavar="DIR",
        help=f"Directory for all output files (default: {DEFAULT_OUTPUT_DIR}).",
    )
    io_grp.add_argument(
        "-f", "--found-file",
        default="found_biosamples.tsv", metavar="FILE",
        help="TSV filename for found IDs (relative to --output-dir; default: found_biosamples.tsv).",
    )
    io_grp.add_argument(
        "-F", "--found-ids-file",
        default="found_ids.txt", metavar="FILE",
        help="Plain-text filename for IDs found in NCBI (relative to --output-dir; default: found_ids.txt).",
    )
    io_grp.add_argument(
        "-n", "--not-found-file",
        default="not_found_ids.txt", metavar="FILE",
        help="Text filename for IDs not found (relative to --output-dir; default: not_found_ids.txt).",
    )
    io_grp.add_argument(
        "-l", "--log-file",
        default="ncbi_check.log", metavar="FILE",
        help="Log filename (relative to --output-dir; default: ncbi_check.log).",
    )

    ncbi_grp = parser.add_argument_group("NCBI / Entrez")
    ncbi_grp.add_argument(
        "-c", "--config",
        default=DEFAULT_CONFIG, metavar="FILE",
        help=(
            f"INI config file for NCBI credentials (default: {DEFAULT_CONFIG}). "
            f"Checked only when {ENV_EMAIL} / {ENV_API_KEY} env vars are not set. "
            "Format: [ncbi] section with 'email' and 'api_key' keys."
        ),
    )
    ncbi_grp.add_argument(
        "-d", "--database",
        default=DEFAULT_DATABASE, metavar="DB",
        help=f"Entrez database to query (default: {DEFAULT_DATABASE}).",
    )

    run_grp = parser.add_argument_group("Parallelism / Retry")
    run_grp.add_argument(
        "-j", "--jobs",
        type=int, default=DEFAULT_JOBS, metavar="N",
        help=(
            f"Number of parallel worker threads (default: {DEFAULT_JOBS}). "
            "Automatically capped at the applicable rate limit."
        ),
    )
    run_grp.add_argument(
        "-r", "--retries",
        type=int, default=DEFAULT_MAX_RETRIES, metavar="N",
        help=f"Maximum retries per ID on transient errors (default: {DEFAULT_MAX_RETRIES}).",
    )
    run_grp.add_argument(
        "-R", "--retry-delay",
        type=float, default=DEFAULT_RETRY_DELAY, metavar="SECS",
        help=(
            f"Base back-off delay in seconds; doubles each retry "
            f"(default: {DEFAULT_RETRY_DELAY})."
        ),
    )

    misc_grp = parser.add_argument_group("Output options")
    misc_grp.add_argument(
        "--detailed",
        action="store_true",
        help=(
            "Also save raw Entrez XML records to <output-dir>/raw_records/ and "
            "write a second TSV with extended fields for downstream validation analysis."
        ),
    )
    misc_grp.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging (very detailed per-ID tracing).",
    )

    return parser.parse_args()


# ──────────────────────────────────── logic functions ─────────────────────────

logger = logging.getLogger(__name__)


def load_ncbi_credentials(config_path: str) -> tuple[str | None, str | None]:
    """Resolve NCBI email and API key from env vars, then config file fallback.

    Priority order:
      1. ``NCBI_EMAIL`` / ``NCBI_API_KEY`` environment variables
      2. INI config file (``[ncbi]`` section, keys ``email`` / ``api_key``)

    Returns ``(email, api_key)`` — either or both may be ``None``.
    """
    email: str | None = os.environ.get(ENV_EMAIL)
    api_key: str | None = os.environ.get(ENV_API_KEY)

    if email:
        logger.debug("Email loaded from environment variable %s", ENV_EMAIL)
    if api_key:
        logger.debug("API key loaded from environment variable %s", ENV_API_KEY)

    # Only consult config file for values not already set by env vars
    if not email or not api_key:
        cfg_path = Path(config_path).expanduser()
        if cfg_path.is_file():
            cfg = configparser.ConfigParser()
            cfg.read(cfg_path)
            if cfg.has_section("ncbi"):
                if not email and cfg.has_option("ncbi", "email"):
                    email = cfg.get("ncbi", "email").strip() or None
                    if email:
                        logger.debug("Email loaded from config file: %s", cfg_path)
                if not api_key and cfg.has_option("ncbi", "api_key"):
                    api_key = cfg.get("ncbi", "api_key").strip() or None
                    if api_key:
                        logger.debug("API key loaded from config file: %s", cfg_path)
        else:
            logger.debug("Config file not found: %s — skipping", cfg_path)

    return email, api_key


def _attr(attrs: dict[str, str], *keys: str) -> str:
    """Return the first matching attribute value from *attrs*, or ''."""
    for k in keys:
        if k in attrs:
            return attrs[k]
    return ""


def parse_biosample_xml(sample_id: str, raw_xml: str) -> tuple[dict[str, str], dict[str, str]] | tuple[None, None]:
    """Parse an Entrez BioSample XML record into structured dicts.

    Returns ``(standard_row, detailed_row)`` where *detailed_row* is a superset
    containing extra fields for downstream validation analysis.  Returns
    ``(None, None)`` if the XML does not contain a ``<BioSample>`` element.
    """
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError as exc:
        logger.warning("[%s] XML parse error: %s", sample_id, exc)
        return None, None

    bs = root.find(".//BioSample")
    if bs is None:
        return None, None

    # ── IDs ──────────────────────────────────────────────────────────────────
    biosample_id = bs.get("accession", "")
    sra_id = ""
    for id_elem in bs.findall(".//Ids/Id"):
        db = id_elem.get("db", "")
        if db == "BioSample" and not biosample_id:
            biosample_id = (id_elem.text or "").strip()
        elif db == "SRA":
            sra_id = (id_elem.text or "").strip()

    # ── Organism ─────────────────────────────────────────────────────────────
    org_elem = bs.find(".//Description/Organism/OrganismName")
    organism = (org_elem.text or "").strip() if org_elem is not None else ""

    # ── Attributes (harmonized_name preferred, else attribute_name) ──────────
    attrs: dict[str, str] = {}
    for attr in bs.findall(".//Attributes/Attribute"):
        name = (
            attr.get("harmonized_name")
            or attr.get("attribute_name")
            or ""
        ).lower().strip()
        if name:
            attrs[name] = (attr.text or "").strip()

    # ── BioProject link ───────────────────────────────────────────────────────
    bioproject = ""
    for link in bs.findall(".//Links/Link"):
        if link.get("target") == "bioproject":
            bioproject = link.get("label") or (link.text or "").strip()
            break

    # ── Submitter / Owner ─────────────────────────────────────────────────────
    owner_elem = bs.find(".//Owner/Name")
    submitter = (owner_elem.text or "").strip() if owner_elem is not None else ""

    # ── Status ────────────────────────────────────────────────────────────────
    status_elem = bs.find(".//Status")
    status = status_elem.get("status", "") if status_elem is not None else ""

    standard: dict[str, str] = {
        "AUSMDU_ID":           sample_id,
        "BioSample_ID":        biosample_id,
        "SRA_ID":              sra_id,
        "Organism":            organism,
        "Strain":              _attr(attrs, "strain"),
        "Collection_Date":     _attr(attrs, "collection_date", "collection date"),
        "Geographic_Location": _attr(attrs, "geo_loc_name", "geographic location"),
        "Isolation_Source":    _attr(attrs, "isolation_source", "isolation source"),
        "Genotype":            _attr(attrs, "genotype"),
        "Host":                _attr(attrs, "host"),
        "Host_Disease":        _attr(attrs, "host_disease", "host disease"),
        "Accession":           biosample_id,
    }

    detailed: dict[str, str] = {
        **standard,
        "Lat_Lon":    _attr(attrs, "lat_lon", "lat lon"),
        "Sample_Type":_attr(attrs, "sample_type", "sample type"),
        "BioProject": bioproject,
        "Submitter":  submitter,
        "Status":     status,
    }

    return standard, detailed


def query_ncbi(
    sample_id: str,
    database: str,
    rate_limiter: TokenBucketRateLimiter,
    max_retries: int,
    retry_delay: float,
) -> tuple[str, str | None]:
    """Query NCBI for *sample_id* with rate-limiting and exponential back-off.

    Returns ``(sample_id, raw_text)`` on success, or ``(sample_id, None)``
    when the ID is not found after all retries.
    """
    for attempt in range(1, max_retries + 1):
        try:
            # ── esearch ──────────────────────────────────────────────────────
            rate_limiter.acquire()
            logger.debug(
                "[%s] esearch attempt %d/%d", sample_id, attempt, max_retries
            )
            with Entrez.esearch(db=database, term=sample_id, retmax=1) as handle:
                search_results = Entrez.read(handle)

            id_list: list[str] = dict(search_results).get("IdList", [])  # type: ignore[arg-type]
            if not id_list:
                logger.debug("[%s] esearch returned no hits", sample_id)
                return sample_id, None

            record_id = id_list[0]
            logger.debug(
                "[%s] esearch hit — internal record ID: %s", sample_id, record_id
            )

            # ── efetch ───────────────────────────────────────────────────────
            rate_limiter.acquire()
            logger.debug("[%s] efetch record %s", sample_id, record_id)
            with Entrez.efetch(
                db=database, id=record_id, retmode="xml"
            ) as handle:
                _raw = handle.read()
                raw_text: str = _raw.decode("utf-8") if isinstance(_raw, bytes) else _raw

            if "<BioSample" not in raw_text:
                logger.warning(
                    "[%s] efetch returned data but no <BioSample> element found "
                    "— treating as not found",
                    sample_id,
                )
                return sample_id, None

            logger.debug("[%s] efetch XML successful (%d chars)", sample_id, len(raw_text))
            return sample_id, raw_text

        except Exception as exc:
            wait = retry_delay * (2 ** (attempt - 1))
            logger.warning(
                "[%s] attempt %d/%d failed — %s: %s — retrying in %.1fs",
                sample_id, attempt, max_retries,
                type(exc).__name__, exc, wait,
            )
            time.sleep(wait)

    logger.error(
        "[%s] exhausted all %d retries — marking as not found", sample_id, max_retries
    )
    return sample_id, None


def setup_logging(log_path: Path, verbose: bool) -> None:
    """Configure root logger: TqdmLoggingHandler to console + FileHandler."""
    fmt = logging.Formatter(
        fmt="[%(asctime)s] <%(levelname)s> %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = TqdmLoggingHandler()
    console_handler.setFormatter(fmt)

    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    root.addHandler(console_handler)
    root.addHandler(file_handler)


# ──────────────────────────────────── main ────────────────────────────────────


def main() -> None:
    args = parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    setup_logging(out_dir / args.log_file, args.verbose)

    logger.info("═" * 60)
    logger.info("NCBI BioSample Upload Check")
    logger.info("═" * 60)
    logger.info("Input file      : %s", args.input)
    logger.info("Output dir      : %s", out_dir.resolve())
    logger.info("Database        : %s", args.database)
    logger.info("Config file     : %s", args.config)
    logger.info("Workers         : %d (requested)", args.jobs)
    logger.info("Retries         : %d", args.retries)
    logger.info("Retry base delay: %.1fs", args.retry_delay)
    logger.info("Detailed output : %s", args.detailed)

    try:
        _run(args, out_dir)
    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
        sys.exit(1)
    except Exception as exc:
        logger.error("Fatal error: %s", exc, exc_info=True)
        sys.exit(1)

    logger.info("Done.")


def _run(args: argparse.Namespace, out_dir: Path) -> None:
    """Core processing logic (separated so main() can catch all exceptions)."""

    # ── Configure Entrez ──────────────────────────────────────────────────────
    email, api_key = load_ncbi_credentials(args.config)

    if api_key and not email:
        raise ValueError(
            f"NCBI email is required when an API key is set. "
            f"Set the {ENV_EMAIL} environment variable or add 'email' to the "
            f"[ncbi] section of your config file."
        )

    if email:
        Entrez.email = email
        logger.info("Email           : set (withheld from log)")
    else:
        logger.warning(
            "No NCBI email found.  Set %s or add 'email' to [ncbi] in your "
            "config file.  Queries will proceed but NCBI may throttle "
            "unidentified clients.",
            ENV_EMAIL,
        )

    if api_key:
        Entrez.api_key = api_key
        rate = RATE_LIMIT_WITH_KEY
        logger.info("API key         : set (withheld from log)")
        logger.info("Rate limit      : %d req/s (API key active)", rate)
    else:
        rate = RATE_LIMIT_NO_KEY
        logger.warning(
            "Rate limit      : %d req/s (no API key). "
            "Set %s or add 'api_key' to your config file to raise the limit to 10 req/s.",
            rate, ENV_API_KEY,
        )

    # Cap worker threads so we never exceed the rate threshold
    workers = min(args.jobs, rate)
    if workers < args.jobs:
        logger.info(
            "Workers capped  : %d → %d (= rate limit) to avoid HTTP 429",
            args.jobs, workers,
        )
    else:
        logger.info("Workers active  : %d", workers)

    rate_limiter = TokenBucketRateLimiter(rate=float(rate), capacity=float(rate))

    # ── Read input IDs ────────────────────────────────────────────────────────
    input_path = Path(args.input)
    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    sample_ids: list[str] = [
        line.strip() for line in input_path.read_text().splitlines() if line.strip()
    ]
    total = len(sample_ids)
    if total == 0:
        logger.warning("Input file is empty — nothing to do.")
        return
    logger.info("Sample IDs      : %d to check", total)

    # Prepare optional raw-records directory
    raw_dir: Path | None = None
    if args.detailed:
        raw_dir = out_dir / "raw_records"
        raw_dir.mkdir(exist_ok=True)
        logger.info("Detailed mode   : raw records → %s", raw_dir)

    # ── Parallel query ────────────────────────────────────────────────────────
    found_standard: list[dict[str, str]] = []
    found_detailed: list[dict[str, str]] = []
    not_found_ids: list[str] = []

    logger.info("─" * 60)
    logger.info("Starting parallel NCBI queries …")

    with tqdm(
        total=total,
        desc="NCBI BioSample",
        unit="ID",
        dynamic_ncols=True,
        file=sys.stderr,
    ) as pbar:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_id: dict[concurrent.futures.Future, str] = {
                executor.submit(
                    query_ncbi,
                    sid,
                    args.database,
                    rate_limiter,
                    args.retries,
                    args.retry_delay,
                ): sid
                for sid in sample_ids
            }

            for future in concurrent.futures.as_completed(future_to_id):
                sample_id, raw_text = future.result()

                if raw_text:
                    std_row, det_row = parse_biosample_xml(sample_id, raw_text)
                    if std_row is None:
                        not_found_ids.append(sample_id)
                        logger.warning("[%s] XML parsed but no BioSample data — skipping", sample_id)
                        pbar.update(1)
                        continue
                    found_standard.append(std_row)
                    found_detailed.append(det_row)  # type: ignore[arg-type]
                    logger.info(
                        "FOUND     %-20s → BioSample: %-12s  SRA: %s",
                        sample_id,
                        std_row["BioSample_ID"] or "?",
                        std_row["SRA_ID"] or "?",
                    )
                    if raw_dir is not None:
                        (raw_dir / f"{sample_id}.xml").write_text(
                            raw_text, encoding="utf-8"
                        )
                else:
                    not_found_ids.append(sample_id)
                    logger.info("NOT FOUND %-20s", sample_id)

                pbar.set_postfix(
                    found=len(found_standard),
                    not_found=len(not_found_ids),
                    refresh=False,
                )
                pbar.update(1)

    logger.info("─" * 60)

    # ── Write outputs ─────────────────────────────────────────────────────────
    found_path = out_dir / args.found_file
    with found_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=BIOSAMPLE_FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(found_standard)
    logger.info("Found TSV          : %s  (%d rows)", found_path, len(found_standard))

    if args.detailed:
        detailed_path = out_dir / ("detailed_" + args.found_file)
        with detailed_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=BIOSAMPLE_FIELDS_DETAILED, delimiter="\t"
            )
            writer.writeheader()
            writer.writerows(found_detailed)
        logger.info(
            "Detailed TSV       : %s  (%d rows)", detailed_path, len(found_detailed)
        )

    found_ids_path = out_dir / args.found_ids_file
    with found_ids_path.open("w", encoding="utf-8") as fh:
        fh.writelines(f"{row['AUSMDU_ID']}\n" for row in found_standard)
    logger.info("Found IDs list     : %s  (%d IDs)", found_ids_path, len(found_standard))

    not_found_path = out_dir / args.not_found_file
    with not_found_path.open("w", encoding="utf-8") as fh:
        fh.writelines(f"{sid}\n" for sid in sorted(not_found_ids))
    logger.info(
        "Not-found list     : %s  (%d IDs)", not_found_path, len(not_found_ids)
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    logger.info("═" * 60)
    logger.info("SUMMARY")
    logger.info("  Total IDs checked  : %d", total)
    logger.info("  Found in NCBI      : %d  (%.1f%%)", len(found_standard),
                100 * len(found_standard) / total if total else 0)
    logger.info("  Not found          : %d  (%.1f%%)", len(not_found_ids),
                100 * len(not_found_ids) / total if total else 0)
    logger.info("═" * 60)


if __name__ == "__main__":
    main()
