from typing import Dict, Union
import requests
import logging
import time
from random import uniform


class OverwatchAPIError(Exception):
    """Custom exception for Overwatch API errors"""

    def __init__(self, status_code: int, message: str, response=None):
        self.status_code = status_code
        self.message = message
        self.response = response
        super().__init__(f"API Error {status_code}: {message}")


class OverwatchAPI:
    def __init__(self):
        self.BASE_URL = "https://overfast-api.tekrop.fr"
        self.USER_AGENT = "Wintons-Corner_Bot/1.0 (https://github.com/CreedsCode/Winton-s-Corner-Bot)"

    def get_player_summary(
            self,
            player_id: str,
            max_retries: int = 3,
            initial_delay: float = 1.0,
            max_delay: float = 10.0,
            jitter: bool = True
    ) -> Union[Dict, None]:
        formated_player_id = player_id.replace('#', '-')
        retry_attempt = 0
        delay = initial_delay

        while retry_attempt <= max_retries:
            try:
                return self.__get_player_summary(formated_player_id)
            except requests.exceptions.HTTPError as e:
                retry_attempt += 1

                if e.response.status_code not in [429]:
                    logging.error(f"Non-retryable error for {player_id}: {str(e)}")
                    return None

                if retry_attempt == max_retries:
                    return None

                delay = float(e.response.headers['Retry-After']) if (
                        e.response.status_code == 429 and 'Retry-After' in e.response.headers) else (
                    min(delay * 2, max_delay))

                if jitter:
                    delay = delay * uniform(0.75, 1.25)

                logging.warning(
                    f"Attempt {retry_attempt + 1}/{max_retries} failed for {player_id}. "
                    f"Retrying in {delay:.2f}s: {str(e)}"
                )
                time.sleep(delay)
            except Exception as e:
                logging.error(f"Unexpected error for {player_id}: {str(e)}")
                return None
        return None

    def __get_player_summary(self, urlsafe_player_id: str) -> Dict:
        response = requests.get(
            f"{self.BASE_URL}/players/{urlsafe_player_id}/summary",
            headers={
                "User-Agent": self.USER_AGENT,
            })
        response.raise_for_status()
        return response.json()
