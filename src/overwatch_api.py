from typing import Dict, Optional, Union
import requests
from requests.exceptions import RequestException
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
    BASE_URL = "https://overfast-api.tekrop.fr"
    
    @staticmethod
    def get_player_summary(player_id: str) -> Dict:
        """
        Get player summary information including name, avatar, and competitive ranks.
        
        Args:
            player_id (str): Player's BattleTag with "#" replaced by "-" (case-sensitive)
                           Example: "TeKrop-2217"
        
        Returns:
            dict: Player summary information
        
        Raises:
            OverwatchAPIError: If the API request fails with a specific error
            RequestException: For general request errors (network issues, etc.)
        """
        endpoint = f"{OverwatchAPI.BASE_URL}/players/{player_id}/summary"
        
        try:
            response = requests.get(endpoint)
            
            # Handle different response status codes
            if response.status_code == 200:
                return response.json()
            
            error_messages = {
                404: "Player not found",
                422: "Invalid player ID format",
                429: "Rate limit exceeded",
                500: "Internal server error",
                504: "Blizzard server error"
            }
            
            error_message = error_messages.get(
                response.status_code, 
                f"Unexpected error: {response.text}"
            )
            raise OverwatchAPIError(response.status_code, error_message, response=response)

        except RequestException as e:
            logging.error(f"Network error while fetching player summary: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"Unknown error occurred: {e}")
            raise

def get_player_summary(
    player_id: str,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
    jitter: bool = True
) -> Union[Dict, None]:
    """
    Convenience function to get player summary without instantiating the class.
    
    Args:
        player_id (str): Player's BattleTag with "#" (will be converted to "-")
        max_retries (int): Maximum number of retry attempts (default: 3)
        initial_delay (float): Initial delay between retries in seconds (default: 1.0)
        max_delay (float): Maximum delay between retries in seconds (default: 10.0)
        jitter (bool): Add random jitter to delay to prevent thundering herd (default: True)
    
    Returns:
        dict: Player summary information if successful
        None: If there was an error and logging is enabled
    
    Example:
        >>> try:
        >>>     player_data = get_player_summary("TeKrop#2217")
        >>>     print(player_data)
        >>> except OverwatchAPIError as e:
        >>>     print(f"Error: {e.message}")
    """
    formated_id = player_id.replace('#', '-')
    attempt = 0
    delay = initial_delay

    while attempt <= max_retries:
        try:
            return OverwatchAPI.get_player_summary(formated_id)
            
        except OverwatchAPIError as e:
            # Don't retry for these status codes
            if e.status_code in [404, 422]:  # Not Found or Validation Error
                logging.error(f"Non-retryable error for {player_id}: {str(e)}")
                return None
                
            # Last attempt failed
            if attempt == max_retries:
                logging.error(f"Final retry attempt failed for {player_id}: {str(e)}")
                return None
                
            # For rate limits (429), use Retry-After header if available
            if e.status_code == 429 and hasattr(e, 'response') and 'Retry-After' in e.response.headers:
                delay = float(e.response.headers['Retry-After'])
                logging.info(f"Rate limited. Server requested wait time: {delay}s")
            else:
                # Calculate next delay with exponential backoff
                delay = min(delay * 2, max_delay)
                
                # Add jitter if enabled (±25% of delay)
                if jitter:
                    delay = delay * uniform(0.75, 1.25)
            
            logging.warning(
                f"Attempt {attempt + 1}/{max_retries} failed for {player_id}. "
                f"Retrying in {delay:.2f}s: {str(e)}"
            )
            time.sleep(delay)
            attempt += 1
            
        except Exception as e:
            logging.error(f"Network error for {player_id}: {str(e)}")
            return None