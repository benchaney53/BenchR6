# R6 Siege Discord Bot

A Discord bot that automatically assigns roles based on player ranks in Rainbow Six Siege.

## Features

- **Automatic Rank Roles**: Assigns roles based on R6 player rank
- **Account Linking**: Link Discord accounts to R6 usernames
- **Hourly Updates**: Automatically checks and updates ranks every hour
- **Manual Updates**: Admin command to manually trigger updates
- **Admin Logging**: Dedicated channel for tracking all bot actions
- **Auto-role on Join**: Assigns cached roles when members rejoin the server
- **Tracker.gg Integration**: Pulls ranks from Tracker Network's Rainbow Six Siege API

## Setup Instructions

### 1. Prerequisites
- Python 3.8+
- Discord server with admin access
- Discord bot token
- **Tracker Network API key** - Free key from https://tracker.gg/developers

### 2. Installation

```bash
# Clone or download the bot files
# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

**Create `.env` file** (copy from `.env.example`):
```
DISCORD_BOT_TOKEN=your_discord_bot_token_here
TRACKER_API_KEY=your_tracker_network_api_key
```

**Edit `config.json`**:
```json
{
  "guild_id": YOUR_SERVER_ID_HERE,
  ...
}
```

### 4. Getting a Tracker Network API Key

1. Visit https://tracker.gg/developers
2. Sign in and create an application
3. Copy the **API Key** from the application page
4. Paste it into your `.env` file as `TRACKER_API_KEY`

```bash
python bot.py
```

### 5. Initial Setup

1. Run `!setup` in your Discord server (requires admin)
2. This will create:
   - All rank roles (Bronze 1-3, Silver 1-3, Gold 1-3, Plat 1-3, Diamond, Champion)
   - Bot command channel (`r6-bot-commands`)
   - Admin logging channel (`r6-bot-logs`)
   - Assign "Unlinked" role to all current members

## Commands

### User Commands
- `!link [username]` - Link your Discord account to an R6 username
- `!unlink` - Unlink your Discord from your R6 account
- `!stats [username]` - View the current rank for an R6 username without linking
- `!help` - Show available commands

### Admin Commands
- `!setup` - Create all roles and channels (run once at setup)
- `!link @user [username]` - Link another user's account
- `!unlink @user` - Unlink another user
- `!update` - Manually trigger rank update for all users
- `!help` - Show admin commands

## How It Works

### Linking Process
1. User runs `!link username` in bot channel or DM
2. Bot validates the R6 username
3. If invalid, bot suggests similar usernames
4. Bot assigns rank roles (both specific hidden and general displayed roles)
5. Every hour, bot checks all linked users' current ranks
6. If rank changed, roles are updated and logged to admin channel

### Role Assignment
- **Specific Rank Role** (hidden): e.g., "Silver 3" - used internally
- **General Rank Role** (displayed): e.g., "Silver" - shown to other users
- **Unlinked Role**: Assigned to members without linked accounts
- **Unranked Role**: Assigned to linked players with no ranked games this season

### Hourly Update
- Checks all linked users' current R6 ranks
- Updates cached ranks in database
- Assigns/removes rank roles as needed
- Logs all changes to admin channel
- Monitors API rate limits

## Logging

Bot logs are stored in `logs/r6_bot.log` and also output to console. Admin channel receives embeds for all major events:
- User linked/unlinked
- Rank changes
- Setup completion
- Update cycles
- Rate limit warnings

## Troubleshooting

**Bot doesn't respond to commands:**
- Make sure bot is in the correct channel
- For DMs, ensure bot has DM permissions enabled

**"Failed to initialize Tracker Network API" error:**
- Ensure `TRACKER_API_KEY` is present in `.env`
- Verify the key is active and associated with your Tracker application

**Invalid username errors:**
- Double-check R6 username spelling (case-sensitive)
- Make sure the player account exists on Tracker Network
- The account must have played at least one ranked match this season

**Members not getting roles on join:**
- Run `!setup` again if channels don't exist
- Check bot has "Manage Roles" permission
- Verify roles exist in the server

**Rank updates not working:**
- Verify the R6 username is correct and exact match
- Make sure player has played ranked matches this season
- Tracker Network data may lag slightly behind in-game updates
- Check bot logs for authentication errors

## Database

Bot uses SQLite database (`r6_bot.db`) to store:
- Discord ID ↔ R6 Username mappings
- Cached player ranks
- Data is persistent and survives bot restarts

## API

Bot uses the **Tracker Network** Rainbow Six Siege API:
- Requires a free Tracker Network developer API key
- Tracks rate limits via response headers
- Pulls season ranks from Tracker.gg player profiles

## Security Notes

- Never share your `.env` file (contains API keys)
- Bot should have admin permissions for role management
- Admin logging channel should only be visible to admins
- Bot commands restricted to specific channels for privacy

## Support

For issues or feature requests, check the bot logs and admin channel for detailed error messages.
