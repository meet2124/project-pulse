import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

try:
    supabase = create_client(url, key)
    print("Success: Database is reachable.")
except Exception as e:
    print(f"Connection failed: {e}")
