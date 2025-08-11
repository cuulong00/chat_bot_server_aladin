from langchain_core.tools import tool
from serpapi import GoogleSearch
from dotenv import load_dotenv

load_dotenv();
@tool
def google_search(query: str, max_results: int = 5) -> list:
    params = {
        "q": query,
        "api_key": "<YOUR_SERPAPI_KEY>",
        "num": max_results
    }
    search = GoogleSearch(params)
    results = search.get_dict()
    return results.get("organic_results", [])