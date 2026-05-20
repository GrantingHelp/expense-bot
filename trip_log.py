import json
import os
import shutil
from datetime import datetime

TRIP_LOG_FILE = "trip_log.json"
PHOTOS_DIR = "photos"

def load_log() -> dict:
    if os.path.exists(TRIP_LOG_FILE):
        with open(TRIP_LOG_FILE, "r") as f:
            return json.load(f)
    return {"trips": {}, "current_trip": None, "last_trip": None}

def save_log(log: dict):
    with open(TRIP_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)

def start_trip(trip_name: str = None) -> str:
    log = load_log()
    trip_id = datetime.now().strftime("%Y%m%d_%H%M")
    if not trip_name:
        trip_name = f"Trip {trip_id}"
    trip_photo_dir = os.path.join(PHOTOS_DIR, trip_id)
    os.makedirs(trip_photo_dir, exist_ok=True)
    log["trips"][trip_id] = {
        "name": trip_name,
        "started": datetime.now().isoformat(),
        "receipts": [],
        "site_codes": {}
    }
    log["current_trip"] = trip_id
    save_log(log)
    return trip_id

def get_current_trip() -> str:
    log = load_log()
    return log.get("current_trip")

def get_last_trip() -> str:
    log = load_log()
    return log.get("last_trip")

def add_receipt(receipt_data: dict, sites: list = None, temp_photo_path: str = None):
    log = load_log()
    trip_id = log.get("current_trip")
    if not trip_id:
        trip_id = start_trip()
        log = load_log()

    receipt_index = len(log["trips"][trip_id]["receipts"]) + 1
    permanent_photo_path = None

    if temp_photo_path and os.path.exists(temp_photo_path):
        ext = os.path.splitext(temp_photo_path)[1]
        permanent_photo_path = os.path.join(
            PHOTOS_DIR,
            trip_id,
            f"receipt_{receipt_index:03d}{ext}"
        )
        shutil.move(temp_photo_path, permanent_photo_path)
        if os.path.exists(temp_photo_path) and temp_photo_path != permanent_photo_path:
            os.remove(temp_photo_path)

    receipt_data["SITES"] = sites if sites else []
    receipt_data.pop("SITE", None)
    receipt_data.pop("POLICY", None)
    receipt_data["logged_at"] = datetime.now().isoformat()
    receipt_data["photo_path"] = permanent_photo_path
    receipt_data["receipt_index"] = receipt_index

    log["trips"][trip_id]["receipts"].append(receipt_data)
    save_log(log)

def add_site_code(code: str, description: str = ""):
    log = load_log()
    trip_id = log.get("current_trip")
    if not trip_id:
        trip_id = start_trip()
        log = load_log()
    log["trips"][trip_id]["site_codes"][code] = {
        "description": description,
        "added_at": datetime.now().isoformat()
    }
    save_log(log)

def update_receipt_sites(trip_id: str, receipt_index: int, sites: list):
    log = load_log()
    if trip_id not in log["trips"]:
        return
    for receipt in log["trips"][trip_id]["receipts"]:
        if receipt.get("receipt_index") == receipt_index:
            receipt["SITES"] = sites
            receipt.pop("SITE", None)
            receipt.pop("POLICY", None)
            break
    save_log(log)

def get_unassigned_receipts(trip_id: str) -> list:
    log = load_log()
    if trip_id not in log["trips"]:
        return []
    return [
        r for r in log["trips"][trip_id]["receipts"]
        if not r.get("SITES")
    ]

def get_assigned_receipts(trip_id: str) -> list:
    log = load_log()
    if trip_id not in log["trips"]:
        return []
    return [
        r for r in log["trips"][trip_id]["receipts"]
        if r.get("SITES")
    ]

def get_trip_summary(trip_id: str = None) -> dict:
    log = load_log()
    if not trip_id:
        trip_id = log.get("current_trip")
    if not trip_id or trip_id not in log["trips"]:
        return None
    return log["trips"][trip_id]

def update_trip_name(trip_id: str, name: str):
    log = load_log()
    if trip_id not in log["trips"]:
        return
    log["trips"][trip_id]["name"] = name
    save_log(log)

def end_trip():
    log = load_log()
    log["last_trip"] = log.get("current_trip")
    log["current_trip"] = None
    save_log(log)