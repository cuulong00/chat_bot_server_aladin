
import os
import httpx
from langgraph_sdk import Auth

auth = Auth()

# Read envs safely; allow bypassing Supabase via SKIP_SUPABASE_AUTH=1
SKIP_SUPABASE_AUTH = os.getenv("SKIP_SUPABASE_AUTH", "0") == "1"
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

@auth.authenticate
async def get_current_user(authorization: str | None):
    """Validate JWT tokens via Supabase unless SKIP_SUPABASE_AUTH=1.

    When skipped, return a minimal authenticated identity without contacting Supabase.
    """
    if SKIP_SUPABASE_AUTH or not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        # Bypass mode: treat request as authenticated with minimal identity
        return {
            "identity": "anonymous",
            "email": None,
            "is_authenticated": True,
        }

    assert authorization, "Missing Authorization header"
    scheme, token = authorization.split()
    assert scheme.lower() == "bearer", "Authorization header must start with Bearer"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={
                    "Authorization": authorization,
                    "apiKey": SUPABASE_SERVICE_KEY,
                },
            )
            assert response.status_code == 200, f"Supabase error: {response.text}"
            user = response.json()
            return {
                "identity": user.get("id") or "anonymous",
                "email": user.get("email"),
                "is_authenticated": True,
            }
    except Exception as e:
        raise Auth.exceptions.HTTPException(status_code=401, detail=str(e))

@auth.on
async def add_owner(ctx, value):
    """Make resources private to their creator using resource metadata."""
    filters = {"owner": ctx.user.identity}
    metadata = value.setdefault("metadata", {})
    metadata.update(filters)
    return filters

