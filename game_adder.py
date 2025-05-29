import os
import json
import requests
import uuid
import re
import time
from pathlib import Path

# --- Configuration ---
STEAM_API_KEY = "YOUR_STEAM_API_KEY" # get a steam api key from https://steamcommunity.com/dev/apikey
STEAM_ID = "YOUR_STEAM_ID"
LENDER_IDS = ["LENDER_STEAM_ID_1", "LENDER_STEAM_ID_2"] # Replace these with the ids of your steam family members
STEAMGRIDDB_API_KEY = "YOUR_STEAMGRIDDB_API_KEY" # get a SteamGridDB api key from https://www.steamgriddb.com/api/v2
APPS_JSON_PATH = r"C:\\Program Files\\Apollo\\config\\apps.json"
COVERS_FOLDER = r"C:\\Program Files\\Apollo\\config\\covers"

# --- Utility Functions ---
def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9 \-_.]', '', name)

def get_owned_games(steam_id, api_key):
    url = f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key={api_key}&steamid={steam_id}&include_appinfo=true&include_played_free_games=true"
    while True:
        resp = requests.get(url)
        if resp.status_code == 429:
            print(f"🚫 Rate limited for Steam ID {steam_id}, retrying in 5 seconds...")
            time.sleep(5)
            continue
        resp.raise_for_status()
        return resp.json()["response"].get("games", [])

def get_existing_apps(apps_json_path):
    if not os.path.exists(apps_json_path):
        return set(), {"apps": [], "env": {}, "version": 2}
    with open(apps_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    existing_names = {app["name"] for app in data.get("apps", [])}
    return existing_names, data

def fetch_cover_image(game_name, appid):
    headers = {"Authorization": f"Bearer {STEAMGRIDDB_API_KEY}"}
    search = requests.get(f"https://www.steamgriddb.com/api/v2/search/autocomplete/{game_name}", headers=headers)
    if search.status_code != 200 or not search.json().get("data"):
        return None
    first_id = search.json()["data"][0]["id"]
    covers = requests.get(f"https://www.steamgriddb.com/api/v2/grids/game/{first_id}?dimensions=600x900", headers=headers)
    if covers.status_code != 200 or not covers.json().get("data"):
        return None
    image_url = covers.json()["data"][0]["url"]
    safe_name = sanitize_filename(game_name)
    local_filename = f"{safe_name}.png"
    local_path = os.path.join(COVERS_FOLDER, local_filename)
    img = requests.get(image_url)
    with open(local_path, "wb") as f:
        f.write(img.content)
    return local_path

def generate_app_entry(game_name, appid, image_path):
    return {
        "allow-client-commands": True,
        "auto-detach": True,
        "cmd": "",
        "detached": [f"steam://rungameid/{appid}"],
        "elevated": False,
        "exclude-global-prep-cmd": False,
        "exit-timeout": 5,
        "gamepad": "",
        "image-path": image_path,
        "name": game_name,
        "output": "",
        "per-client-app-identity": False,
        "scale-factor": 100,
        "use-app-identity": False,
        "uuid": str(uuid.uuid4()).upper(),
        "virtual-display": True,
        "wait-all": True
    }

# --- Main Logic ---
print("🎮 Fetching games from your account and shared libraries...")
all_games = get_owned_games(STEAM_ID, STEAM_API_KEY)
for lender in LENDER_IDS:
    lender_games = get_owned_games(lender, STEAM_API_KEY)
    all_games.extend(lender_games)

game_map = {game["appid"]: game["name"] for game in all_games}
existing_names, data = get_existing_apps(APPS_JSON_PATH)
Path(COVERS_FOLDER).mkdir(parents=True, exist_ok=True)

for appid, name in game_map.items():
    if name in existing_names:
        continue
    print(f"Adding {name}...")

    cover_path = fetch_cover_image(name, appid)
    if not cover_path:
        print(f"  ⚠️  Failed to get cover for {name}, skipping.") # this could fail due to special characters, haven't tested it yet
        continue

    app_entry = generate_app_entry(name, appid, cover_path)
    data["apps"].append(app_entry)

# --- Save Updated JSON ---
with open(APPS_JSON_PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4)

print("✅ Finished adding games to Apollo.")
