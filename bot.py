import discord
from discord.ext import commands, tasks
import os
import json
import logging
import logging.handlers
from dotenv import load_dotenv
from datetime import datetime
from typing import Optional, Tuple

from database import Database
from r6_api import R6SAPIClient

# Load environment variables
load_dotenv()

# Setup logging
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# File handler
file_handler = logging.handlers.RotatingFileHandler(
    f"{log_dir}/r6_bot.log",
    maxBytes=10485760,  # 10MB
    backupCount=5
)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Load configuration
def load_config():
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        logger.info("Config loaded successfully")
        return config
    except json.JSONDecodeError:
        logger.error("config.json is not valid JSON")
        exit(1)
    except FileNotFoundError:
        logger.error("config.json not found")
        exit(1)

CONFIG = load_config()

# Initialize bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Initialize database and API
db = Database(CONFIG['database']['path'])

# Get Ubisoft credentials
ubisoft_email = os.getenv('UBISOFT_EMAIL')
ubisoft_password = os.getenv('UBISOFT_PASSWORD')

if not ubisoft_email or not ubisoft_password:
    logger.error("UBISOFT_EMAIL and UBISOFT_PASSWORD must be set in .env")
    exit(1)

api = R6SAPIClient(ubisoft_email, ubisoft_password)

# Global variables
bot_command_channel = None
admin_logging_channel = None
guild = None

# Rank roles mapping
RANKS = {
    "unranked": "Unranked",
    "bronze-3": ("Bronze 3", "Bronze"),
    "bronze-2": ("Bronze 2", "Bronze"),
    "bronze-1": ("Bronze 1", "Bronze"),
    "silver-3": ("Silver 3", "Silver"),
    "silver-2": ("Silver 2", "Silver"),
    "silver-1": ("Silver 1", "Silver"),
    "gold-3": ("Gold 3", "Gold"),
    "gold-2": ("Gold 2", "Gold"),
    "gold-1": ("Gold 1", "Gold"),
    "platinum-3": ("Platinum 3", "Platinum"),
    "platinum-2": ("Platinum 2", "Platinum"),
    "platinum-1": ("Platinum 1", "Platinum"),
    "diamond": ("Diamond 1", "Diamond"),
    "champion": ("Champion", "Champion"),
}

async def log_to_admin(message: str):
    """Log message to admin channel"""
    if admin_logging_channel:
        embed = discord.Embed(
            description=message,
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        await admin_logging_channel.send(embed=embed)
    logger.info(message)

async def warn_rate_limit():
    """Warn in bot command channel if rate limit is approaching"""
    percentage = api.get_rate_limit_percentage()
    if percentage >= CONFIG['api']['rate_limit_warning_threshold']:
        if bot_command_channel:
            embed = discord.Embed(
                title="⚠️ Rate Limit Warning",
                description=f"API rate limit is at {percentage:.1f}%. Updates may be slower.",
                color=discord.Color.red()
            )
            await bot_command_channel.send(embed=embed)
        logger.warning(f"Rate limit at {percentage:.1f}%")

async def get_or_create_role(name: str, is_hidden: bool = False) -> discord.Role:
    """Get or create a role"""
    role = discord.utils.get(guild.roles, name=name)
    if not role:
        color = discord.Color.random()
        role = await guild.create_role(
            name=name,
            color=color,
            hoist=not is_hidden,
            reason="R6 Bot Setup"
        )
        logger.info(f"Created role: {name}")
    return role

async def get_or_create_channel(name: str, is_admin: bool = False) -> discord.TextChannel:
    """Get or create a text channel"""
    channel = discord.utils.get(guild.text_channels, name=name)
    if not channel:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False)
        }
        if is_admin:
            # Only admins can see
            admin_role = discord.utils.get(guild.roles, name="Administrator")
            overwrites[guild.default_role] = discord.PermissionOverwrite(read_messages=False)
        
        channel = await guild.create_text_channel(name, overwrites=overwrites)
        logger.info(f"Created channel: {name}")
    return channel

def normalize_rank(rank_str: str) -> str:
    """Normalize rank string to lowercase with hyphens"""
    if not rank_str:
        return "unranked"
    rank_lower = rank_str.lower().replace(" ", "-")
    return rank_lower

async def assign_rank_roles(member: discord.Member, rank: Optional[str]):
    """Assign specific and general rank roles to a member"""
    try:
        # Remove all rank roles first
        for role_name in RANKS.values():
            if isinstance(role_name, tuple):
                role_names = role_name
            else:
                role_names = (role_name,)
            
            for rn in role_names:
                role = discord.utils.get(guild.roles, name=rn)
                if role and role in member.roles:
                    await member.remove_roles(role)
        
        # Assign new rank roles
        if rank:
            normalized = normalize_rank(rank)
            if normalized in RANKS:
                role_names = RANKS[normalized]
                if isinstance(role_names, tuple):
                    for role_name in role_names:
                        role = await get_or_create_role(role_name, is_hidden=(role_name != role_names[-1]))
                        await member.add_roles(role)
                else:
                    role = await get_or_create_role(role_names)
                    await member.add_roles(role)
        else:
            # Unranked
            unranked_role = await get_or_create_role(CONFIG['roles']['unranked_name'])
            await member.add_roles(unranked_role)
    except Exception as e:
        logger.error(f"Error assigning rank roles to {member}: {e}")

async def remove_all_rank_roles(member: discord.Member):
    """Remove all rank roles from a member"""
    try:
        for role_name in RANKS.values():
            if isinstance(role_name, tuple):
                role_names = role_name
            else:
                role_names = (role_name,)
            
            for rn in role_names:
                role = discord.utils.get(guild.roles, name=rn)
                if role and role in member.roles:
                    await member.remove_roles(role)
        
        # Add unlinked role
        unlinked_role = await get_or_create_role(CONFIG['roles']['unlinked_name'])
        await member.add_roles(unlinked_role)
    except Exception as e:
        logger.error(f"Error removing rank roles from {member}: {e}")

@bot.event
async def on_ready():
    """Bot startup validation"""
    global guild, bot_command_channel, admin_logging_channel
    
    logger.info(f"Bot logged in as {bot.user}")
    
    # Authenticate with Ubisoft
    if not api.auth:
        auth_success = await api.authenticate()
        if not auth_success:
            logger.error("Failed to authenticate with Ubisoft. Exiting.")
            exit(1)
    
    # Get guild
    guild = bot.get_guild(CONFIG['guild_id'])
    if not guild:
        logger.error(f"Guild {CONFIG['guild_id']} not found")
        return
    
    # Check admin permissions
    bot_member = guild.me
    if not bot_member.guild_permissions.administrator:
        logger.error("Bot does not have admin permissions in the guild")
        return
    
    logger.info("Bot has admin permissions")
    
    # Check if channels and roles exist
    bot_command_channel = discord.utils.get(guild.text_channels, name=CONFIG['channels']['bot_commands_name'])
    admin_logging_channel = discord.utils.get(guild.text_channels, name=CONFIG['channels']['admin_logging_name'])
    
    # Log startup
    startup_message = f"Bot started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    if admin_logging_channel:
        embed = discord.Embed(
            title="✅ Bot Startup",
            description=startup_message,
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await admin_logging_channel.send(embed=embed)
    
    logger.info(startup_message)
    
    # Start hourly update task
    if not hourly_update.is_running():
        hourly_update.start()

@bot.event
async def on_member_join(member: discord.Member):
    """Assign roles when member joins"""
    global guild
    
    if member.guild.id != CONFIG['guild_id']:
        return
    
    user_data = db.get_user(member.id)
    
    if user_data:
        # User is linked, assign rank roles
        r6_username, cached_rank = user_data
        await assign_rank_roles(member, cached_rank)
        await log_to_admin(f"✅ Member {member} joined - restored rank: {cached_rank or 'Unranked'}")
    else:
        # User is not linked, assign unlinked role
        unlinked_role = await get_or_create_role(CONFIG['roles']['unlinked_name'])
        await member.add_roles(unlinked_role)
        await log_to_admin(f"📝 Member {member} joined - assigned Unlinked role")

@bot.command(name='setup')
@commands.has_permissions(administrator=True)
async def setup(ctx):
    """Create all necessary roles and channels"""
    global guild, bot_command_channel, admin_logging_channel
    
    if ctx.guild.id != CONFIG['guild_id']:
        await ctx.send("This command can only be used in the configured guild.")
        return
    
    guild = ctx.guild
    
    try:
        # Create ranks roles
        for rank_names in RANKS.values():
            if isinstance(rank_names, tuple):
                # Specific rank (hidden)
                role = await get_or_create_role(rank_names[0], is_hidden=True)
                # General rank (displayed)
                role = await get_or_create_role(rank_names[1], is_hidden=False)
            else:
                role = await get_or_create_role(rank_names)
        
        # Create unlinked role
        unlinked_role = await get_or_create_role(CONFIG['roles']['unlinked_name'])
        
        # Create channels
        bot_command_channel = await get_or_create_channel(CONFIG['channels']['bot_commands_name'])
        admin_logging_channel = await get_or_create_channel(CONFIG['channels']['admin_logging_name'], is_admin=True)
        
        # Assign unlinked role to all current members
        for member in guild.members:
            if member.bot:
                continue
            
            user_data = db.get_user(member.id)
            if not user_data:
                if unlinked_role not in member.roles:
                    await member.add_roles(unlinked_role)
        
        embed = discord.Embed(
            title="✅ Setup Complete",
            description=f"All roles and channels created successfully.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await ctx.send(embed=embed)
        await log_to_admin(f"✅ Setup completed by {ctx.author}")
        
    except Exception as e:
        logger.error(f"Error in setup: {e}")
        await ctx.send(f"❌ Error during setup: {e}")

@bot.command(name='link')
async def link(ctx, *args):
    """Link user to R6 account. Usage: !link username or !link @user username (admin only)"""
    
    # Check if command is used in bot channel or DM
    if ctx.guild and ctx.channel.id != bot_command_channel.id:
        await ctx.send(f"This command can only be used in {bot_command_channel.mention} or DMs.")
        return
    
    target_user = ctx.author
    r6_username = None
    
    # Parse arguments
    if len(args) == 1:
        # !link username
        r6_username = args[0]
    elif len(args) == 2:
        # !link @user username (admin only)
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ Only admins can link other users.")
            return
        
        # Parse user mention
        if ctx.guild and ctx.message.mentions:
            target_user = ctx.message.mentions[0]
        else:
            await ctx.send("❌ Invalid user mention.")
            return
        
        r6_username = args[1]
    else:
        await ctx.send("❌ Usage: `!link username` or `!link @user username` (admin only)")
        return
    
    if not r6_username:
        await ctx.send("❌ Please provide an R6 username.")
        return
    
    # Validate username
    if not await api.is_username_valid(r6_username):
        similar = api.get_similar_usernames(r6_username)
        embed = discord.Embed(
            title="❌ Invalid Username",
            description=f"'{r6_username}' is not a valid R6 username.",
            color=discord.Color.red()
        )
        embed.add_field(name="", value="Please try again with the correct username.", inline=False)
        await ctx.send(embed=embed)
        return
    
    # Check if target user is already linked
    existing = db.get_user(target_user.id)
    if existing and existing[0] != r6_username:
        embed = discord.Embed(
            title="⚠️ Already Linked",
            description=f"You are currently linked to `{existing[0]}`.\nDo you want to switch to `{r6_username}`?",
            color=discord.Color.orange()
        )
        embed.add_field(name="", value="Reply with `yes` or `no`", inline=False)
        await ctx.send(embed=embed)
        
        def check(message):
            return message.author == ctx.author and message.content.lower() in ['yes', 'no']
        
        try:
            response = await bot.wait_for('message', check=check, timeout=30)
            if response.content.lower() != 'yes':
                await ctx.send("Cancelled.")
                return
        except:
            await ctx.send("❌ Confirmation timed out.")
            return
    
    # Get player rank
    rank = await api.get_player_rank(r6_username)
    
    # Link user
    db.link_user(target_user.id, r6_username)
    db.update_rank(target_user.id, rank)
    
    # Assign roles
    if ctx.guild:
        member = ctx.guild.get_member(target_user.id)
        if member:
            await assign_rank_roles(member, rank)
    
    embed = discord.Embed(
        title="✅ Linked",
        description=f"Linked to R6 account: `{r6_username}`",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Current Rank", value=rank or "Unranked")
    await ctx.send(embed=embed)
    
    log_msg = f"🔗 Linked {target_user} to R6 account: {r6_username} (Rank: {rank or 'Unranked'})"
    await log_to_admin(log_msg)

@bot.command(name='unlink')
async def unlink(ctx, user: Optional[discord.User] = None):
    """Unlink from R6 account. Usage: !unlink or !unlink @user (admin only)"""
    
    # Check if command is used in bot channel or DM
    if ctx.guild and ctx.channel.id != bot_command_channel.id:
        await ctx.send(f"This command can only be used in {bot_command_channel.mention} or DMs.")
        return
    
    target_user = user if user else ctx.author
    
    # Admin only for unlinking others
    if user and not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Only admins can unlink other users.")
        return
    
    # Check if user is linked
    if not db.user_exists(target_user.id):
        await ctx.send("❌ This user is not linked.")
        return
    
    # Unlink user
    db.unlink_user(target_user.id)
    
    # Remove rank roles and assign unlinked role
    if ctx.guild:
        member = ctx.guild.get_member(target_user.id)
        if member:
            await remove_all_rank_roles(member)
    
    embed = discord.Embed(
        title="✅ Unlinked",
        description=f"Unlinked from R6 account.",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    await ctx.send(embed=embed)
    
    log_msg = f"🔓 Unlinked {target_user}"
    await log_to_admin(log_msg)

@bot.command(name='update')
@commands.has_permissions(administrator=True)
async def update(ctx):
    """Manually trigger rank update for all users"""
    
    if ctx.guild.id != CONFIG['guild_id']:
        return
    
    if ctx.guild and ctx.channel.id != bot_command_channel.id:
        await ctx.send(f"This command can only be used in {bot_command_channel.mention}.")
        return
    
    embed = discord.Embed(
        title="⏳ Updating ranks...",
        color=discord.Color.blue()
    )
    status_msg = await ctx.send(embed=embed)
    
    await log_to_admin(f"🔄 Manual update triggered by {ctx.author}")
    
    # Run update
    updated = await run_rank_update()
    
    embed = discord.Embed(
        title="✅ Rank Update Complete",
        description=f"Updated {updated} users.",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    await status_msg.edit(embed=embed)

@tasks.loop(hours=1)
async def hourly_update():
    """Hourly rank update"""
    global guild, bot_command_channel
    
    if not guild:
        return
    
    logger.info("Starting hourly rank update")
    api.reset_request_count()
    await log_to_admin("🔄 Starting hourly rank update")
    
    updated = await run_rank_update()
    
    await log_to_admin(f"✅ Hourly update complete - Updated {updated} users")
    await warn_rate_limit()

async def run_rank_update() -> int:
    """Run the rank update logic"""
    global guild
    
    updated_count = 0
    users = db.get_all_users()
    
    for discord_id, r6_username, cached_rank in users:
        # Get current rank from API
        current_rank = await api.get_player_rank(r6_username)
        
        # Check if rank changed
        if current_rank != cached_rank:
            # Update database
            db.update_rank(discord_id, current_rank)
            updated_count += 1
            
            # Update member roles
            member = guild.get_member(discord_id)
            if member:
                await assign_rank_roles(member, current_rank)
                await log_to_admin(
                    f"📊 Updated {member} rank: {cached_rank or 'Unranked'} → {current_rank or 'Unranked'}"
                )
    
    # Check for unlinked members
    for member in guild.members:
        if member.bot:
            continue
        
        if not db.user_exists(member.id):
            # Check if they have the unlinked role
            unlinked_role = discord.utils.get(guild.roles, name=CONFIG['roles']['unlinked_name'])
            if unlinked_role and unlinked_role not in member.roles:
                await member.add_roles(unlinked_role)
    
    return updated_count

@bot.command(name='help')
async def help_command(ctx):
    """Show available commands"""
    
    if ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            title="R6 Bot - Admin Commands",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="!setup",
            value="Create all roles and channels (admin only)",
            inline=False
        )
        embed.add_field(
            name="!link [username]",
            value="Link your Discord to an R6 account",
            inline=False
        )
        embed.add_field(
            name="!link @user [username]",
            value="Link another user's Discord to an R6 account (admin only)",
            inline=False
        )
        embed.add_field(
            name="!unlink",
            value="Unlink your Discord from your R6 account",
            inline=False
        )
        embed.add_field(
            name="!unlink @user",
            value="Unlink another user (admin only)",
            inline=False
        )
        embed.add_field(
            name="!update",
            value="Manually trigger rank update for all users (admin only)",
            inline=False
        )
        embed.add_field(
            name="!help",
            value="Show this message",
            inline=False
        )
    else:
        embed = discord.Embed(
            title="R6 Bot - User Commands",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="!link [username]",
            value="Link your Discord to an R6 account",
            inline=False
        )
        embed.add_field(
            name="!unlink",
            value="Unlink your Discord from your R6 account",
            inline=False
        )
        embed.add_field(
            name="!help",
            value="Show this message",
            inline=False
        )
    
    await ctx.send(embed=embed)

@hourly_update.before_loop
async def before_hourly_update():
    """Wait for bot to be ready before starting hourly update"""
    await bot.wait_until_ready()

# Run bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("DISCORD_BOT_TOKEN not found in .env")
        exit(1)
    
    bot.run(token)
