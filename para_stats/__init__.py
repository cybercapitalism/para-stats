import pickle
import json
from config import Config
from .api_fetch import APIFetch
from .transform import TransformData
from .db import DatabaseLoader

DEBUG = True
WRITE_TO_CACHE = False

def init_script(start_round_id: int, end_round_id: int):
    responses = fetch_rounds(start_round_id, end_round_id)
    prepped_round_list = prep_rounds(responses)
    upload = load_rounds(prepped_round_list)
    print(upload)

def update_db_metadata():
    """TODO: this needs to build the whole thing once and then just look up against local storage"""
    fetcher = APIFetch()
    metadata_list = fetcher.fetch_all_metadata()
    db = DatabaseLoader(Config)
    upload = db.db_upload_metadata(metadata_list)
    print(upload)

def fetch_rounds(start_round_id: int, end_round_id: int) -> tuple:
    fetcher = APIFetch()
    response_tuple = fetcher.concurrent_whole_round_batch(start_round_id, end_round_id)

    # hmm yes give me several hundred megabytes of text please
    if WRITE_TO_CACHE:
        with open("data/raw/metadata_cache.json", 'w') as f:
            json.dump(response_tuple[0], f)

        with open("data/raw/playercount_cache.json", 'w') as f:
            json.dump(response_tuple[1], f)

        with open("data/raw/blackbox_cache.json", 'w') as f:
            json.dump(response_tuple[2], f)

    return response_tuple


def prep_rounds(endpoint_responses: tuple) -> list:
    transform_data = TransformData()
    collected_round_list = transform_data.collect_round_batch(*endpoint_responses)

    if WRITE_TO_CACHE:
        with open("data/processed/processed_rounds_cache.json", 'w') as f:
            json.dump(collected_round_list, f)

    return collected_round_list


def load_rounds(round_list: list) -> str:
    db = DatabaseLoader(Config)
    rounds_upload = db.upload_round_list(round_list)

    return rounds_upload


def read_raw_caches() -> tuple:
    with open("data/raw/metadata_cache.json") as f:
        metadata_raw = json.load(f)
    with open("data/raw/playercount_cache.json") as f:
        playercount_raw = json.load(f)
    with open("data/raw/blackbox_cache.json") as f:
        blackbox_raw = json.load(f)
    
    return (metadata_raw, playercount_raw, blackbox_raw)

"""
---------------------------
        pickle debug
---------------------------
"""


def debug_write(round_list, fpath):
    if not DEBUG:
        return None
    with open(fpath, "wb") as f:
        pickle.dump(round_list, f)
    print("DEBUG::pickled rounds list to", fpath)


def debug_load(fpath):
    if not DEBUG:
        return None
    with open(fpath, "rb") as f:
        result = pickle.load(f)
    print("DEBUG::deserialized from", fpath)
    return result
