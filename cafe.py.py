"""
timeout_cafes_snapshot_v3.py
Fixed TimeOut London cafes scraper with improved parsing logic.
Requires: requests, beautifulsoup4, pandas, openpyxl
Install: pip install requests beautifulsoup4 pandas openpyxl
"""

import os, re, time, random, requests, logging
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import pandas as pd

# -------- config --------
URL = "https://www.timeout.com/london/food-drink/londons-best-cafes-and-coffee-shops"
MAX_ITEMS = 20
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-GB,en;q=0.9"
}
SAVE_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "ws portfolio")
os.makedirs(SAVE_DIR, exist_ok=True)
SAVE_CSV = os.path.join(SAVE_DIR, "timeout_london_cafes.csv")
SAVE_XLSX = os.path.join(SAVE_DIR, "timeout_london_cafes.xlsx")
LOG_FILE = os.path.join(SAVE_DIR, "timeout_errors.log")

# logging
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

# --------- helpers ----------
def fetch(url, retries=3, backoff=1.4, timeout=20):
    """Fetch URL with retry logic"""
    last_exc = None
    for attempt in range(1, retries+1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            r.raise_for_status()
            return r.text
        except Exception as e:
            last_exc = e
            wait = backoff ** attempt + random.random()
            logging.info(f"Fetch failed ({attempt}) {url} -> {e}; waiting {wait:.1f}s")
            time.sleep(wait)
    raise last_exc

def extract_article_entries(html):
    """Extract cafe entries from TimeOut article using text pattern matching"""
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    
    # Get all text content from the page
    # Look for the main article/content area
    main_content = soup.find('main') or soup.find('article') or soup.find('body')
    
    if not main_content:
        logging.error("Could not find main content area")
        return entries
    
    # Get all text blocks
    text_blocks = []
    for elem in main_content.find_all(['p', 'div', 'section', 'li']):
        text = elem.get_text("\n", strip=True)
        if text and len(text) > 20:
            text_blocks.append(text)
    
    # Combine into one text and split by cafe entries
    full_text = "\n".join(text_blocks)
    
    # Split by "What is it?" pattern - this marks the start of each cafe
    entries_raw = re.split(r'(?=What is it\?)', full_text)
    
    for entry_text in entries_raw:
        if 'What is it?' not in entry_text:
            continue
        
        # Initialize entry dict
        entry = {
            'name': '',
            'description': '',
            'address': '',
            'opening_hours': '',
            'source_link': ''
        }
        
        # Extract name (usually appears before "What is it?")
        lines = entry_text.split('\n')
        for line in lines[:5]:  # Check first few lines
            line = line.strip()
            # Look for a line that looks like a cafe name
            if line and len(line) < 100 and 'What is it?' not in line:
                # Filter out noise
                if not any(x in line.lower() for x in ['recommended', 'stars', 'shopping', 'out of']):
                    if len(line.split()) >= 2:  # At least 2 words
                        entry['name'] = re.sub(r'^\d+\.\s*', '', line).strip()
                        break
        
        # Extract description from "What is it?" section
        what_match = re.search(r'What is it\?\s*(.+?)(?=Why we love it:|Order this:|Address:|$)', 
                               entry_text, re.DOTALL | re.IGNORECASE)
        if what_match:
            entry['description'] = what_match.group(1).strip()
        
        # If no "What is it?" description, try "Why we love it:"
        if not entry['description']:
            why_match = re.search(r'Why we love it:\s*(.+?)(?=Order this:|Address:|$)', 
                                  entry_text, re.DOTALL | re.IGNORECASE)
            if why_match:
                entry['description'] = why_match.group(1).strip()
        
        # Extract address
        addr_match = re.search(r'Address:\s*(.+?)(?=Opening hours?:|$)', 
                              entry_text, re.DOTALL | re.IGNORECASE)
        if addr_match:
            addr = addr_match.group(1).strip()
            # Clean up - take only first line or up to postcode
            addr_lines = addr.split('\n')
            entry['address'] = addr_lines[0].strip()
        
        # Extract opening hours
        hours_match = re.search(r'Opening hours?:\s*(.+?)(?=\n\n|$)', 
                               entry_text, re.DOTALL | re.IGNORECASE)
        if hours_match:
            entry['opening_hours'] = hours_match.group(1).strip().replace('\n', ' ')
        
        # Only add if we have at least a name and description
        if entry['name'] and entry['description']:
            # Find corresponding link in HTML
            # Search for the cafe name in the soup to find its link
            if entry['name']:
                # Look for heading or link with this name
                for elem in main_content.find_all(['h2', 'h3', 'h4', 'a']):
                    elem_text = elem.get_text(strip=True)
                    if entry['name'].lower() in elem_text.lower() or elem_text.lower() in entry['name'].lower():
                        if elem.name == 'a' and elem.get('href'):
                            entry['source_link'] = urljoin(URL, elem.get('href'))
                            break
                        else:
                            # Check for nearby link
                            link = elem.find('a') or elem.find_next('a')
                            if link and link.get('href'):
                                href = link.get('href')
                                # Make sure it's a venue link, not navigation
                                if '/venue/' in href or entry['name'].lower().replace(' ', '-') in href.lower():
                                    entry['source_link'] = urljoin(URL, href)
                                    break
            
            entries.append(entry)
            
            if len(entries) >= MAX_ITEMS:
                break
    
    # If we found no entries, try alternative method
    if not entries:
        logging.info("Pattern-based extraction failed, trying heading-based method")
        entries = extract_by_headings(soup)
    
    return entries[:MAX_ITEMS]

def extract_by_headings(soup):
    """Alternative extraction method using headings"""
    entries = []
    seen = set()
    
    # Find all headings
    headings = soup.find_all(['h2', 'h3', 'h4'])
    
    for h in headings:
        name = h.get_text(" ", strip=True)
        if not name or len(name) > 100:
            continue
        
        # Skip generic headings
        if any(x in name.lower() for x in ['best café', 'top', 'london', 'time out']):
            continue
        
        name = re.sub(r'^\d+\.\s*', '', name).strip()
        key = name.lower()
        
        if key in seen or len(name.split()) < 2:
            continue
        
        seen.add(key)
        
        # Collect text after heading
        description = ""
        address = ""
        opening_hours = ""
        
        # Get next siblings
        current = h.next_sibling
        collected_text = []
        
        while current and len(collected_text) < 10:
            if hasattr(current, 'name'):
                if current.name and re.match(r'^h[1-6]$', current.name):
                    break
                text = current.get_text(" ", strip=True)
                if text:
                    collected_text.append(text)
            current = current.next_sibling if hasattr(current, 'next_sibling') else None
        
        full_text = " ".join(collected_text)
        
        # Parse collected text
        if 'What is it?' in full_text:
            desc_match = re.search(r'What is it\?\s*(.+?)(?=Why we love it:|Address:|$)', 
                                   full_text, re.IGNORECASE)
            if desc_match:
                description = desc_match.group(1).strip()
        
        if not description and len(full_text) > 50:
            description = full_text[:500]
        
        # Address
        if 'Address:' in full_text:
            addr_match = re.search(r'Address:\s*(.+?)(?=Opening|$)', full_text, re.IGNORECASE)
            if addr_match:
                address = addr_match.group(1).strip()
        
        # Opening hours
        if 'Opening hours' in full_text or 'Opening Hours' in full_text:
            hours_match = re.search(r'Opening hours?:\s*(.+?)(?:\.|$)', full_text, re.IGNORECASE)
            if hours_match:
                opening_hours = hours_match.group(1).strip()
        
        # Find link
        link = h.find('a') or h.find_next('a')
        source_link = ""
        if link and link.get('href'):
            href = link.get('href')
            if '/venue/' in href or not href.startswith('http'):
                source_link = urljoin(URL, href)
        
        if description:  # Only add if we have a description
            entries.append({
                'name': name,
                'description': description,
                'address': address,
                'opening_hours': opening_hours,
                'source_link': source_link
            })
        
        if len(entries) >= MAX_ITEMS:
            break
    
    return entries

# Phone and postcode patterns
PHONE_RE = re.compile(r'(\+44\s?\d[\d\s\-]{7,}\d|0\d{2,4}[\s\-]?\d{3,4}[\s\-]?\d{3,4})')
POSTCODE_RE = re.compile(r'[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}', re.IGNORECASE)

def scrape_venue_info(url):
    """Scrape additional venue details from individual pages"""
    out = {"phone": "", "website": "", "address": ""}
    if not url:
        return out
    
    try:
        html = fetch(url)
        soup = BeautifulSoup(html, "html.parser")

        # Phone: look for tel: links
        tel = soup.select_one('a[href^="tel:"]')
        if tel and tel.get("href"):
            out["phone"] = tel.get("href").replace("tel:", "").strip()
        
        # Website: external links
        for sel in ['a[rel*="nofollow"]', 'a[target="_blank"]', 'a.external']:
            a = soup.select_one(sel)
            if a and a.get("href"):
                href = a.get("href")
                if "timeout.com" not in href and href.startswith("http"):
                    out["website"] = href
                    break
        
        # Address: look for address tag
        addr_tag = soup.find("address")
        if addr_tag:
            out["address"] = addr_tag.get_text(" ", strip=True)
        else:
            # Search for postcode in text
            text = soup.get_text(" ", strip=True)
            match = POSTCODE_RE.search(text)
            if match:
                idx = match.start()
                out["address"] = text[max(0, idx-80):min(len(text), idx+80)].strip()
        
        # Phone fallback
        if not out["phone"]:
            text = soup.get_text(" ", strip=True)
            match = PHONE_RE.search(text)
            if match:
                out["phone"] = match.group(0).strip()
    
    except Exception as e:
        logging.info(f"scrape_venue_info failed for {url}: {e}")
    
    return out

def main():
    print("=" * 60)
    print("TimeOut London Cafes Scraper")
    print("=" * 60)
    
    try:
        print(f"\nFetching main page: {URL}")
        html = fetch(URL)
        print(f"✓ Page fetched successfully ({len(html)} bytes)")
    except Exception as e:
        print(f"✗ Could not fetch main page: {e}")
        logging.error(f"Main fetch failed: {e}")
        return

    print("\nExtracting cafe entries...")
    entries = extract_article_entries(html)
    print(f"✓ Found {len(entries)} cafe entries\n")
    
    if not entries:
        print("⚠ Warning: No entries found. The website structure may have changed.")
        logging.warning("No entries extracted")
        return

    rows = []
    print("Scraping individual cafe details:")
    print("-" * 60)
    
    for idx, e in enumerate(entries, 1):
        print(f"[{idx:2d}] {e['name'][:50]}")
        
        # Small delay to be polite
        time.sleep(random.uniform(1.0, 2.0))

        phone = ""
        website = ""
        address = e.get("address", "")

        # Try to get more details from individual page
        if e.get("source_link"):
            try:
                venue = scrape_venue_info(e["source_link"])
                phone = venue.get("phone", "")
                website = venue.get("website", "")
                if not address:
                    address = venue.get("address", "")
            except Exception as ex:
                logging.warning(f"Error scraping {e.get('source_link')}: {ex}")

        row = {
            "name": e.get("name", ""),
            "description": e.get("description", ""),
            "address": address,
            "phone": phone,
            "website": website,
            "opening_hours": e.get("opening_hours", ""),
            "source_link": e.get("source_link", "")
        }
        rows.append(row)

    print("-" * 60)
    
    # Create DataFrame
    df = pd.DataFrame(rows)
    
    # Save files
    try:
        df.to_csv(SAVE_CSV, index=False, encoding='utf-8')
        df.to_excel(SAVE_XLSX, index=False, engine='openpyxl')
        print(f"\n✓ Successfully saved {len(df)} cafes to:")
        print(f"  → {SAVE_CSV}")
        print(f"  → {SAVE_XLSX}")
        print(f"\n✓ Logs saved to: {LOG_FILE}")
    except Exception as e:
        print(f"\n✗ Error saving files: {e}")
        logging.error(f"Save error: {e}")

    print("\n" + "=" * 60)
    print("Scraping complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()