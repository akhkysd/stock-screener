import os

from dotenv import load_dotenv

load_dotenv()


def load_edinet_api_key() -> str | None:
    return os.environ.get("EDINET_API_KEY")
