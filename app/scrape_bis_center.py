import json
import re
import time
import requests
from bs4 import BeautifulSoup

TARGET_URLS = [
    "https://www.bis.gov.in/directory/regional-offices/?lang=en",
    "https://www.bis.gov.in/branch-office/?lang=en",
    "https://www.bis.gov.in/regional-branch-offices-bis-list/?lang=en",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

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


INDIA_LAT_MIN, INDIA_LAT_MAX = 6.0, 37.0
INDIA_LON_MIN, INDIA_LON_MAX = 68.0, 97.0


def clean_email(raw_text: str) -> str:
  match = re.search(
      r'[\w\.-]+\s*(?:\[at\]|@)\s*[\w\.-]+\s*(?:\[dot\]|\.)\s*[\w\.-]+',
      raw_text,
  )
  if not match:
    return ''
  email = match.group(0).replace('[at]', '@').replace('[dot]', '.').replace(' ', '')
  if email.endswith('.gov'):
    email += '.in'
  return email.lower()


def clean_phone(raw_text: str) -> str:
  match = re.search(
      r'(?:Tel\s*:\s*|\+?91[\s-]*)?([\d\s,-]{8,20})', raw_text, re.IGNORECASE
  )
  if match:
    cleaned = re.sub(r'[^\d,-]', '', match.group(1)).strip()
    return cleaned if len(cleaned) >= 8 else ''
  return ''


def extract_pincode(text: str) -> str:
  match = re.search(r'\b\d{3}\s?\d{3}\b', text)
  return match.group(0).replace(' ', '') if match else ''


def is_valid_india_coords(lat: float, lon: float) -> bool:
  """Validates if coordinates fall within India's geographic bounding box."""
  if lat is None or lon is None:
    return False
  return (
      INDIA_LAT_MIN <= lat <= INDIA_LAT_MAX
      and INDIA_LON_MIN <= lon <= INDIA_LON_MAX
  )


def geocode_address(address: str, city: str):
  """Uses Nominatim API to fetch and validate GPS coordinates for India."""
  query = f'{city}, India' if city else address
  url = 'https://nominatim.openstreetmap.org/search'
  params = {'q': query, 'format': 'json', 'limit': 1}
  headers = {'User-Agent': 'BISSahayakLocator/1.0'}

  try:
    res = requests.get(url, params=params, headers=headers, timeout=5)
    data = res.json()
    if data:
      lat = float(data[0]['lat'])
      lon = float(data[0]['lon'])
      if is_valid_india_coords(lat, lon):
        return lat, lon
  except Exception as e:
    print(f'Geocoding error for {query}: {e}')

  return None, None


def determine_centre_type(name: str) -> str:
  name_lower = name.lower()
  if 'regional office' in name_lower or 'region office' in name_lower:
    return 'Regional Office'
  elif 'headquarter' in name_lower or 'head quarter' in name_lower:
    return 'Headquarters'
  elif 'lab' in name_lower or 'laboratory' in name_lower:
    return 'Testing Laboratory'
  return 'Branch Office'


def is_valid_centre_name(name: str) -> bool:
  name_clean = name.strip()
  if len(name_clean) < 4:
    return False
  if name_clean.count('BO') > 2 or name_clean.count('DLBO') > 1:
    return False
  if 'main menu' in name_clean.lower() or 'directory' in name_clean.lower():
    return False
  return True


def scrape_and_build_dataset():
  all_records = []
  seen_entries = set()

  for target_url in TARGET_URLS:
    print(f'\n[+] Fetching URL: {target_url}')
    try:
      response = requests.get(target_url, headers=HEADERS, timeout=10)
      if response.status_code != 200:
        continue

      soup = BeautifulSoup(response.content, 'html.parser')
      tables = soup.find_all('table')

      for table in tables:
        rows = table.find_all('tr')
        if not rows:
          continue

        for row in rows[1:]:
          cols = row.find_all('td')
          if len(cols) < 2:
            continue

          name = cols[0].get_text(' ', strip=True)
          if not is_valid_centre_name(name):
            continue

          raw_address = cols[1].get_text(' ', strip=True)
          contact_text = (
              cols[3].get_text(' ', strip=True)
              if len(cols) > 3
              else cols[-1].get_text(' ', strip=True)
          )

          
          unique_key = f'{name}_{raw_address[:15]}'
          if unique_key in seen_entries:
            continue

          email = clean_email(contact_text)
          phone = clean_phone(contact_text)
          pincode = extract_pincode(raw_address)
          centre_type = determine_centre_type(name)

          
          city_match = re.search(r'([A-Za-z]+)\s*-\s*\d{6}', raw_address)
          if city_match:
            city = city_match.group(1).strip()
          else:
            city = (
                name.replace('Branch Office', '')
                .replace('Regional Office', '')
                .replace('Office', '')
                .strip()
            )

          state = STATE_MAP.get(city, '')
          lat, lon = geocode_address(raw_address, city)
          time.sleep(1)  

          record = {
    "name": name,
    "centre_type": centre_type,
    "address": raw_address,
    "city": city,
    "state": state,
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
          seen_entries.add(unique_key)

    except Exception as e:
      print(f'Error scraping {target_url}: {e}')

  with open('complete_bis_centres.json', 'w', encoding='utf-8') as f:
    json.dump(all_records, f, indent=2)

  print(f'\n[✔] Final dataset saved: {len(all_records)} records.')


if __name__ == '__main__':
  scrape_and_build_dataset()