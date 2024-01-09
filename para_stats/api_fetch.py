import logging
import time
import requests
from functools import partial
from typing import List, Dict
from .adapter import SessionAdapter
from concurrent.futures import ThreadPoolExecutor


class APIFetch:
    def __init__(self) -> None:
        self._log = logging.getLogger(__name__)
        self._adapter = SessionAdapter()

    def __fetch_roundlist_paged(self, offset_start: int, offset_end: int) -> List:
        """Generator for paginated retrieval of roundlist endpoint. Will return overlapping data."""

        def fetch_single_page(offset: int) -> List:
            return self._adapter.get(f"/roundlist?offset={offset}")

        result = fetch_single_page(offset_start)
        yield result

        while result[-1]["round_id"] > offset_end:
            result = fetch_single_page(result[-1]["round_id"])
            yield result

    def fetch_roundlist_batch(self, offset_start: int, offset_end: int) -> List:
        rounds_list = []

        for result in self.__fetch_roundlist_paged(offset_start, offset_end):
            rounds_list += result

        return rounds_list

    def fetch_blackbox(self, round_id: int) -> List:
        """Fetch blackbox stats for a single round. `raw_data` is processed on hand."""
        result = self._adapter.get(f"/blackbox/{round_id}")

        return result

    def fetch_playercounts(self, round_id: int) -> Dict[str, int]:
        """Returns playercount timestamps for `round_id`"""
        result = self._adapter.get(f"/playercounts/{round_id}")

        return result

    def fetch_metadata(self, round_id: int) -> Dict:
        """Returns metadata stats for `round_id`. This returns the same information as the roundlist endpoint."""
        result = self._adapter.get(f"/metadata/{round_id}")

        return result

    def fetch_single_round(self, round_id: int) -> Dict:
        """Debug method, needs refactoring in the future."""
        round_metadata = self.fetch_metadata(round_id)
        round_blackbox = self.fetch_blackbox(round_id)
        round_playercounts = self.fetch_playercounts(round_id)

        round_metadata["playercounts"] = round_playercounts
        round_metadata["stats"] = round_blackbox

        return [round_metadata]

    def fetch_whole_round_batch(self, offset_start: int, offset_end: int) -> tuple:
        """Get all queryable information from the most recent to the target `offset_end` round."""

        self._log.info("Starting whole round batch fetch")

        # grab the rounds we'll need to query and then get the rest of their info after
        round_metadata_list = self.fetch_roundlist_batch(offset_start, offset_end)
        valid_round_ids = [r["round_id"] for r in round_metadata_list]
        self._log.info(f"Metadata retrieved successfully with length {len(round_metadata_list)}")

        blackbox_list = [self.fetch_blackbox(r) for r in valid_round_ids]
        self._log.info(f"Blackbox data retrieved successfully with length {len(blackbox_list)}")

        playercount_list = [self.fetch_playercounts(r) for r in valid_round_ids]
        self._log.info(f"Playercount data retrieved successfully with length {len(playercount_list)}")

        return (round_metadata_list, playercount_list, blackbox_list)

    def get_most_recent_round_id(self):
        return self._adapter.get("/roundlist?offset=0")[0]["round_id"]


# --------------- do not cross, bad juju ahead ---------------

    def concurrent_whole_round_batch(self, offset_start: int, offset_end: int) -> Dict:
        self._log.info("Starting concurrent get...")

        # TODO: pretty sure a generator expression is going to shit itself if we try to multithread it - have to test
        round_metadata_list = self.fetch_roundlist_batch(0, offset_end)

        self._log.info("Got metadata list of len", len(round_metadata_list))

        round_id_list = [r["round_id"] for r in round_metadata_list]
        test_pcount_urls = ["/playercounts/" + str(i) for i in round_id_list]
        test_blackbox_urls = ["/blackbox/" + str(i) for i in round_id_list]

        playercount_list, raw_blackbox_list = self.__concurrent_fetch_list(test_pcount_urls, test_blackbox_urls)

        cleaned_blackbox_list = [self.clean_blackbox_response(i) for i in raw_blackbox_list]
        self._log.info("Successfully got playercount and blackbox lists with lens:", len(playercount_list), len(cleaned_blackbox_list))

        return (round_metadata_list, playercount_list, cleaned_blackbox_list)
    
    def __concurrent_fetch_list(self, playercount_urls, blackbox_urls):
        CONNECTIONS = 2
        # TODO: needs to not be urls, just endpoints :)
        self._log.info("Starting concurrent session pool with url lists of len:", len(playercount_urls), len(blackbox_urls))

        with requests.Session() as session:
            with ThreadPoolExecutor(max_workers=CONNECTIONS) as pool:
                playercount_list = list(pool.map(partial(self._adapter.concurrent_get, session), playercount_urls))
                raw_blackbox_list = list(pool.map(partial(self._adapter.concurrent_get, session), blackbox_urls))

        return playercount_list, raw_blackbox_list