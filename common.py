"""Shared helpers: load/save the data file, de-duplicate, parse rating from title."""
import json, re, pathlib, urllib.request

DATA_FILE = pathlib.Path(__file__).resolve().parent.parent / "data" / "ratings.json"
UA = "Mozilla/5.0 (compatible; rating-tracker/1.0)"

# Longest first so "CRISIL AA+" is not read as "CRISIL A"
RATING_RE = re.compile(
    r"(?<![\w+\-])("
    r"A1\+|A1|A2\+|A2|A3\+|A3|A4\+|A4"
    r"|AAA|AA\+|AA-|AA|A\+|A-|A"
    r"|BBB\+|BBB-|BBB|BB\+|BB-|BB|B\+|B-|B|C|D"
    r")(?![\w+\-])"
)
OUTLOOK_RE = re.compile(r"\b(Stable|Positive|Negative|Developing|Watch)\b", re.I)


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_json(url):
    return json.loads(fetch(url))


def parse_title(title):
    rating = RATING_RE.search(title or "")
    outlook = OUTLOOK_RE.search(title or "")
    return (rating.group(1) if rating else ""), (outlook.group(1).title() if outlook else "")


def load():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return []


def save(rows):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    rows.sort(key=lambda r: (r["date"], r["id"]), reverse=True)
    DATA_FILE.write_text(json.dumps(rows, indent=1, ensure_ascii=False))


def merge(existing, new):
    """Add only rows whose (agency, id) is not already present. Returns count added."""
    seen = {(r["agency"], r["id"]) for r in existing}
    added = 0
    for r in new:
        key = (r["agency"], r["id"])
        if key not in seen:
            existing.append(r)
            seen.add(key)
            added += 1
    return added
