import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


class R6SAPIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_count = 0
        self.rate_limit_limit: Optional[int] = None
        self.rate_limit_remaining: Optional[int] = None

    async def _handle_auth_failure(self, error: Exception) -> bool:
        """Log authentication errors with Tracker Network."""
        message = str(error).lower()
        if "401" in message or "403" in message:
            logger.error("Tracker Network rejected the API key; check configuration")
            return False

        return False

    async def authenticate(self) -> bool:
        """Create a Tracker Network session."""
        if not self.api_key:
            logger.error("TRACKER_API_KEY is not configured")
            return False

        if self.session and not self.session.closed:
            return True

        try:
            self.session = aiohttp.ClientSession(
                headers={
                    "TRN-Api-Key": self.api_key,
                    "Accept": "application/json",
                    "User-Agent": "BenchR6Bot/1.0"
                }
            )
            logger.info("Initialized Tracker Network API session")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Tracker Network session: {e}")
            return False

    async def close(self):
        """Close the HTTP session."""
        if self.session:
            try:
                await self.session.close()
                logger.info("Closed Tracker Network session")
            except Exception as e:
                logger.error(f"Error closing session: {e}")

    async def get_player_rank(self, username: str, platform: str = "pc", retry: bool = True) -> Optional[str]:
        """Get player's current rank"""
        try:
            if not self.session or self.session.closed:
                return None

            self.request_count += 1

            platform_map = {
                "pc": "uplay",
                "xbox": "xbl",
                "ps4": "psn",
                "ps5": "psn"
            }

            platform_slug = platform_map.get(platform.lower(), "uplay")
            url = f"https://public-api.tracker.gg/v2/r6/standard/profile/{platform_slug}/{username}"

            async with self.session.get(url) as response:
                self._update_rate_limit(response)

                if response.status == 404:
                    logger.debug(f"Player not found on Tracker Network: {username}")
                    return None

                if response.status >= 400:
                    error_text = await response.text()
                    raise RuntimeError(f"Tracker API error {response.status}: {error_text}")

                data = await response.json()
                rank = self._extract_rank(data)
                return rank if rank else "Unranked"

        except Exception as e:
            if retry and await self._handle_auth_failure(e):
                return await self.get_player_rank(username, platform, retry=False)

            logger.error(f"Error getting player rank for {username}: {e}")
            return None

    async def is_username_valid(self, username: str, platform: str = "pc", retry: bool = True) -> bool:
        """Check if a username exists"""
        try:
            if not self.session or self.session.closed:
                logger.warning("Username validation requested before session was established")
                return False

            platform_map = {
                "pc": "uplay",
                "xbox": "xbl",
                "ps4": "psn",
                "ps5": "psn"
            }

            platform_slug = platform_map.get(platform.lower(), "uplay")
            url = f"https://public-api.tracker.gg/v2/r6/standard/profile/{platform_slug}/{username}"

            async with self.session.get(url) as response:
                self._update_rate_limit(response)

                if response.status == 200:
                    return True

                if response.status == 404:
                    return False

                error_text = await response.text()
                raise RuntimeError(f"Tracker API error {response.status}: {error_text}")
        except Exception as e:
            if retry and await self._handle_auth_failure(e):
                return await self.is_username_valid(username, platform, retry=False)

            logger.warning(f"Error validating username {username}: {e}")
            return False

    def get_similar_usernames(self, username: str, limit: int = 5) -> list:
        """Tracker Network search requires paid access; not supported here."""
        return []

    def get_rate_limit_percentage(self) -> float:
        """Return how much of the rate limit is used based on response headers."""
        if not self.rate_limit_limit:
            return 0.0

        if self.rate_limit_remaining is None:
            return 0.0

        used = self.rate_limit_limit - self.rate_limit_remaining
        return max(0.0, min(100.0, (used / self.rate_limit_limit) * 100))

    def reset_request_count(self):
        """Reset request counter"""
        logger.info(f"Resetting request count. Used {self.request_count} requests this cycle")
        self.request_count = 0

    def _update_rate_limit(self, response: aiohttp.ClientResponse):
        """Update rate limit counters from Tracker API headers."""
        try:
            limit_header = response.headers.get("X-RateLimit-Limit")
            remaining_header = response.headers.get("X-RateLimit-Remaining")

            if limit_header:
                self.rate_limit_limit = int(limit_header)
            if remaining_header:
                self.rate_limit_remaining = int(remaining_header)
        except Exception as e:
            logger.debug(f"Unable to parse rate limit headers: {e}")

    @staticmethod
    def _extract_rank(data: dict) -> Optional[str]:
        """Extract the current season rank from Tracker Network response."""
        segments = data.get("data", {}).get("segments", [])
        for segment in segments:
            stats = segment.get("stats") or {}

            for key in ("currentSeasonRank", "rankName", "rank", "overallRank"):
                stat = stats.get(key)
                if isinstance(stat, dict):
                    value = stat.get("displayValue") or stat.get("metadata", {}).get("name") or stat.get("value")
                    if value:
                        return str(value)

            metadata_name = (segment.get("metadata", {}).get("name") or "").lower()
            if metadata_name in {"seasonal", "pvp"}:
                for stat in stats.values():
                    if isinstance(stat, dict) and stat.get("displayCategory", "").lower() == "ranked":
                        value = stat.get("displayValue") or stat.get("value")
                        if value:
                            return str(value)

        return None
