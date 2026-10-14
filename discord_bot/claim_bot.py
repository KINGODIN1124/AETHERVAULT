import os
import sys
import json
import time
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Ensure parent directory is in path to import key_engine
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.key_engine import key_engine

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
API_BASE_URL = os.getenv("API_PUBLIC_URL", "http://your-server-ip:8000")
CLAIMS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "discord_claims.json")

def load_claims() -> dict:
    if os.path.exists(CLAIMS_FILE):
        try:
            with open(CLAIMS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_claims(claims: dict):
    try:
        with open(CLAIMS_FILE, "w", encoding="utf-8") as f:
            json.dump(claims, f, indent=2)
    except Exception as e:
        print(f"Error saving claims: {e}")

class ClaimBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ Slash commands synced globally for {self.user}!")

bot = ClaimBot()

@bot.tree.command(name="claimkey", description="Claim a FREE 1-Month API Key for Steam Manifests & Lua (150 req/day)")
async def claimkey(interaction: discord.Interaction):
    """Issues a 1-month API key to verified Discord server members."""
    await interaction.response.defer(ephemeral=True)

    user_id = str(interaction.user.id)
    username = str(interaction.user)
    now = time.time()

    claims = load_claims()

    # Check cooldown (30 days between claims)
    if user_id in claims:
        last_claim = claims[user_id].get("claimed_at", 0)
        expires_at = claims[user_id].get("expires_at", 0)
        existing_key = claims[user_id].get("api_key", "")

        if now < expires_at:
            remaining_days = int((expires_at - now) / 86400)
            embed = discord.Embed(
                title="🔑 Your Active 1-Month API Key",
                description=(
                    f"Hello **{interaction.user.display_name}**, you already have an active API key!\n\n"
                    f"**Your Key:**\n`{existing_key}`\n\n"
                    f"⏳ **Days Remaining:** `{remaining_days} days`\n"
                    f"⚡ **Daily Quota:** `150 requests/day`\n\n"
                    f"👉 **Usage Example:**\n"
                    f"`curl -H \"X-API-Key: {existing_key}\" {API_BASE_URL}/api/v1/manifest/730 -o 730.zip`"
                ),
                color=discord.Color.blue()
            )
            embed.set_footer(text="AetherVault Engine • Discord Member Perk")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

    # Mint a fresh 1-Month Key (30 Days, 150 req/day)
    record = key_engine.create_discord_member_key(
        user_id=interaction.user.id,
        username=username
    )

    claims[user_id] = {
        "user_id": interaction.user.id,
        "username": username,
        "api_key": record["api_key"],
        "key_id": record["key_id"],
        "claimed_at": int(now),
        "expires_at": record.get("expires_at")
    }
    save_claims(claims)

    embed = discord.Embed(
        title="🎉 Congratulations! Your 1-Month Key is Ready",
        description=(
            f"Welcome to **AetherVault Community**, **{interaction.user.display_name}**!\n\n"
            f"Here is your dedicated 1-Month Extended Access Key:\n"
            f"```\n{record['api_key']}\n```\n"
            f"✨ **Tier:** `Discord Member (1-Month)`\n"
            f"📅 **Valid For:** `30 Days`\n"
            f"⚡ **Daily Rate Limit:** `150 requests per day`\n\n"
            f"### 🛠️ How to Use It in Your Tools\n"
            f"**cURL:**\n"
            f"```bash\ncurl -H \"X-API-Key: {record['api_key']}\" {API_BASE_URL}/api/v1/manifest/730 -o 730.zip\n```\n"
            f"**In Manifest-Bot (.env):**\n"
            f"```ini\nMANIFEST_API_KEY={record['api_key']}\nMANIFEST_API_URL={API_BASE_URL}\n```"
        ),
        color=discord.Color.green()
    )
    embed.set_footer(text="AetherVault Engine • Please do not share your private key")
    await interaction.followup.send(embed=embed, ephemeral=True)

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ Please set DISCORD_TOKEN in your .env file to run the claim bot.")
    else:
        print("🚀 Starting AetherVault Key Claim Discord Bot...")
        bot.run(DISCORD_TOKEN)
