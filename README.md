# Ratings Tracker – daily auto-update

## One-time setup (about 10 minutes)
1. Create a free GitHub account and a new repository (e.g. `rating-tracker`).
2. Upload everything in this folder (keep the `.github/workflows/daily.yml` path).
3. Open `config.json` and replace the placeholder with your CRISIL list address, keeping
   `start={start}` and `limit={limit}` where the paging numbers were.
4. Repo -> Settings -> Pages -> Source: "Deploy from a branch" -> main / root. Your dashboard link appears there.
5. Repo -> Actions -> "Daily rating update" -> Run workflow (first test run).
6. After that it runs by itself every day at 08:00 IST.

## Seeding existing data
Export your current dashboard rows into `data/ratings.json` (same fields as the scraper writes:
agency, id, date, company, industry, title, rating, outlook, amount, instrument, url).
The collector skips anything already present, so nothing is duplicated.

## Adding the other agencies
Each agency is one file in `scrapers/` (copy `crisil.py`) plus its name in the `for a in crisil` line of
`.github/workflows/daily.yml`. One agency failing does not stop the others.

## Known limits
- Amount and instrument are blank: the list does not carry them.
- If an agency blocks GitHub's servers, that agency's run fails and the log says so.
