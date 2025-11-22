# TimeOut London Cafes Scraper

This script scrapes the TimeOut London article **“London’s best cafes and coffee shops”** and collects details like name, description, address, phone, website, and opening hours. All extracted data is saved automatically on the Desktop inside a folder named **ws portfolio**.

---

## What this script does
- Fetches café entries from the main TimeOut article.
- Extracts important info using pattern‑based logic.
- Visits each café’s individual page to collect phone, website, and address (if available).
- Saves everything in:
  - `timeout_london_cafes.csv`
  - `timeout_london_cafes.xlsx`
- Logs any errors or failed fetch attempts in `timeout_errors.log`.

---

## Requirements
Install these Python packages before running:

```
pip install requests beautifulsoup4 pandas openpyxl
```

---

## How to run
Just run the script using:

```
python timeout_cafes_snapshot_v3.py
```

The script will automatically:
- Create the **ws portfolio** folder on Desktop if it doesn’t exist.
- Save the CSV, Excel, and log file there.

---

## Output columns
The saved CSV/XLSX contains:
- name  
- description  
- address  
- phone  
- website  
- opening_hours  
- source_link  

---

## Files generated
All files are saved in:

```
Desktop/ws portfolio/
```

Files created:
- `timeout_london_cafes.csv`
- `timeout_london_cafes.xlsx`
- `timeout_errors.log`

---

## Note
This script works with the current structure of the TimeOut article. If TimeOut changes their layout, the extraction logic might need updates.
