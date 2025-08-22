import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load env data
load_dotenv()

# Initialize url and key vars.
url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(url, key)
