# Conversion Tracking Setup Guide

## Overview
This guide explains the new Discord invite conversion tracking feature that has been added to Winton-s-Corner-Bot.

## What Was Added

### 1. New Dependencies
- **PostHog Python SDK** (`posthog==3.7.4`) for analytics tracking

### 2. New Files
- `src/posthog_tracker.py` - PostHog integration module
- `.env.example` - Environment variable template

### 3. Modified Files
- `src/main.py` - Added invite tracking and conversion events
- `requirements.txt` - Added PostHog dependency
- `README.md` - Updated documentation

## Features Implemented

### Automatic Invite Tracking
- Bot caches all Discord invites when it starts
- Detects which invite code was used when a member joins
- Stores all join events in MongoDB (`invite_joins` collection)

### PostHog Conversion Events
- Automatically sends conversion events to PostHog when users join via target invite (`GbjrfMQey2`)
- Event name: `discord_invite_conversion`
- Includes user metadata: username, guild, account age, bot status

### New Slash Command
- `/invite_stats [invite_code]` - View statistics for any invite code
  - Shows total joins, unique users, bot count
  - Displays 5 most recent joins with timestamps

## Setup Instructions

### 1. Install New Dependencies

If using Docker (recommended):
```bash
docker-compose down
docker-compose build
docker-compose up -d
```

If running locally:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Add these to your `.env` file:

```bash
# PostHog Configuration (Required for conversion tracking)
POSTHOG_API_KEY=your_posthog_project_api_key
POSTHOG_HOST=https://app.posthog.com

# Invite Tracking Configuration (Optional - defaults to GbjrfMQey2)
TARGET_INVITE_CODE=GbjrfMQey2
```

**Note:** If `POSTHOG_API_KEY` is not set, the bot will still work but conversion events won't be sent to PostHog. Join data will still be stored in MongoDB.

### 3. Update Bot Permissions

Ensure your Discord bot has the **"Manage Server"** permission to access invite information:
1. Go to Discord Developer Portal
2. Select your application
3. Go to "Bot" section
4. Enable "Manage Server" permission
5. Re-invite the bot to your server with updated permissions

### 4. Get Your PostHog API Key

1. Log in to PostHog (app.posthog.com or your self-hosted instance)
2. Go to Project Settings
3. Copy your "Project API Key"
4. Add it to your `.env` file

### 5. Restart the Bot

```bash
docker-compose restart
# or
python src/main.py
```

## How to Use

### Viewing Conversion Data in PostHog

1. Log in to PostHog
2. Go to "Events" or "Insights"
3. Filter for event: `discord_invite_conversion`
4. You'll see all conversions with properties:
   - `invite_code`
   - `username`
   - `guild_name`
   - `account_age_days`
   - `is_bot`

### Viewing Stats in Discord

Use the `/invite_stats` command:
```
/invite_stats GbjrfMQey2
```

This shows:
- Total joins via that invite
- Number of unique users (excluding bots)
- Number of bots
- 5 most recent joins

### MongoDB Data

All join events are stored in the `invite_joins` collection with this structure:
```json
{
  "user_id": "123456789",
  "username": "JohnDoe",
  "discriminator": "1234",
  "invite_code": "GbjrfMQey2",
  "guild_id": "987654321",
  "guild_name": "My Server",
  "joined_at": "ISODate(...)",
  "created_at": "ISODate(...)",
  "is_bot": false
}
```

## Tracking Multiple Invites

To track conversions for a different invite code:
1. Update `TARGET_INVITE_CODE` in your `.env` file
2. Restart the bot

To track multiple invites simultaneously, modify the code in `src/main.py`:
```python
# Change from:
if invite_code == TARGET_INVITE_CODE:
    posthog_tracker.track_conversion(...)

# To:
TRACKED_INVITES = ['GbjrfMQey2', 'AnotherCode']
if invite_code in TRACKED_INVITES:
    posthog_tracker.track_conversion(...)
```

## Troubleshooting

### "Could not determine invite used by {member.name}"
- This happens when:
  - Bot doesn't have "Manage Server" permission
  - Invite was deleted
  - Member joined through vanity URL or discovery
  - Multiple invites were used simultaneously

### "PostHog not initialized"
- Check that `POSTHOG_API_KEY` is set in `.env`
- Verify the API key is correct
- Check PostHog host URL if self-hosting

### No invites cached on startup
- Ensure bot has "Manage Server" permission
- Check bot logs for permission errors

## Next Steps

1. Set up PostHog dashboards to visualize conversion data
2. Create funnels: Page View → Discord Join
3. Set up alerts for conversion milestones
4. Analyze conversion rates by time period

## Support

For issues or questions:
1. Check bot logs: `docker-compose logs -f bot`
2. Verify environment variables are set correctly
3. Ensure bot has proper Discord permissions
