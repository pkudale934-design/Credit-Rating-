"""CRISIL collector. Reads the rationale list JSON (newest first), keeps only new rows.

Set the list address once in config.json -> "crisil_url" (the same address you gave me,
with start={start}&limit={limit} in place of the paging numbers).
"""
import json, pathlib, sys, datetime
from common import fetch_json, parse_title, load, save, merge

CONFIG = json.loads((pathlib.Path(__file__).resolve().parent.parent / "config.json").read_text())
PAGE = 100
MAX_PAGES = 30  # safety cap: 3,000 rows per run


def parse_date(s):
    for fmt in ("%b %d, %Y", "%d %b %Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(s.strip(), fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return s


def rows_from(payload):
    # The list may be a bare list or wrapped; adapt to whichever key holds the records.
    if isinstance(payload, list):
        return payload
    for k in ("data", "rows", "results", "items", "list"):
        if isinstance(payload.get(k), list):
            return payload[k]
    return []


def to_row(rec):
    title = rec.get("title") or rec.get("Title") or ""
    rating, outlook = parse_title(title)
    return {
        "agency": "CRISIL",
        "id": str(rec.get("prId") or rec.get("id")),
        "date": parse_date(str(rec.get("date") or rec.get("Date") or rec.get("pubDate") or "")),
        "company": rec.get("company") or rec.get("companyName") or rec.get("Company") or "",
        "industry": rec.get("industry") or rec.get("Industry") or "",
        "title": title,
        "rating": rating,
        "outlook": outlook,
        "amount": "",       # needs the rationale page; filled later if wanted
        "instrument": "",
        "url": rec.get("url") or rec.get("link") or rec.get("Link") or "",
    }


def main():
    existing = load()
    known = {r["id"] for r in existing if r["agency"] == "CRISIL"}
    new = []
    for p in range(MAX_PAGES):
        url = CONFIG["crisil_url"].format(start=p * PAGE, limit=PAGE)
        recs = rows_from(fetch_json(url))
        if not recs:
            break
        page_rows = [to_row(r) for r in recs]
        new += [r for r in page_rows if r["id"] not in known]
        # newest first: once a whole page is already known, we are caught up
        if all(r["id"] in known for r in page_rows):
            break
    added = merge(existing, new)
    save(existing)
    print(f"CRISIL: {added} new rows added, {len(existing)} total")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # one agency failing must not stop the others
        print(f"CRISIL FAILED: {e}", file=sys.stderr)
        sys.exit(1)
