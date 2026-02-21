"""
Authentication router — OAuth sign-in (Google, GitHub, LinkedIn) + JWT cookie.

Endpoints:
    GET  /auth/register            → sign-up page (social buttons)
    GET  /auth/login               → login page (social buttons)
    GET  /auth/login/{provider}    → redirect to OAuth consent screen
    GET  /auth/callback/{provider} → handle OAuth callback, create/login user
    GET  /auth/logout              → clear JWT cookie
"""

from typing import Optional

from datetime import datetime, timedelta, timezone

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.config import Config

from app.config import settings
from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")

COOKIE_KEY = "access_token"

# ═══════════════════════════════════════════════════════════════
#  OAuth client setup
# ═══════════════════════════════════════════════════════════════

oauth = OAuth()

# ── Google ──
oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# ── GitHub ──
oauth.register(
    name="github",
    client_id=settings.GITHUB_CLIENT_ID,
    client_secret=settings.GITHUB_CLIENT_SECRET,
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "user:email"},
)

VALID_PROVIDERS = {"google", "github"}


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

def create_access_token(data: dict) -> str:
    """Create a signed JWT with an expiry claim."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _set_auth_cookie(response: RedirectResponse, user_id: int) -> RedirectResponse:
    """Attach the JWT cookie to a response."""
    token = create_access_token({"sub": str(user_id)})
    response.set_cookie(
        key=COOKIE_KEY,
        value=token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
    )
    return response


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Extract the JWT from the cookie, decode it, and return the User.
    Returns None when no valid token is present (allows public pages).
    """
    token = request.cookies.get(COOKIE_KEY)
    if not token:
        return None
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: int = int(payload.get("sub", 0))
        if not user_id:
            return None
    except (JWTError, ValueError):
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


# ═══════════════════════════════════════════════════════════════
#  Logout
# ═══════════════════════════════════════════════════════════════

@router.get("/logout")
async def logout():
    """Clear the auth cookie and redirect to homepage."""
    response = RedirectResponse(url="/?success=Logged+out+successfully", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(COOKIE_KEY)
    return response


async def _get_oauth_user_info(provider: str, token: dict, client) -> dict:
    """
    Fetch the user's profile from the OAuth provider.
    Returns dict with keys: email, name, picture, oauth_id
    """
    if provider == "google":
        userinfo = token.get("userinfo", {})
        return {
            "email": userinfo.get("email"),
            "name": userinfo.get("name", ""),
            "picture": userinfo.get("picture"),
            "oauth_id": userinfo.get("sub"),
        }

    elif provider == "github":
        resp = await client.get("user", token=token)
        profile = resp.json()

        # GitHub may not include email in profile — fetch from /user/emails
        email = profile.get("email")
        if not email:
            emails_resp = await client.get("user/emails", token=token)
            emails = emails_resp.json()
            primary = next((e for e in emails if e.get("primary")), None)
            email = primary["email"] if primary else None

        return {
            "email": email,
            "name": profile.get("name") or profile.get("login", ""),
            "picture": profile.get("avatar_url"),
            "oauth_id": str(profile.get("id")),
            "github_username": profile.get("login"),
        }

    return {}


# ═══════════════════════════════════════════════════════════════
#  Page routes
# ═══════════════════════════════════════════════════════════════

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Render the sign-up page with social buttons."""
    return templates.TemplateResponse(
        "register.html", {"request": request, "errors": []}
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the login page with social buttons."""
    return templates.TemplateResponse(
        "login.html", {"request": request, "errors": []}
    )


# ═══════════════════════════════════════════════════════════════
#  OAuth flow
# ═══════════════════════════════════════════════════════════════

@router.get("/login/{provider}")
async def oauth_login(provider: str, request: Request, account_type: Optional[str] = None):
    """Redirect the user to the provider's OAuth consent screen."""
    if provider not in VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    if account_type in ["Leader", "Member"]:
        request.session["account_type"] = account_type

    client = oauth.create_client(provider)
    redirect_uri = request.url_for("oauth_callback", provider=provider)
    return await client.authorize_redirect(request, str(redirect_uri))


@router.get("/callback/{provider}")
async def oauth_callback(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle the OAuth callback — find or create the user, set JWT cookie."""
    if provider not in VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    try:
        client = oauth.create_client(provider)
        token = await client.authorize_access_token(request)
    except Exception as e:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "errors": [f"Authentication failed: {str(e)}"],
            },
        )

    user_info = await _get_oauth_user_info(provider, token, client)
    email = user_info.get("email")
    oauth_id = user_info.get("oauth_id")

    if not email or not oauth_id:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "errors": ["Could not retrieve your email from the provider. Please try a different sign-in method."],
            },
        )

    # ── Find existing user by oauth_provider + oauth_id ──
    result = await db.execute(
        select(User).where(User.oauth_provider == provider, User.oauth_id == oauth_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Check if a user with this email already exists (different provider)
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user:
            # Link this provider to the existing account
            user.oauth_provider = provider
            user.oauth_id = oauth_id
            if user_info.get("picture"):
                user.avatar_url = user_info["picture"]
        else:
            from app.models.user import AccountTypeEnum
            account_type_str = request.session.pop("account_type", "Member")
            
            # Create a brand-new user
            user = User(
                email=email,
                full_name=user_info.get("name", email.split("@")[0]),
                oauth_provider=provider,
                oauth_id=oauth_id,
                avatar_url=user_info.get("picture"),
                github_username=user_info.get("github_username"),
                account_type=AccountTypeEnum(account_type_str)
            )
            db.add(user)
    
        await db.commit()
    else:
        # Clear any dangling session preference if they are just logging into an existing account
        request.session.pop("account_type", None)

    await db.flush()
    await db.refresh(user)

    response = RedirectResponse(url="/?success=Account+created+successfully", status_code=status.HTTP_303_SEE_OTHER)
    return _set_auth_cookie(response, user.id)


# ═══════════════════════════════════════════════════════════════
#  Logout
# ═══════════════════════════════════════════════════════════════

@router.get("/logout")
async def logout():
    """Clear the auth cookie and redirect to the landing page."""
    response = RedirectResponse(url="/?success=Logged+out+successfully", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key=COOKIE_KEY)
    return response
