#!/usr/bin/env python3
"""
Fetch official bibtex for @article/@inproceedings/@book entries from CrossRef
(DOI-based) and DBLP (title-based fallback). Keeps original citation keys.
Skips @misc/@online/@techreport entries (websites, reports, arXiv-only).
"""
import re
import sys
import time
import json
import urllib.parse
import warnings
warnings.filterwarnings("ignore")

import requests
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bparser import BibTexParser

PEER_REVIEWED = {"article", "inproceedings", "conference", "proceedings", "book", "incollection", "phdthesis"}
SKIP_TYPES    = {"misc", "online", "techreport", "manual", "unpublished", "electronic"}

HEADERS = {"User-Agent": "thesis-bib-updater/1.0 (mailto:annakaranika@gmail.com)"}
CROSSREF_URL = "https://api.crossref.org/works/{doi}/transform/application/x-bibtex"
DBLP_SEARCH  = "https://dblp.org/search/publ/api?q={query}&format=bib&h=1"


def clean_latex(s):
    """Strip basic LaTeX markup for API queries."""
    s = re.sub(r"\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\[a-zA-Z]+\s*", "", s)
    return s.strip()


def fetch_crossref(doi):
    """Return raw bibtex string from CrossRef for a given DOI, or None."""
    doi = doi.strip().lstrip("https://doi.org/").lstrip("http://dx.doi.org/")
    url = CROSSREF_URL.format(doi=urllib.parse.quote(doi, safe="./"))
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200 and "@" in r.text:
            return r.text
    except Exception:
        pass
    return None


def fetch_dblp(title, author_last=""):
    """Return raw bibtex string from DBLP for the best title match, or None."""
    query = clean_latex(title)
    if author_last:
        query = f"{author_last} {query}"
    url = DBLP_SEARCH.format(query=urllib.parse.quote(query))
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200 and "@" in r.text:
            return r.text
    except Exception:
        pass
    return None


def parse_single_entry(raw_bib):
    """Parse a raw bibtex string and return the first BibDatabase entry, or None."""
    try:
        parser = BibTexParser(common_strings=True)
        parser.ignore_nonstandard_types = False
        db = bibtexparser.loads(raw_bib, parser=parser)
        if db.entries:
            return db.entries[0]
    except Exception:
        pass
    return None


KEEP_FIELDS = {
    "author", "title", "booktitle", "journal", "year", "volume", "number",
    "pages", "doi", "isbn", "issn", "publisher", "address", "series",
    "month", "editor", "organization", "institution", "school", "url",
    "chapter", "edition", "note", "howpublished", "archiveprefix",
    "eprint", "primaryclass", "articleno", "numpages",
}

def merge_entry(original, fetched, original_key):
    """
    Merge fetched entry into original: keep the original key and any fields
    the fetched version is missing. Prefer fetched values for common fields.
    """
    merged = dict(original)
    merged["ID"] = original_key
    merged["ENTRYTYPE"] = fetched.get("ENTRYTYPE", original.get("ENTRYTYPE", "misc")).lower()
    for field, value in fetched.items():
        if field.lower() in KEEP_FIELDS:
            merged[field.lower()] = value
    return merged


def process_file(bib_path):
    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    with open(bib_path, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    db = bibtexparser.loads(raw, parser=parser)

    updated, skipped, failed = 0, 0, 0
    for entry in db.entries:
        etype = entry.get("ENTRYTYPE", "misc").lower()
        key   = entry.get("ID", "")

        if etype in SKIP_TYPES:
            skipped += 1
            continue
        if etype not in PEER_REVIEWED:
            skipped += 1
            continue

        doi    = entry.get("doi", "").strip()
        title  = entry.get("title", "").strip()
        author = entry.get("author", "").strip()
        author_last = author.split(",")[0].split(" ")[-1] if author else ""

        fetched_raw = None

        # 1. Try CrossRef by DOI
        if doi:
            fetched_raw = fetch_crossref(doi)
            time.sleep(0.15)

        # 2. Try DBLP by title (if no DOI hit or CrossRef failed)
        if not fetched_raw and title:
            fetched_raw = fetch_dblp(title, author_last)
            time.sleep(0.2)

        if fetched_raw:
            fetched = parse_single_entry(fetched_raw)
            if fetched:
                new_entry = merge_entry(entry, fetched, key)
                # Update in-place in the entry list
                idx = db.entries.index(entry)
                db.entries[idx] = new_entry
                updated += 1
                print(f"  ✓ {key}")
            else:
                failed += 1
                print(f"  ✗ parse failed: {key}")
        else:
            failed += 1
            print(f"  ? not found: {key}")

    # Write back
    writer = BibTexWriter()
    writer.indent = "  "
    writer.order_entries_by = None
    with open(bib_path, "w", encoding="utf-8") as f:
        f.write(bibtexparser.dumps(db, writer=writer))

    print(f"  → {bib_path}: {updated} updated, {skipped} skipped, {failed} not found")
    return updated, skipped, failed


if __name__ == "__main__":
    bib_files = sys.argv[1:] or [
        "/Users/anna/GitHub/phd-thesis/CoMesh/ref.bib",
        "/Users/anna/GitHub/phd-thesis/ControlInContext/refs_titlecase.bib",
        "/Users/anna/GitHub/phd-thesis/RASC/bibliography_short.bib",
    ]
    total_u = total_s = total_f = 0
    for path in bib_files:
        print(f"\nProcessing: {path}")
        u, s, f = process_file(path)
        total_u += u; total_s += s; total_f += f

    print(f"\nTotal: {total_u} updated, {total_s} skipped (misc/online), {total_f} not found")
