"""
GitHub Service — create repos via GitHub REST API.
Falls back to simulation mode when GITHUB_TOKEN is not set.
"""

import re
import requests
from typing import List, Optional

from app.config import settings


GITHUB_API = "https://api.github.com"


def _slugify(name: str) -> str:
    """Convert a team name to a valid GitHub repo name."""
    slug = re.sub(r"[^a-zA-Z0-9\-_ ]", "", name)
    slug = slug.strip().replace(" ", "-").lower()
    return slug[:100] or "team-repo"


def _headers() -> dict:
    return {
        "Authorization": f"token {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }


def create_team_repo(
    team_name: str,
    description: str,
    member_github_usernames: List[str],
    hackathon_name: Optional[str] = None,
) -> str:
    """
    Create a GitHub repo, add collaborators, push initial README.

    Returns the repo html_url.
    If GITHUB_TOKEN is empty, simulates and returns a fake URL.
    """
    token = settings.GITHUB_TOKEN
    org = settings.GITHUB_ORG
    repo_name = _slugify(team_name)

    # ── Simulation mode ──
    if not token:
        fake_owner = org or "nest-campus"
        fake_url = f"https://github.com/{fake_owner}/{repo_name}"
        print(f"\n{'='*60}")
        print(f"  🔧 GITHUB SIMULATION MODE")
        print(f"  Repo:          {fake_url}")
        print(f"  Collaborators: {', '.join(member_github_usernames) or 'none'}")
        print(f"{'='*60}\n")
        return fake_url

    # ── Create repository ──
    if org:
        create_url = f"{GITHUB_API}/orgs/{org}/repos"
    else:
        create_url = f"{GITHUB_API}/user/repos"

    repo_payload = {
        "name": repo_name,
        "description": description or f"Team repo for {team_name}",
        "private": False,
        "auto_init": False,
    }

    resp = requests.post(create_url, json=repo_payload, headers=_headers(), timeout=15)
    if resp.status_code not in (201, 422):
        resp.raise_for_status()

    # If 422, repo may already exist — fetch it
    if resp.status_code == 422:
        owner = org or _get_authenticated_user()
        get_resp = requests.get(
            f"{GITHUB_API}/repos/{owner}/{repo_name}",
            headers=_headers(),
            timeout=10,
        )
        get_resp.raise_for_status()
        repo_data = get_resp.json()
    else:
        repo_data = resp.json()

    repo_full_name = repo_data["full_name"]
    repo_url = repo_data["html_url"]

    # ── Add collaborators ──
    for username in member_github_usernames:
        if username:
            try:
                requests.put(
                    f"{GITHUB_API}/repos/{repo_full_name}/collaborators/{username}",
                    json={"permission": "push"},
                    headers=_headers(),
                    timeout=10,
                )
            except Exception:
                pass  # Best-effort; don't fail the whole flow

    # ── Create initial README ──
    readme_lines = [
        f"# {team_name}\n",
        f"{description or ''}\n",
    ]
    if hackathon_name:
        readme_lines.append(f"**Hackathon:** {hackathon_name}\n")
    readme_lines.append("\n## Team Members\n")
    for username in member_github_usernames:
        if username:
            readme_lines.append(f"- [@{username}](https://github.com/{username})\n")
    readme_lines.append("\n---\n*Created by N.E.S.T — Campus Collaboration Platform*\n")

    import base64
    content_b64 = base64.b64encode("".join(readme_lines).encode()).decode()

    try:
        requests.put(
            f"{GITHUB_API}/repos/{repo_full_name}/contents/README.md",
            json={
                "message": "Initial commit — created by N.E.S.T",
                "content": content_b64,
            },
            headers=_headers(),
            timeout=15,
        )
    except Exception:
        pass  # README is nice-to-have

    return repo_url


def _get_authenticated_user() -> str:
    """Return the login of the authenticated user (for personal repos)."""
    resp = requests.get(f"{GITHUB_API}/user", headers=_headers(), timeout=10)
    resp.raise_for_status()
    return resp.json()["login"]
