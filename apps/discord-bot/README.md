# Winton-s-Corner-Bot

A Discord bot with Overwatch leaderboard tracking and invite conversion analytics.

## Features

- 🏆 Overwatch leaderboard tracking
- 📊 Discord invite conversion tracking with PostHog analytics
- 🎤 Dynamic voice channel creation
- 📈 Real-time conversion metrics

## Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Winton-s-Corner-Bot
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   
   Copy `.env.example` to `.env` and fill in your values:
   ```bash
   cp .env.example .env
   ```

   Required variables:
   - `TOKEN`: Your Discord bot token
   - `BOT_DEV_GUILDS`: Your Discord guild ID(s)
   - `MONGO_URI`: MongoDB connection string
   - `POSTHOG_API_KEY`: Your PostHog API key (optional)
   - `POSTHOG_HOST`: PostHog host URL (default: https://app.posthog.com)
   - `TARGET_INVITE_CODE`: The invite code to track (default: GbjrfMQey2)

5. **Run with Docker (Recommended)**
   ```bash
   docker-compose up -d
   ```

   Or run locally:
   ```bash
   python src/main.py
   ```

## Invite Conversion Tracking

The bot automatically tracks when users join via specific Discord invites and sends conversion events to PostHog.

### How it works:

1. Bot caches all server invites on startup
2. When a user joins, it compares invite usage to detect which invite was used
3. Stores join data in MongoDB (`invite_joins` collection)
4. If the invite matches `TARGET_INVITE_CODE`, sends conversion event to PostHog

### PostHog Events

**Event Name:** `discord_invite_conversion`

**Properties:**
- `invite_code`: The Discord invite code used
- `username`: Discord username
- `platform`: "discord"
- `guild_name`: Server name
- `account_age_days`: Age of the Discord account
- `is_bot`: Whether the user is a bot

### Commands

- `/invite_stats [invite_code]` - View statistics for a specific invite code

### Required Bot Permissions

- `Manage Server` (to access invite information)
- `Manage Channels` (for voice channel features)
- `View Channels`
- `Send Messages`

## MongoDB Collections

- `invite_joins`: Stores all member joins with invite information
- Other collections used by leaderboard features

## Development

```bash
source venv/bin/activate
```
