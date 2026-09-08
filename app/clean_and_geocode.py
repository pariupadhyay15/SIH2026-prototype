import json
import re
import time
from geopy.geocoders import Nominatim


geolocator = Nominatim(user_agent="bis_centre_cleaner")

INPUT_FILE = "complete_bis_centres.json"
OUTPUT_FILE = "complete_bis_centres.json"


def clean_text(text: str) -> str:
  """Removes line breaks, emails, phone numbers, and extra spaces from strings."""
  if not text:
    return ""

  text = re.sub(
      r"[a-zA-Z0-9._%+-]+\[at\][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "", text
  )
  text = re.sub(r"Tel\s*:\s*[\d\s,-]+", "", text, flags=re.IGNORECASE)
  text = re.sub(r"\s+", " ", text)
  return text.strip()


def extract_clean_city(centre: dict) -> str:
  """Extracts a simple, single-word/two-word city name."""
  name = centre.get("name", "")
  city = centre.get("city", "")


  if len(city) > 30 or "Tel" in city or "Plot" in city:
    for word in [
        "Bangalore",
        "Bengaluru",
        "Kolkata",
        "Chandigarh",
        "Chennai",
        "Mumbai",
        "Delhi",
        "Ghaziabad",
        "Patna",
        "Mohali",
        "Guwahati",
        "Hyderabad",
        "Pune",
        "Bhopal",
        "Jaipur",
        "Lucknow",
        "Noida",
    ]:
      if word.lower() in (name + " " + city).lower():
        return word
    return "Unknown"
  return clean_text(city)


def geocode_centre(address: str, city: str):
  """Attempts to fetch precise (lat, lon) using OpenStreetMap."""
  search_query = f"{city}, India" if city != "Unknown" else f"{address}, India"
  try:
    location = geolocator.geocode(search_query, timeout=10)
    if location:
      return round(location.latitude, 7), round(location.longitude, 7)
  except Exception as e:
    print(f"Geocoding error for {search_query}: {e}")
  return None, None


def main():
  print("Starting automatic dataset cleaning and geocoding...")

  with open(INPUT_FILE, "r", encoding="utf-8") as f:
    centres = json.load(f)

  cleaned_count = 0
  geocoded_count = 0

  for centre in centres:
    
    centre["name"] = clean_text(centre.get("name", ""))
    centre["address"] = clean_text(centre.get("address", ""))
    centre["city"] = extract_clean_city(centre)


    c_lat = centre.get("latitude")
    c_lon = centre.get("longitude")

    if c_lat is None or c_lon is None:
      print(f"Fetching coordinates for: {centre['name']} ({centre['city']})...")
      new_lat, new_lon = geocode_centre(centre["address"], centre["city"])

      if new_lat and new_lon:
        centre["latitude"] = new_lat
        centre["longitude"] = new_lon
        geocoded_count += 1
        print(f" -> Found: {new_lat}, {new_lon}")
      else:
        print(f" -> Could not automatically locate {centre['name']}")

   
      time.sleep(1)

    cleaned_count += 1

 
  with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(centres, f, indent=2, ensure_ascii=False)

  print("\n--- Cleaning Complete ---")
  print(f"Total centres processed: {cleaned_count}")
  print(f"Missing coordinates fixed: {geocoded_count}")
  print(f"Updated file saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
  main()