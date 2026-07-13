import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

class ProjectService:
    def __init__(self):
        self.supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

    def create_project(self, project_name: str, user_id: str):
        data = {"name": project_name, "user_id": user_id}
        return self.supabase.table("projects").insert(data).execute()

    def get_all_projects(self):
        return self.supabase.table("projects").select("*").execute()