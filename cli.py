import os
import sys
import argparse
import asyncio
import json

# Ensure python path includes the depotbox-api directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app.core.key_engine import key_engine
from app.core.upstream_client import upstream_client
from app.core.anti_scrape import anti_scrape
from app.core.session_refresher import session_refresher
from app.config import SESSION_COOKIE

class Color:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    ENDC = "\033[0m"

def print_banner():
    banner = f"""{Color.CYAN}{Color.BOLD}
====================================================================
      ⚡ AETHERVAULT MANIFEST & LUA API CLI MANAGER ⚡
===================================================================={Color.ENDC}"""
    print(banner)

def cmd_create_key(args):
    session_id = args.session or SESSION_COOKIE
    if not session_id:
        print(f"{Color.RED}[-] Error: No session cookie found in .env or via --session argument.{Color.ENDC}")
        sys.exit(1)

    print(f"{Color.CYAN}[*] Creating API key from Master Session...{Color.ENDC}")
    record = key_engine.create_api_key_from_session(
        label=args.label,
        tier=args.tier,
        expires_days=args.days,
        prefix=args.prefix
    )

    print(f"\n{Color.GREEN}[+] API Key Generated Successfully!{Color.ENDC}")
    print(f"--------------------------------------------------------------------")
    print(f"🔑 {Color.BOLD}API Key:{Color.ENDC}    {Color.YELLOW}{record['api_key']}{Color.ENDC}")
    print(f"🏷️  {Color.BOLD}Label:{Color.ENDC}      {record['label']}")
    print(f"⭐ {Color.BOLD}Tier:{Color.ENDC}       {record['tier']}")
    print(f"🆔 {Color.BOLD}Key ID:{Color.ENDC}     {record['key_id']}")
    print(f"📅 {Color.BOLD}Expires In:{Color.ENDC} {args.days} days")
    print(f"--------------------------------------------------------------------")
    print(f"\n{Color.CYAN}👉 Usage in cURL:{Color.ENDC}")
    print(f"curl -H \"X-API-Key: {record['api_key']}\" http://localhost:8000/api/v1/manifest/730 -o 730.zip")
    print(f"\n{Color.CYAN}👉 Usage in Python:{Color.ENDC}")
    print(f"headers = {{'X-API-Key': '{record['api_key']}'}}")
    print(f"r = requests.get('http://localhost:8000/api/v1/manifest/730', headers=headers)")

def cmd_public_key(args):
    print(f"{Color.CYAN}[*] Retrieving active 7-Day Public Community Key...{Color.ENDC}")
    record = key_engine.get_or_create_public_7day_key()
    print(f"\n{Color.GREEN}[+] Active 7-Day Public Trial Key:{Color.ENDC}")
    print(f"--------------------------------------------------------------------")
    print(f"🔑 {Color.BOLD}Key:{Color.ENDC}         {Color.YELLOW}{record['api_key']}{Color.ENDC}")
    print(f"⚡ {Color.BOLD}Rate Limit:{Color.ENDC}  30 requests / day")
    print(f"⏳ {Color.BOLD}Expires At:{Color.ENDC}  {record.get('expires_at')}")
    print(f"--------------------------------------------------------------------")
    print(f"Put this key in your README so GitHub visitors can try it immediately!")

def cmd_check_session(args):
    print(f"{Color.CYAN}[*] Testing upstream session connectivity...{Color.ENDC}")
    if not SESSION_COOKIE:
        print(f"{Color.RED}[-] No session cookie configured in .env!{Color.ENDC}")
        return

    async def _run():
        is_valid, msg = await upstream_client.check_session_health()
        if is_valid:
            print(f"{Color.GREEN}[+] Success: {msg}{Color.ENDC}")
        else:
            print(f"{Color.YELLOW}[!] Notice: {msg}{Color.ENDC}")

    asyncio.run(_run())

def cmd_auto_login(args):
    print(f"{Color.CYAN}[*] Attempting automated headless login to rejuvenate session...{Color.ENDC}")
    async def _run():
        success, msg = await session_refresher.auto_refresh_session()
        if success:
            print(f"{Color.GREEN}[+] {msg}{Color.ENDC}")
        else:
            print(f"{Color.RED}[-] {msg}{Color.ENDC}")
    asyncio.run(_run())

def cmd_list_banned(args):
    banned = anti_scrape.banned_ips
    if not banned:
        print(f"{Color.GREEN}[+] No IPs are currently banned. Anti-Scraping shield is clean.{Color.ENDC}")
        return
    print(f"\n{Color.RED}Blacklisted Scraper IPs ({len(banned)} total):{Color.ENDC}")
    print("=" * 80)
    for ip, info in banned.items():
        print(f"🚫 IP: {Color.BOLD}{ip}{Color.ENDC}")
        print(f"   Reason: {info.get('reason')}")
        print(f"   Banned: {info.get('banned_at')} | Unbans at: {info.get('unban_at')}")
    print("=" * 80)

def cmd_unban(args):
    ip = args.ip.strip()
    if anti_scrape.unban_ip(ip):
        print(f"{Color.GREEN}[+] Successfully unbanned IP: {ip}{Color.ENDC}")
    else:
        print(f"{Color.RED}[-] IP {ip} was not found in the blacklist.{Color.ENDC}")

def cmd_ban(args):
    ip = args.ip.strip()
    anti_scrape.ban_ip(ip, reason=args.reason or "Manual administrative block")
    print(f"{Color.RED}[+] IP {ip} has been blocked for 24 hours.{Color.ENDC}")

def cmd_list_keys(args):
    keys = key_engine.list_keys()
    if not keys:
        print(f"{Color.YELLOW}[!] No registered keys found.{Color.ENDC}")
        return

    print(f"\n{Color.CYAN}Registered API Keys ({len(keys)} total):{Color.ENDC}")
    print("=" * 80)
    for kid, r in keys.items():
        status_color = Color.GREEN if r.get("active", True) else Color.RED
        status_text = "ACTIVE" if r.get("active", True) else "REVOKED"
        print(f"[{status_color}{status_text}{Color.ENDC}] {r.get('label')} (ID: {kid})")
        print(f"    Key:  {r.get('api_key')}")
        print(f"    Tier: {r.get('tier')} | Created: {r.get('created_at')}")
    print("=" * 80)

def cmd_revoke_key(args):
    if key_engine.revoke_key(args.key_id):
        print(f"{Color.GREEN}[+] Key {args.key_id} successfully revoked.{Color.ENDC}")
    else:
        print(f"{Color.RED}[-] Key ID {args.key_id} not found.{Color.ENDC}")

def cmd_fetch(args):
    appid = args.appid
    out_dir = args.out or "."
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"{appid}.zip")

    print(f"{Color.CYAN}[*] Fetching manifest package for AppID {appid}...{Color.ENDC}")
    async def _run():
        try:
            zip_bytes = await upstream_client.fetch_manifest_zip(appid, args.name or "")
            with open(out_file, "wb") as f:
                f.write(zip_bytes)
            print(f"{Color.GREEN}[+] Successfully downloaded manifest archive: {out_file} ({len(zip_bytes):,} bytes){Color.ENDC}")
        except Exception as e:
            print(f"{Color.RED}[-] Fetch failed: {e}{Color.ENDC}")
    asyncio.run(_run())

def main():
    print_banner()
    parser = argparse.ArgumentParser(description="AetherVault CLI Manager")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # create-key
    p_create = subparsers.add_parser("create-key", help="Generate an API key")
    p_create.add_argument("--label", default="Developer Key", help="Client name")
    p_create.add_argument("--tier", default="standard", help="Tier (standard, discord_member, premium, admin)")
    p_create.add_argument("--days", type=int, default=30, help="Validity period in days")
    p_create.add_argument("--prefix", default="av_", help="Key prefix")
    p_create.add_argument("--session", default=None, help="Explicit session cookie")

    # public-key
    subparsers.add_parser("public-key", help="Get or rotate the 7-day public trial key")

    # check-session
    subparsers.add_parser("check-session", help="Verify upstream session status")

    # auto-login
    subparsers.add_parser("auto-login", help="Execute automated login using credentials in .env")

    # list-keys
    subparsers.add_parser("list-keys", help="List all generated API keys")

    # revoke-key
    p_revoke = subparsers.add_parser("revoke-key", help="Revoke an existing API key")
    p_revoke.add_argument("key_id", help="The Key ID to revoke")

    # list-banned
    subparsers.add_parser("list-banned", help="List all auto-banned scraper IPs")

    # ban
    p_ban = subparsers.add_parser("ban", help="Manually ban an IP address")
    p_ban.add_argument("ip", help="IP to block")
    p_ban.add_argument("--reason", default="Manual block", help="Reason for ban")

    # unban
    p_unban = subparsers.add_parser("unban", help="Unban a blacklisted IP address")
    p_unban.add_argument("ip", help="IP to unban")

    # fetch
    p_fetch = subparsers.add_parser("fetch", help="Test fetch a game manifest via CLI")
    p_fetch.add_argument("appid", type=int, help="Steam App ID")
    p_fetch.add_argument("--name", default="", help="Optional game title")
    p_fetch.add_argument("--out", default=".", help="Output directory")

    args = parser.parse_args()

    if args.command == "create-key":
        cmd_create_key(args)
    elif args.command == "public-key":
        cmd_public_key(args)
    elif args.command == "check-session":
        cmd_check_session(args)
    elif args.command == "auto-login":
        cmd_auto_login(args)
    elif args.command == "list-keys":
        cmd_list_keys(args)
    elif args.command == "revoke-key":
        cmd_revoke_key(args)
    elif args.command == "list-banned":
        cmd_list_banned(args)
    elif args.command == "ban":
        cmd_ban(args)
    elif args.command == "unban":
        cmd_unban(args)
    elif args.command == "fetch":
        cmd_fetch(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
