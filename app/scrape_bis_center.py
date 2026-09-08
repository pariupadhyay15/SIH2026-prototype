STATE_MAP = {
    "Ghaziabad": "Uttar Pradesh",
    "Noida": "Uttar Pradesh",
    "Delhi": "Delhi",
    "New Delhi": "Delhi",
    "Chandigarh": "Chandigarh",
    "Mumbai": "Maharashtra",
    "Kolkata": "West Bengal",
    "Chennai": "Tamil Nadu",
    "Jaipur": "Rajasthan",
    "Lucknow": "Uttar Pradesh",
    "Bhopal": "Madhya Pradesh",
    "Dehradun": "Uttarakhand",
    "Faridabad": "Haryana",
}

import json
import re
import time
import requests
from bs4 import BeautifulSoup


TARGET_URLS = [
     "https://www.bis.gov.in/directory/regional-offices/?lang=en",
     "https://www.bis.gov.in/branch-office/?lang=en",
     "https://www.bis.gov.in/regional-branch-offices-bis-list/?lang=en"
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

def clean_email(raw_text: str) -> str:
    """Extracts and formats complete email addresses."""
    match = re.search(
        r'[\w\.-]+\s*(?:\[at\]|@)\s*[\w\.-]+\s*(?:\[dot\]|\.)\s*[\w\.-]+',
        raw_text,
    )
    if not match:
        return ""
    email = match.group(0).replace('[at]', '@').replace('[dot]', '.').replace(' ', '')
    if email.endswith('.gov'):
        email += '.in'
    return email

def extract_pincode(text: str) -> str:
    """Extracts 6-digit Indian PIN codes, handling optional space formats (e.g. 201 010)."""
    match = re.search(r'\b\d{3}\s?\d{3}\b', text)
    if match:
        return match.group(0).replace(' ', '')
    return ""

def geocode_address(address: str, city: str):
    """Uses OpenStreetMap Nominatim API to fetch exact Latitude and Longitude."""
    query = f"{city}, India" if city else address
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 1}
    headers = {"User-Agent": "BISSahayakLocator/1.0"}

    try:
        res = requests.get(url, params=params, headers=headers, timeout=5)
        data = res.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print(f"Geocoding error for {query}: {e}")

    return None, None

def determine_centre_type(name: str) -> str:
    """Categorizes the centre type based on the official title."""
    name_lower = name.lower()
    if "regional office" in name_lower or "region office" in name_lower:
        return "Regional Office"
    elif "headquarter" in name_lower or "head quarter" in name_lower:
        return "Headquarters"
    elif "lab" in name_lower or "laboratory" in name_lower:
        return "Testing Laboratory"
    return "Branch Office"

def is_valid_centre_name(name: str) -> bool:
    """Filters out navigation bar menus and header text junk."""
    name_clean = name.strip()
    if len(name_clean) < 4:
        return False
    # Drop rows that are just lists of city abbreviations from navigation lists
    if name_clean.count("BO") > 2 or name_clean.count("DLBO") > 1:
        return False
    if "main menu" in name_clean.lower() or "directory" in name_clean.lower():
        return False
    return True

def scrape_and_build_dataset():
    all_records = []
    seen_names = set()

    for target_url in TARGET_URLS:
        print(f"\n[+] Fetching URL: {target_url}")
        try:
            response = requests.get(target_url, headers=HEADERS, timeout=10)
            if response.status_code != 200:
                print(f"Failed to fetch {target_url} (Status: {response.status_code})")
                continue

            soup = BeautifulSoup(response.content, "html.parser")
            tables = soup.find_all("table")

            if not tables:
                print(f"No <table> elements found on {target_url}")
                continue

            for table in tables:
                rows = table.find_all("tr")
                if not rows:
                    continue

                for row in rows[1:]:  # Skip header row
                    cols = row.find_all("td")
                    if len(cols) < 2:
                        continue

                    name = cols[0].get_text(" ", strip=True)
                    if not is_valid_centre_name(name) or name in seen_names:
                        continue

                    raw_address = cols[1].get_text(" ", strip=True)
                    contact_text = (
                        cols[3].get_text(" ", strip=True)
                        if len(cols) > 3
                        else cols[-1].get_text(" ", strip=True)
                    )

                    email = clean_email(contact_text)

                    # Extract Phone Number
                    phone_match = re.search(
                        r"(?:Tel\s*:\s*|\+?91[\s-]*)?[\d\s,-]{8,20}", contact_text
                    )
                    phone = phone_match.group(0).strip() if phone_match else ""

                    pincode = extract_pincode(raw_address)
                    centre_type = determine_centre_type(name)

                    # Extract City Name
                    city_match = re.search(r"([A-Za-z]+)\s*-\s*\d{6}", raw_address)
                    if city_match:
                        city = city_match.group(1).strip()
                    else:
                        city = (
                            name.replace("Branch Office", "")
                            .replace("Regional Office", "")
                            .replace("Office", "")
                            .strip()
                        )

                    print(f"-> Processing: {name} | City: {city}")
                    lat, lon = geocode_address(raw_address, city)

                    # Respect OpenStreetMap rate limit (1 request per second)
                    time.sleep(1)

                    record = {
                        "name": name,
                        "centre_type": centre_type,
                        "address": raw_address,
                        "city": city,
                        "state": STATE_MAP.get(city, ""),
                        "pincode": pincode,
                        "latitude": lat,
                        "longitude": lon,
                        "phone": phone,
                        "email": email,
                        "services": [
                            "Standards Information",
                            "Certification Services",
                            "Public Grievances",
                        ],
                    }
                    all_records.append(record)
                    seen_names.add(name)

        except Exception as e:
            print(f"Error scraping {target_url}: {e}")

    # Save to final JSON file
    with open("complete_bis_centres.json", "w", encoding="utf-8") as f:
        json.dump(all_records, f, indent=2)

    print(
        f"\n[✔] Finished! Saved {len(all_records)} clean records to"
        " 'complete_bis_centres.json'."
    )

if __name__ == "__main__":
    scrape_and_build_dataset()