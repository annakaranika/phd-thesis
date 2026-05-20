#!/usr/bin/env python3
"""
Two-pass update for .bib files:
  Pass 1 — Fix abbreviated venue names (booktitle/journal) using VENUE_MAP
            and CrossRef event/container data.
  Pass 2 — Add missing DOIs via CrossRef title+author fuzzy search (only
            if the top hit has a confident title match).
Only @article/@inproceedings/@book entries are touched; @misc/@online skipped.
"""
import re, sys, time, warnings
warnings.filterwarnings("ignore")
import requests, bibtexparser
from bibtexparser.bwriter import BibTexWriter

HEADERS = {"User-Agent": "thesis-bib-fixer/1.0 (mailto:annakaranika@gmail.com)"}

PEER_REVIEWED = {"article","inproceedings","conference","proceedings","book","incollection","phdthesis"}

# ─── Venue abbreviation map ─────────────────────────────────────────────────
VENUE_MAP = {
    # Systems / Networking
    "nsdi":        "USENIX Symposium on Networked Systems Design and Implementation (NSDI)",
    "osdi":        "USENIX Symposium on Operating Systems Design and Implementation (OSDI)",
    "atc":         "USENIX Annual Technical Conference (ATC)",
    "eurosys":     "European Conference on Computer Systems (EuroSys)",
    "sosp":        "ACM Symposium on Operating Systems Principles (SOSP)",
    "asplos":      "ACM International Conference on Architectural Support for Programming Languages and Operating Systems (ASPLOS)",
    "sigcomm":     "ACM Special Interest Group on Data Communication (SIGCOMM)",
    "imc":         "ACM Internet Measurement Conference (IMC)",
    "hotnets":     "ACM Workshop on Hot Topics in Networks (HotNets)",
    "hotedge":     "USENIX Workshop on Hot Topics in Edge Computing (HotEdge)",
    "hotos":       "USENIX Workshop on Hot Topics in Operating Systems (HotOS)",
    "hotcloud":    "USENIX Workshop on Hot Topics in Cloud Computing (HotCloud)",
    "conext":      "ACM International Conference on Emerging Networking EXperiments and Technologies (CoNEXT)",
    "infocom":     "IEEE International Conference on Computer Communications (INFOCOM)",
    "icdcs":       "IEEE International Conference on Distributed Computing Systems (ICDCS)",
    "icdcn":       "International Conference on Distributed Computing and Networking (ICDCN)",
    "disc":        "International Symposium on Distributed Computing (DISC)",
    "podc":        "ACM Symposium on Principles of Distributed Computing (PODC)",
    "middleware":  "ACM/IFIP/USENIX International Middleware Conference (Middleware)",
    "cloudnet":    "IEEE International Conference on Cloud Networking (CloudNet)",
    "hpdc":        "ACM International Symposium on High-Performance Parallel and Distributed Computing (HPDC)",
    "dais":        "International Conference on Distributed Applications and Interoperable Systems (DAIS)",
    "rtas":        "IEEE Real-Time and Embedded Technology and Applications Symposium (RTAS)",
    "rtcsa":       "IEEE International Conference on Real-Time Computing Systems and Applications (RTCSA)",
    "ewsn":        "International Conference on Embedded Wireless Systems and Networks (EWSN)",
    "sensys":      "ACM Conference on Embedded Networked Sensor Systems (SenSys)",
    "ipsn":        "ACM/IEEE International Conference on Information Processing in Sensor Networks (IPSN)",
    "iotdi":       "ACM/IEEE Conference on Internet of Things Design and Implementation (IoTDI)",
    "mobicom":     "ACM International Conference on Mobile Computing and Networking (MobiCom)",
    "mobisys":     "ACM International Conference on Mobile Systems, Applications, and Services (MobiSys)",
    "sec":         "USENIX/ACM Symposium on Edge Computing (SEC)",
    "buildsys":    "ACM International Conference on Systems for Energy-Efficient Built Environments (BuildSys)",
    "focs":        "IEEE Annual Symposium on Foundations of Computer Science (FOCS)",
    "stoc":        "ACM Symposium on Theory of Computing (STOC)",
    "soda":        "ACM-SIAM Symposium on Discrete Algorithms (SODA)",
    "cidr":        "Conference on Innovative Data Systems Research (CIDR)",
    # Databases
    "sigmod":      "ACM International Conference on Management of Data (SIGMOD)",
    "vldb":        "International Conference on Very Large Data Bases (VLDB)",
    "icde":        "IEEE International Conference on Data Engineering (ICDE)",
    # HCI / Robotics
    "chi":         "ACM Conference on Human Factors in Computing Systems (CHI)",
    "cscw":        "ACM Conference on Computer-Supported Cooperative Work and Social Computing (CSCW)",
    "uist":        "ACM Symposium on User Interface Software and Technology (UIST)",
    "ubicomp":     "ACM International Joint Conference on Pervasive and Ubiquitous Computing (UbiComp)",
    "hri":         "ACM/IEEE International Conference on Human-Robot Interaction (HRI)",
    "iros":        "IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS)",
    "icra":        "IEEE International Conference on Robotics and Automation (ICRA)",
    # ML / Vision
    "neurips":     "Conference on Neural Information Processing Systems (NeurIPS)",
    "nips":        "Conference on Neural Information Processing Systems (NeurIPS)",
    "icml":        "International Conference on Machine Learning (ICML)",
    "iclr":        "International Conference on Learning Representations (ICLR)",
    "cvpr":        "IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)",
    # Security
    "ccs":         "ACM Conference on Computer and Communications Security (CCS)",
    "ndss":        "Network and Distributed System Security Symposium (NDSS)",
    # Journals
    "ieee tnsm":   "IEEE Transactions on Network and Service Management",
    "ieee toc":    "IEEE Transactions on Computers",
    "ieee tvt":    "IEEE Transactions on Vehicular Technology",
    "ieee/acm ton":"IEEE/ACM Transactions on Networking",
    "acm toit":    "ACM Transactions on Internet of Things",
    "cacm":        "Communications of the ACM",
    "tocs":        "ACM Transactions on Computer Systems",
    "acm tocs":    "ACM Transactions on Computer Systems",
    "tosn":        "ACM Transactions on Sensor Networks",
    "twc":         "IEEE Transactions on Wireless Communications",
    "igops":       "ACM SIGOPS Operating Systems Review",
    "imwut":       "Proceedings of the ACM on Interactive, Mobile, Wearable and Ubiquitous Technologies (IMWUT)",
    "elsevier comnet": "Computer Networks",
    "ccf tpci":    "CCF Transactions on Pervasive Computing and Interaction",
    "acm sigmod record": "ACM SIGMOD Record",
}

ABBREV_RE = re.compile(r"^[A-Z][A-Za-z'/\-]{0,14}(?:\s*['`]?\d{2,4})?$")

def looks_abbreviated(s):
    s = s.strip()
    if ABBREV_RE.match(s):
        return True
    # Multi-word abbreviations like "IEEE TOC", "ACM TOCS", "Elsevier COMNET":
    # all space/slash-separated tokens must be short (≤8 chars) and at least
    # one token must be all-uppercase.
    tokens = [t for t in re.split(r"[\s/]+", s) if t]
    if 2 <= len(tokens) <= 4 and all(len(t) <= 8 and t[0].isupper() for t in tokens):
        return any(t.isupper() and len(t) >= 2 for t in tokens)
    return False

def clean_latex(s):
    s = re.sub(r"\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\[a-zA-Z]+\s*", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def title_similarity(a, b):
    """Simple word-overlap similarity 0..1."""
    def words(t): return set(re.sub(r"[^a-z0-9 ]", "", t.lower()).split())
    wa, wb = words(a), words(b)
    if not wa or not wb: return 0.0
    return len(wa & wb) / max(len(wa), len(wb))

# ─── CrossRef helpers ────────────────────────────────────────────────────────

def crossref_by_doi(doi):
    """Return CrossRef work dict or None."""
    doi = doi.strip().lstrip("https://doi.org/").lstrip("http://dx.doi.org/")
    url = f"https://api.crossref.org/works/{requests.utils.quote(doi, safe='./')}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json().get("message", {})
    except Exception:
        pass
    return None

def crossref_search(title, author_last="", year=""):
    """Search CrossRef by bibliographic query. Returns top-1 work dict or None."""
    q = clean_latex(title)
    if author_last:
        q = f"{author_last} {q}"
    params = {
        "query.bibliographic": q,
        "rows": 1,
        "mailto": "annakaranika@gmail.com",
    }
    if year:
        params["filter"] = f"from-pub-date:{year},until-pub-date:{year}"
    try:
        r = requests.get("https://api.crossref.org/works", params=params,
                         headers=HEADERS, timeout=10)
        if r.status_code == 200:
            items = r.json().get("message", {}).get("items", [])
            if items:
                return items[0]
    except Exception:
        pass
    return None

def extract_venue(work):
    """Return (venue_str, abbrev) from a CrossRef work dict."""
    event = work.get("event", {}).get("name", "")
    container = (work.get("container-title") or [""])[0]
    abbrev    = (work.get("short-container-title") or [""])[0]
    return (event or container, abbrev)

def format_venue(full, abbrev):
    if not full:
        return None
    full = full.strip(); abbrev = (abbrev or "").strip()
    if "(" in full and ")" in full:
        return full
    if abbrev and abbrev.upper() not in full.upper():
        return f"{full} ({abbrev})"
    return full

def expand_map(val):
    key = val.strip().lower().rstrip(".,")
    if key in VENUE_MAP:
        return VENUE_MAP[key]
    no_year = re.sub(r"[\s'`\-]*\d{2,4}$", "", key).strip()
    if no_year in VENUE_MAP:
        suffix = val.strip()[len(no_year):].strip()
        return VENUE_MAP[no_year] + (f" ({suffix})" if suffix else "")
    return None

# ─── Main processing ─────────────────────────────────────────────────────────

def process_file(bib_path):
    with open(bib_path, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    parser = bibtexparser.bparser.BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    db = bibtexparser.loads(raw, parser=parser)

    venue_count = doi_count = 0

    for entry in db.entries:
        if entry.get("ENTRYTYPE", "misc").lower() not in PEER_REVIEWED:
            continue

        key   = entry.get("ID", "?")
        doi   = entry.get("doi", "").strip()
        title = entry.get("title", "").strip()
        author= entry.get("author", "").strip()
        year  = entry.get("year", "").strip()
        author_last = author.split(",")[0].strip() if author else ""

        work = None  # lazy CrossRef fetch

        # ── Pass 1: venue names ──────────────────────────────────────────────
        for field in ("booktitle", "journal"):
            val = entry.get(field, "").strip()
            if not val or not looks_abbreviated(val):
                continue

            # (a) VENUE_MAP
            new_val = expand_map(val)

            # (b) CrossRef by DOI
            if not new_val and doi:
                if work is None:
                    work = crossref_by_doi(doi); time.sleep(0.15)
                if work:
                    full, abbrev = extract_venue(work)
                    new_val = format_venue(full, abbrev)

            if new_val and new_val != val:
                print(f"  [venue] {key}: {val!r} → {new_val!r}")
                entry[field] = new_val
                venue_count += 1

        # ── Pass 2: add missing DOI ──────────────────────────────────────────
        if not doi and title:
            if work is None and doi:
                work = crossref_by_doi(doi); time.sleep(0.15)
            if work is None:
                work = crossref_search(title, author_last, year); time.sleep(0.2)
            if work:
                # Confidence check: title similarity ≥ 0.75 and year match
                cr_titles = work.get("title", [])
                cr_title  = cr_titles[0] if cr_titles else ""
                sim = title_similarity(clean_latex(title), clean_latex(cr_title))
                cr_year = str((work.get("published") or work.get("issued") or {})
                              .get("date-parts", [[""]])[0][0])
                year_ok = (not year) or (cr_year == year)
                cr_doi  = work.get("DOI", "")
                if sim >= 0.75 and year_ok and cr_doi:
                    print(f"  [doi]   {key}: added DOI {cr_doi!r} (sim={sim:.2f})")
                    entry["doi"] = cr_doi
                    doi_count += 1

    writer = BibTexWriter()
    writer.indent = "  "
    writer.order_entries_by = None
    with open(bib_path, "w", encoding="utf-8") as f:
        f.write(bibtexparser.dumps(db, writer=writer))

    print(f"  → {bib_path}: {venue_count} venues fixed, {doi_count} DOIs added")
    return venue_count, doi_count

if __name__ == "__main__":
    files = sys.argv[1:] or [
        "CoMesh/ref.bib",
        "ControlInContext/refs_titlecase.bib",
        "RASC/bibliography_short.bib",
    ]
    tv = td = 0
    for p in files:
        print(f"\nProcessing: {p}")
        v, d = process_file(p)
        tv += v; td += d
    print(f"\nTotal: {tv} venue names fixed, {td} DOIs added.")
