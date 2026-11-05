#!/usr/bin/env python3
"""Merge new rating rows into Ratings_Explorer HTML (the gzip+base64 blob in <script id=d1/d2>).

Usage:
  python merge_build.py --html index.html --new new_rows.jsonl --out index.html
  python merge_build.py --html index.html --selftest

new_rows.jsonl: one JSON object per line, keys = the 16 column names, values = display
strings (or null). 'Link' is the full URL. Missing keys are treated as null.
"""
import argparse, base64, gzip, json, re, sys, datetime, random
from collections import defaultdict

COLS = ["Rating Agency","Date","Company Name","Industry / Sector","Instrument / Facility","Amount","Rating",
        "Outlook","Rating Action","Status","Report Title","Document Type","Source ID","PDF File Name","Link","Additional Details"]
PRE = {'ICRA':'https://www.icra.in/Rationale/ShowRationaleReport?Id=',
       'CARE Ratings':'https://www.careratings.com/upload/CompanyFiles/PR/',
       'CRISIL':'https://www.crisil.com/mnt/winshare/Ratings/RatingList/RatingDocs/',
       'Infomerics':'https://infomericstorage.blob.core.windows.net/uploads/',
       'Acuité':'https://connect.acuite.in/fcompany-details/'}
IR = 'https://www.indiaratings.co.in/pressrelease/'
KEY_COLS = ["Rating Agency","Date","Company Name","Instrument / Facility","Rating","Source ID","Link","Rating Action"]

# ---------- HTML <-> data ----------
def read_blob(html):
    parts = [re.search(r'id="d%d">(.*?)</script>' % i, html, re.S).group(1).strip() for i in (1, 2)]
    return json.loads(gzip.decompress(base64.b64decode(''.join(parts))))

def write_blob(html, obj):
    txt = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf8')
    b64 = base64.b64encode(gzip.compress(txt, 9)).decode()
    h = len(b64) // 2
    for i, part in ((1, b64[:h]), (2, b64[h:])):
        html = re.sub(r'(id="d%d">).*?(</script>)' % i, lambda m: m.group(1) + part + m.group(2), html, count=1, flags=re.S)
    return html

# ---------- raw (dictionary) <-> display, mirrors val() in the page JS ----------
def to_display(r):
    ag = r.get('Rating Agency') or ''
    out = {}
    for c in COLS:
        v = r.get(c)
        out[c] = '' if v is None else v
    # Link
    v = r.get('Link')
    if v is None:
        m = re.search(r'URL Key: ([^;]+)', r.get('Additional Details') or '') if ag == 'India Ratings' else None
        out['Link'] = IR + m.group(1).strip() if m else ''
    elif v[:1] == '\x02':
        out['Link'] = v[1:]
    elif v == '' and ag == 'ICRA':
        out['Link'] = PRE[ag] + (r.get('Source ID') or '')
    else:
        out['Link'] = PRE.get(ag, '') + v
    # Report Title
    v = r.get('Report Title')
    out['Report Title'] = '' if v is None else ((r.get('Company Name') or '') + v[1:] if v[:1] == '\x01' else v)
    # PDF File Name
    v = r.get('PDF File Name')
    if v is None: out['PDF File Name'] = ''
    elif v != '': out['PDF File Name'] = v
    else:
        from urllib.parse import unquote
        out['PDF File Name'] = unquote(out['Link'].split('/')[-1])
    return out

def to_raw(d):
    """display dict -> raw dict (None = null code -1)"""
    g = lambda k: (d.get(k) or '')
    ag = g('Rating Agency'); r = {}
    for c in COLS:
        r[c] = g(c) or None
    # Link
    url = g('Link'); p = PRE.get(ag, '')
    if not url: r['Link'] = None
    elif ag == 'India Ratings' and url.startswith(IR) and re.search(r'URL Key: ' + re.escape(url[len(IR):]) + r'(;|$)', g('Additional Details')): r['Link'] = None
    elif ag == 'ICRA' and url == p + g('Source ID'): r['Link'] = ''
    elif p and url.startswith(p) and url[len(p):][:1] != '\x02' and url[len(p):]: r['Link'] = url[len(p):]
    else: r['Link'] = '\x02' + url
    # Report Title
    t = g('Report Title'); co = g('Company Name')
    if not t: r['Report Title'] = None
    elif co and t.startswith(co) and t[len(co):][:1] == ':': r['Report Title'] = '\x01' + t[len(co):]
    else: r['Report Title'] = t
    # PDF file name
    f = g('PDF File Name')
    if not f: r['PDF File Name'] = None
    else:
        from urllib.parse import unquote
        link_disp = url
        r['PDF File Name'] = '' if f == unquote(link_disp.split('/')[-1]) and link_disp else f
    return r

class Table:
    def __init__(self, blob):
        self.D = {c: list(blob['data'][c]['d']) for c in COLS}
        self.C = {c: list(blob['data'][c]['c']) for c in COLS}
        self.idx = {c: {s: i for i, s in enumerate(self.D[c])} for c in COLS}
        self.n = len(self.C[COLS[0]])
    def raw_row(self, i):
        return {c: (None if self.C[c][i] < 0 else self.D[c][self.C[c][i]]) for c in COLS}
    def add_raw(self, r):
        for c in COLS:
            v = r[c]
            if v is None: self.C[c].append(-1); continue
            k = self.idx[c].get(v)
            if k is None: k = len(self.D[c]); self.D[c].append(v); self.idx[c][v] = k
            self.C[c].append(k)
        self.n += 1
    def key(self, r):
        return tuple(r[c] for c in KEY_COLS)
    def blob(self):
        return {'cols': COLS, 'data': {c: {'d': self.D[c], 'c': self.C[c]} for c in COLS}}

def clean_date(s):
    s = (s or '').strip()
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', s): return s
    for f in ('%d-%m-%Y', '%d/%m/%Y', '%d %b %Y', '%d %B %Y', '%b %d, %Y'):
        try: return datetime.datetime.strptime(s, f).strftime('%Y-%m-%d')
        except ValueError: pass
    return None

def set_asof(html, table):
    dates = [d for d in table.D['Date'] if re.match(r'^\d{4}-\d{2}-\d{2}$', d)]
    asof = max(dates)
    return re.sub(r'(<div class="brand"><h1>Ratings Explorer</h1><span>)[^<]*(</span>)',
                  lambda m: m.group(1) + 'Seven Indian credit rating agencies in one table · Data as of ' + asof + m.group(2), html, count=1)

def merge(html, new_rows):
    t = Table(read_blob(html))
    seen = {t.key(t.raw_row(i)) for i in range(t.n)}
    added = defaultdict(int); skipped = 0; bad = 0
    for d in new_rows:
        d = dict(d); d['Date'] = clean_date(d.get('Date'))
        if not d['Date'] or not d.get('Rating Agency') or not d.get('Company Name'): bad += 1; continue
        r = to_raw(d); k = t.key(r)
        if k in seen: skipped += 1; continue
        seen.add(k); t.add_raw(r); added[d['Rating Agency']] += 1
    html = write_blob(html, t.blob())
    return set_asof(html, t), dict(added), skipped, bad

def selftest(html):
    blob = read_blob(html); t = Table(blob)
    print('rows', t.n)
    # 1. re-serialisation is lossless
    assert read_blob(write_blob(html, t.blob())) == blob, 'blob round trip failed'
    print('blob round-trip OK')
    # 2. encoder reproduces what the page displays
    random.seed(1); bad = 0
    for i in random.sample(range(t.n), 60000):
        r = t.raw_row(i); disp = to_display(r); r2 = to_raw(disp)
        if to_display(r2) != disp:
            bad += 1
            if bad < 4: print('MISMATCH', i, r, disp, r2, sep='\n  ')
    print('encode/decode mismatches in 60000 sampled rows:', bad)
    assert bad == 0
    # 3. dedupe: re-adding existing rows adds nothing
    sample = [to_display(t.raw_row(i)) for i in random.sample(range(t.n), 2000)]
    _, added, skipped, _ = merge(html, sample)
    print('re-adding 2000 existing rows -> added', added, 'skipped', skipped)
    assert not added

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--html', required=True); ap.add_argument('--new'); ap.add_argument('--out'); ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    html = open(a.html, encoding='utf8').read()
    if a.selftest: selftest(html); return
    rows = [json.loads(l) for l in open(a.new, encoding='utf8') if l.strip()]
    html, added, skipped, bad = merge(html, rows)
    open(a.out or a.html, 'w', encoding='utf8').write(html)
    print(json.dumps({'added': added, 'duplicates_skipped': skipped, 'invalid_rows': bad}))

if __name__ == '__main__':
    main()
