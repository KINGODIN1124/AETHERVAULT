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
from app.core.depotbox_client import depotbox_client
from app.core.cache_manager import cache_manager
from app.config import DEPOTBOX_COOKIE

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
      ⚡ DEPOTBOX MANIFEST & LUA API CLI MANAGER ⚡
===================================================================={Color.ENDC}"""
    print(banner)

def cmd_create_key(args):
    session_id = args.session or DEPOTBOX_COOKIE
    if not session_id:
        print(f"{Color.RED}[-] Error: No DepotBox session cookie found in .env or via --session argument.{Color.ENDC}")
        sys.exit(1)

    print(f"{Color.CYAN}[*] Creating API key from DepotBox Session ID...{Color.ENDC}")
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

def cmd_check_session(args):
    print(f"{Color.CYAN}[*] Testing DepotBox session cookie against https://depotbox.org...{Color.ENDC}")
    if not DEPOTBOX_COOKIE:
        print(f"{Color.RED}[-] No DEPOTBOX_COOKIE is configured in .env!{Color.ENDC}")
        return

    async def _run():
        is_valid, msg = await depotbox_client.check_session_health()
        if is_valid:
            print(f"{Color.GREEN}[+] Success: {msg}{Color.ENDC}")
        else:
            print(f"{Color.YELLOW}[!] Notice: {msg}{Color.ENDC}")
            print(f"👉 Make sure you are logged into https://depotbox.org with a Premium membership.")

    asyncio.run(_run())

def cmd_list_keys(args):
    keys = key_engine.list_keys()
    if not keys:
        print(f"{Color.YELLOW}[!] No registered keys found. Use 'python cli.py create-key' to generate one.{Color.ENDC}")
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
    success = key_engine.revoke_key(args.key_id)
    if success:
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
            zip_bytes = await depotbox_client.fetch_manifest_zip(appid, args.name or "")
            with open(out_file, "wb") as f:
                f.write(zip_bytes)
            print(f"{Color.GREEN}[+] Successfully downloaded manifest archive: {out_file} ({len(zip_bytes):,} bytes){Color.ENDC}")
        except Exception as e:
            print(f"{Color.RED}[-] Fetch failed: {e}{Color.ENDC}")

    asyncio.run(_run())

def main():
    print_banner()
    parser = argparse.ArgumentParser(description="DepotBox API Management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # create-key
    p_create = subparsers.add_parser("create-key", help="Generate an API key from DepotBox Session ID")
    p_create.add_argument("--label", default="Discord Bot", help="Label or client name")
    p_create.add_argument("--tier", default="premium", help="Tier (premium or standard)")
    p_create.add_argument("--days", type=int, default=365, help="Validity period in days")
    p_create.add_argument("--prefix", default="dbx_", help="Key prefix (default: dbx_)")
    p_create.add_argument("--session", default=None, help="Explicit DepotBox connect.sid value")

    # check-session
    subparsers.add_parser("check-session", help="Verify DepotBox session cookie status")

    # list-keys
    subparsers.add_parser("list-keys", help="List all generated API keys")

    # revoke-key
    p_revoke = subparsers.add_parser("revoke-key", help="Revoke an existing API key")
    p_revoke.add_argument("key_id", help="The Key ID to revoke")

    # fetch
    p_fetch = subparsers.add_parser("fetch", help="Test fetch a game manifest via CLI")
    p_fetch.add_argument("appid", type=int, help="Steam App ID")
    p_fetch.add_argument("--name", default="", help="Optional game title")
    p_fetch.add_argument("--out", default=".", help="Output directory")

    args = parser.parse_args()

    if args.command == "create-key":
        cmd_create_key(args)
    elif args.command == "check-session":
        cmd_check_session(args)
    elif args.command == "list-keys":
        cmd_list_keys(args)
    elif args.command == "revoke-key":
        cmd_revoke_key(args)
    elif args.command == "fetch":
        cmd_fetch(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
