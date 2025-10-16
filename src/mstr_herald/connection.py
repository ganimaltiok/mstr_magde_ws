from dotenv import load_dotenv
import os
from mstrio.connection import Connection

load_dotenv()

def create_connection() -> Connection:
    """Establish and return a MicroStrategy connection."""
    base_url = os.getenv("MSTR_URL_API")
    username = os.getenv("MSTR_USERNAME")
    password = os.getenv("MSTR_PASSWORD")
    project = os.getenv("MSTR_PROJECT")

    return Connection(
        base_url,
        username,
        password,
        login_mode=1,
        project_name=project
    )
