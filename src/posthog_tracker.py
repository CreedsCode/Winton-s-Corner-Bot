import os
from posthog import Posthog
from typing import Optional

_posthog_client = None


def init():
    """Initialize PostHog client"""
    global _posthog_client
    
    api_key = os.getenv('POSTHOG_API_KEY')
    host = os.getenv('POSTHOG_HOST', 'https://app.posthog.com')
    
    if not api_key:
        print("Warning: POSTHOG_API_KEY not set. PostHog tracking disabled.")
        return
    
    _posthog_client = Posthog(project_api_key=api_key, host=host)
    print("PostHog initialized successfully")


def track_conversion(user_id: str, username: str, invite_code: str, properties: Optional[dict] = None):
    """
    Track a conversion event when a user joins via a specific invite
    
    Args:
        user_id: Discord user ID
        username: Discord username
        invite_code: The invite code used to join
        properties: Additional properties to track
    """
    if _posthog_client is None:
        print(f"PostHog not initialized. Would track conversion: {username} via {invite_code}")
        return
    
    event_properties = {
        'invite_code': invite_code,
        'username': username,
        'platform': 'discord',
        **(properties or {})
    }
    
    try:
        _posthog_client.capture(
            distinct_id=user_id,
            event='discord_invite_conversion',
            properties=event_properties
        )
        print(f"Tracked conversion: {username} (ID: {user_id}) via invite {invite_code}")
    except Exception as e:
        print(f"Error tracking conversion to PostHog: {e}")


def shutdown():
    """Shutdown PostHog client"""
    global _posthog_client
    
    if _posthog_client is not None:
        _posthog_client.shutdown()
        _posthog_client = None
