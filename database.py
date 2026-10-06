"""Supabase connection for the bot.

The supabase-py client is synchronous, so every call from the bot should go
through `run_query` to avoid blocking Discord's event loop.
"""
import os
import asyncio

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    print("Supabase disabled: SUPABASE_URL / SUPABASE_KEY not set in .env")


async def run_query(fn):
    """Run a blocking Supabase call in a thread.

    Example:
        data = await run_query(lambda: supabase.table('todos').select('*').execute().data)
    """
    return await asyncio.to_thread(fn)
