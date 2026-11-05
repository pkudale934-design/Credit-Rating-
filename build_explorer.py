"""Add rows from ratings.json (collector output) into the Ratings Explorer page (index.html)."""
import json, re, pathlib, sys
import merge_build

HTML = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "index.html")
DATA = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "ratings.json")

ACTIONS = [("downgrad", "Downgrades"), ("upgrad", "Upgrades"), ("reaffirm", "Affirms"), ("affirm", "Affirms"),
           ("withdraw", "Withdraws"), ("watch", "Places on Watch"), ("assign", "Assigns"), ("revis", "Revises")]

def rating_text(r):
    quoted = re.findall(r"['‘\"]([^'’\"]*)['’\"]", r.get("title") or "")
    if quoted:
        parts = [p.strip() for p in quoted[-1].split("/") if p.strip().lower().startswith("crisil")]
        if parts: return " / ".join(parts)
    return ("Crisil " + r["rating"]) if r.get("rating") else None

def action(title):
    t = (title or "").lower()
    for k, v in ACTIONS:
        if k in t: return v
    return None

def to_explorer(r):
    if r.get("agency") != "CRISIL": return None          # other agencies get added here as collectors are built
    return {"Rating Agency": "CRISIL", "Date": r["date"], "Company Name": r["company"],
            "Industry / Sector": r.get("industry") or None, "Report Title": r.get("title") or None,
            "Rating": rating_text(r), "Outlook": r.get("outlook") or None, "Rating Action": action(r.get("title")),
            "Source ID": r["id"], "Link": r.get("url") or None,
            "Additional Details": "Source: daily collector"}

rows = [x for x in (to_explorer(r) for r in json.loads(DATA.read_text(encoding="utf8"))) if x]
html, added, skipped, bad = merge_build.merge(HTML.read_text(encoding="utf8"), rows)
HTML.write_text(html, encoding="utf8")
print(json.dumps({"added": added, "already_present": skipped, "invalid": bad}))
