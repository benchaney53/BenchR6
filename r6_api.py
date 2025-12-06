import asyncio
import logging
import types
from typing import Optional

# r6sapi 1.x still decorates coroutines using the removed asyncio.coroutine
# helper. Provide a compatibility alias on Python 3.11+ so the import succeeds
# without crashing during bot startup.
if not hasattr(asyncio, "coroutine"):
    asyncio.coroutine = types.coroutine

import r6sapi as api

logger = logging.getLogger(__name__)

class R6SAPIClient:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.auth = None
        self.request_count = 0
        self.rate_limit = None
    
    async def authenticate(self) -> bool:
        """Authenticate with Ubisoft"""
        try:
            self.auth = api.Auth(self.email, self.password)
            logger.info("Successfully authenticated with Ubisoft")
            return True
        except Exception as e:
            logger.error(f"Failed to authenticate with Ubisoft: {e}")
            return False
    
    async def close(self):
        """Close the authentication session"""
        if self.auth:
            try:
                await self.auth.close()
                logger.info("Closed Ubisoft session")
            except Exception as e:
                logger.error(f"Error closing session: {e}")
    
    async def get_player_rank(self, username: str, platform: str = "pc") -> Optional[str]:
        """Get player's current rank"""
        try:
            if not self.auth:
                return None
            
            self.request_count += 1
            
            # Map platform names
            platform_map = {
                "pc": api.Platforms.UPLAY,
                "xbox": api.Platforms.XBOX,
                "ps4": api.Platforms.PLAYSTATION
            }
            
            platform_obj = platform_map.get(platform.lower(), api.Platforms.UPLAY)
            
            # Get player
            player = await self.auth.get_player(username, platform_obj)
            if not player:
                logger.debug(f"Player not found: {username}")
                return None
            
            # Get current seasonal stats
            seasonal = await player.get_seasonal()
            if not seasonal:
                logger.debug(f"No seasonal data for {username}")
                return None
            
            # Get rank from current season
            rank = seasonal.rank
            return rank if rank else "Unranked"
            
        except Exception as e:
            logger.error(f"Error getting player rank for {username}: {e}")
            return None
    
    async def is_username_valid(self, username: str, platform: str = "pc") -> bool:
        """Check if a username exists"""
        try:
            if not self.auth:
                return False
            
            platform_map = {
                "pc": api.Platforms.UPLAY,
                "xbox": api.Platforms.XBOX,
                "ps4": api.Platforms.PLAYSTATION
            }
            
            platform_obj = platform_map.get(platform.lower(), api.Platforms.UPLAY)
            player = await self.auth.get_player(username, platform_obj)
            
            return player is not None
        except Exception as e:
            logger.debug(f"Error validating username {username}: {e}")
            return False
    
    def get_similar_usernames(self, username: str, limit: int = 5) -> list:
        """r6sapi doesn't support fuzzy search"""
        return []
    
    def get_rate_limit_percentage(self) -> float:
        """No strict rate limits with Ubisoft auth"""
        return 0.0
    
    def reset_request_count(self):
        """Reset request counter"""
        logger.info(f"Resetting request count. Used {self.request_count} requests this cycle")
        self.request_count = 0
