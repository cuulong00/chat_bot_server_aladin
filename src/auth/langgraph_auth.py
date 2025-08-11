
import os
import httpx
from langgraph_sdk import Auth

auth = Auth()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

@auth.authenticate
async def get_current_user(authorization: str | None):
    """Validate JWT tokens and extract user information from Supabase."""
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
                "identity": user["id"],
                "email": user["email"],
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

