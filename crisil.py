"""CRISIL collector. Reads the rationale list JSON (newest first), keeps only new rows."""
import json, pathlib, sys, datetime, re
from urllib.parse import quote
from common import fetch_json, parse_title, load, save, merge

CONFIG = json.loads((pathlib.Path(__file__).resolve().parent / "config.json").read_text())
PAGE = 100
MAX_PAGES = 30  # safety cap per run (3,000 rows)
DOC_BASE = "https://www.crisilratings.com/mnt/winshare/Ratings/RatingList/RatingDocs/"


def parse_date(s):
    for fmt in ("%b %d, %Y", "%d %b %Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(s.strip(), fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return s


def rating_from_heading(heading):
    # Use the final quoted part (the new rating) when present
    quoted = re.findall(r"[\u2018'\"]([^\u2019'\"]*)[\u2019'\"]", heading or "")
    text = quoted[-1] if quoted else (heading or "")
    return parse_title(text)


def to_row(rec):
    heading = rec.get("heading") or ""
    rating, outlook = rating_from_heading(heading)
    fname = rec.get("ratingFileName") or ""
    return {
        "agency": "CRISIL",
        "id": str(rec.get("prId")),
        "date": parse_date(rec.get("ratingDate") or rec.get("transDate") or ""),
        "company": rec.get("companyName") or "",
        "industry": rec.get("industryName") or "",
        "title": heading,
        "rating": rating,
        "outlook": outlook,
        "amount": "",
        "instrument": "",
        "url": DOC_BASE + quote(fname) if fname else "",
    }


def main():
    existing = load()
    known = {r["id"] for r in existing if r["agency"] == "CRISIL"}
    new = []
    for p in range(MAX_PAGES):
        url = CONFIG["crisil_url"].format(start=p * PAGE, limit=PAGE)
        payload = fetch_json(url)
        recs = payload.get("docs", []) if isinstance(payload, dict) else []
        if not recs:
            if p == 0:
                print("WARNING: CRISIL returned no records; keys:", list(payload)[:10] if isinstance(payload, dict) else type(payload))
            break
        page_rows = [to_row(r) for r in recs]
        new += [r for r in page_rows if r["id"] not in known]
        if all(r["id"] in known for r in page_rows):
            break
    added = merge(existing, new)
    save(existing)
    print(f"CRISIL: {added} new rows added, {len(existing)} total")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"CRISIL FAILED: {e}", file=sys.stderr)
        sys.exit(1)
