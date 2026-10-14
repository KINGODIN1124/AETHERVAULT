import os
import time
import json
from typing import Dict, List, Tuple, Optional
from app.config import (
    BASE_DIR,
    ENABLE_ANTI_SCRAPING,
    PUBLIC_DAILY_LIMIT,
    DISCORD_DAILY_LIMIT,
    BURST_LIMIT_PER_SECOND,
    BAN_DURATION_HOURS
)

BANNED_IPS_FILE = os.path.join(BASE_DIR, "banned_ips.json")

# Known aggressive scrapers / exploit user agents
BLOCKED_USER_AGENTS = [
    "sqlmap", "nikto", "scrapy", "acunetix", "zgrab", "dirbuster",
    "gobuster", "wpscan", "havij", "masscan"
]

class AntiScrapeShield:
    """
    Automated IP Protection & Anti-Scraping Defense Engine.
    Enforces:
      1. Immediate IP Ban on burst scraping (> 5 req/sec)
      2. 24-Hour Automated IP Blacklist
      3. Strict Daily Limits: 30 req/day for 7-day Public Key
      4. 150 req/day for 1-month Discord Keys
      5. Malicious scanner User-Agent blocking
    """

    def __init__(self):
        self.enabled = ENABLE_ANTI_SCRAPING
        self._load_banned_ips()
        # In-memory sliding window: {ip: [timestamps]}
        self.ip_burst_tracker: Dict[str, List[float]] = {}
        # In-memory daily counter: {key_or_ip: [(timestamp)]}
        self.daily_usage_tracker: Dict[str, List[float]] = {}

    def _load_banned_ips(self):
        self.banned_ips: Dict[str, Dict] = {}
        if os.path.exists(BANNED_IPS_FILE):
            try:
                with open(BANNED_IPS_FILE, "r", encoding="utf-8") as f:
                    self.banned_ips = json.load(f)
            except Exception as e:
                print(f"[AntiScrape] Failed to load banned IPs: {e}")
                self.banned_ips = {}

    def _save_banned_ips(self):
        try:
            with open(BANNED_IPS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.banned_ips, f, indent=2)
        except Exception as e:
            print(f"[AntiScrape] Failed to save banned IPs: {e}")

    def is_ip_banned(self, ip: str) -> Tuple[bool, Optional[str]]:
        """Checks if an IP address is currently banned."""
        if not self.enabled or not ip:
            return False, None

        if ip in self.banned_ips:
            ban_info = self.banned_ips[ip]
            unban_at = ban_info.get("unban_at", 0)
            if time.time() < unban_at:
                remaining_hrs = round((unban_at - time.time()) / 3600, 1)
                return True, f"IP temporarily blocked for automated scraping. Unbans in {remaining_hrs} hours."
            else:
                # Ban expired
                del self.banned_ips[ip]
                self._save_banned_ips()

        return False, None

    def ban_ip(self, ip: str, reason: str = "Automated scraping detected", duration_hours: int = BAN_DURATION_HOURS):
        """Immediately blocks an IP address."""
        if not ip:
            return
        unban_timestamp = time.time() + (duration_hours * 3600)
        self.banned_ips[ip] = {
            "ip": ip,
            "reason": reason,
            "banned_at": int(time.time()),
            "unban_at": int(unban_timestamp),
            "duration_hours": duration_hours
        }
        self._save_banned_ips()
        print(f"[!] [AntiScrape] AUTO-BANNED IP {ip}: {reason} for {duration_hours} hours.")

    def unban_ip(self, ip: str) -> bool:
        """Manually removes an IP from the blacklist."""
        if ip in self.banned_ips:
            del self.banned_ips[ip]
            self._save_banned_ips()
            print(f"[+] [AntiScrape] Manually unbanned IP: {ip}")
            return True
        return False

    def check_request(self, ip: str, user_agent: str, key_info: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validates request against anti-scraping rules and daily quotas.
        Returns: (is_allowed, error_message)
        """
        if not self.enabled:
            return True, None

        now = time.time()

        # 1. Check IP Blacklist
        banned, reason = self.is_ip_banned(ip)
        if banned:
            return False, reason

        # 2. Check Malicious User Agent
        ua_clean = (user_agent or "").lower()
        for bad_ua in BLOCKED_USER_AGENTS:
            if bad_ua in ua_clean:
                self.ban_ip(ip, reason=f"Suspicious scraping User-Agent: {bad_ua}")
                return False, "Access Denied: Automated scraping tools are strictly forbidden."

        # 3. Burst Rate-Limiting Protection (Detect Scraping Bots)
        if ip not in self.ip_burst_tracker:
            self.ip_burst_tracker[ip] = []
        
        # Keep only timestamps within the last 1 second
        self.ip_burst_tracker[ip] = [t for t in self.ip_burst_tracker[ip] if now - t <= 1.0]
        self.ip_burst_tracker[ip].append(now)

        if len(self.ip_burst_tracker[ip]) > BURST_LIMIT_PER_SECOND:
            self.ban_ip(ip, reason=f"High frequency scraping detected ({len(self.ip_burst_tracker[ip])} req/s)")
            return False, "Access Denied: Rapid sequential scraping activity detected. Your IP has been banned for 24 hours."

        # 4. Enforce Daily Quotas (30 req/day for Public, 150 for Discord, unlimited for admin)
        tier = key_info.get("tier", "standard")
        key_id = key_info.get("key_id", ip)

        if tier != "admin" and tier != "unlimited":
            tracker_id = f"{key_id}:{ip}"
            if tracker_id not in self.daily_usage_tracker:
                self.daily_usage_tracker[tracker_id] = []

            # Clean entries older than 24 hours (86400 seconds)
            self.daily_usage_tracker[tracker_id] = [
                t for t in self.daily_usage_tracker[tracker_id] if now - t < 86400
            ]

            max_limit = PUBLIC_DAILY_LIMIT if tier == "public_trial" else DISCORD_DAILY_LIMIT
            current_count = len(self.daily_usage_tracker[tracker_id])

            if current_count >= max_limit:
                if tier == "public_trial":
                    return False, (
                        f"Daily limit reached ({max_limit}/30 requests used for Public 7-Day Key). "
                        "To get 1-Month Extended Access with 150 requests/day, join our Discord server and use /claimkey!"
                    )
                else:
                    return False, f"Daily limit reached ({max_limit} requests/day). Resets automatically in 24 hours."

            self.daily_usage_tracker[tracker_id].append(now)

        return True, None

# Global Shield Instance
anti_scrape = AntiScrapeShield()
