"""
Gemini-backed Vibe Analysis Service.

Analyses a user's personality, collaboration style, and skills
based on their username/email using Google's Gemini API.

Falls back to a smart local analysis when no GEMINI_API_KEY is set.
"""

import hashlib
import json
import os
import logging
from typing import Dict, Any, List, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# ── Personality trait pools for local fallback ──
TRAIT_POOLS = {
    "tech": {
        "skills": ["Python", "JavaScript", "React", "Cloud Computing", "Data Analysis", "Machine Learning"],
        "vibe_tags": ["analytical", "structured", "innovative", "problem-solver"],
        "collab_style": "methodical",
    },
    "design": {
        "skills": ["UI/UX Design", "Figma", "User Research", "Prototyping", "Visual Design"],
        "vibe_tags": ["creative", "empathetic", "visionary", "detail-oriented"],
        "collab_style": "visual-thinker",
    },
    "business": {
        "skills": ["Project Management", "Strategy", "Communication", "Agile", "Leadership"],
        "vibe_tags": ["driven", "collaborative", "communicative", "strategic"],
        "collab_style": "leader",
    },
    "research": {
        "skills": ["Research Methods", "Data Science", "Statistics", "Academic Writing"],
        "vibe_tags": ["curious", "thorough", "analytical", "persistent"],
        "collab_style": "deep-diver",
    },
    "general": {
        "skills": ["Communication", "Teamwork", "Problem Solving", "Adaptability"],
        "vibe_tags": ["professional", "focused", "reliable", "adaptable"],
        "collab_style": "generalist",
    },
}

# ── Name-pattern heuristics for local personality analysis ──
NAME_HINTS = {
    "tech": ["dev", "code", "hack", "tech", "eng", "sys", "data", "cyber", "net", "comp", "prog", "soft"],
    "design": ["design", "art", "creat", "ux", "ui", "graph", "visual", "media", "photo"],
    "business": ["manage", "lead", "exec", "strat", "market", "biz", "mba", "consult"],
    "research": ["research", "sci", "phd", "lab", "study", "acad", "prof"],
}


def _hash_seed(text: str) -> int:
    """Deterministic numeric hash from text."""
    return int(hashlib.md5(text.encode()).hexdigest(), 16)


def _analyse_locally(email: str, username: str) -> Dict[str, Any]:
    """
    Smart local personality analysis based on name/email patterns.
    Provides a ChatGPT-like result without an API call.
    """
    seed_text = (email or username or "unknown").lower().strip()
    seed = _hash_seed(seed_text)

    # Detect personality domain from name/email patterns
    detected_domain = "general"
    for domain, keywords in NAME_HINTS.items():
        if any(kw in seed_text for kw in keywords):
            detected_domain = domain
            break

    # If no keyword match, use hash to assign a domain
    if detected_domain == "general" and seed_text != "unknown":
        domains = ["tech", "design", "business", "research", "general"]
        detected_domain = domains[seed % len(domains)]

    pool = TRAIT_POOLS[detected_domain]

    # Deterministically pick a subset of skills and vibe tags
    n_skills = 2 + (seed % 3)  # 2-4 skills
    n_vibes = 2 + (seed % 2)   # 2-3 vibe tags
    skills = pool["skills"][:n_skills]
    vibe_tags = pool["vibe_tags"][:n_vibes]

    # Cross-pollinate with a secondary domain based on email length
    secondary = list(TRAIT_POOLS.keys())
    secondary_domain = secondary[(seed >> 4) % len(secondary)]
    if secondary_domain != detected_domain:
        extra_pool = TRAIT_POOLS[secondary_domain]
        skills.append(extra_pool["skills"][seed % len(extra_pool["skills"])])
        vibe_tags.append(extra_pool["vibe_tags"][seed % len(extra_pool["vibe_tags"])])

    # Extract "experience" from email patterns (student roll numbers = less exp)
    experience_years = 1
    if any(c.isdigit() for c in seed_text):
        # Looks like a student roll number
        experience_years = 1 + (seed % 3)
    else:
        experience_years = 2 + (seed % 6)

    personality_summary = (
        f"Based on profile analysis, this user shows strong {detected_domain} "
        f"tendencies with a {pool['collab_style']} collaboration style. "
        f"They are likely to be {', '.join(vibe_tags[:2])} in a team setting."
    )

    return {
        "skills": list(set(skills)),
        "vibe_tags": list(set(vibe_tags)),
        "collab_style": pool["collab_style"],
        "personality_summary": personality_summary,
        "experience_years": experience_years,
        "certifications": [],
        "domain": detected_domain,
    }


async def _analyse_with_gemini(email: str, username: str) -> Dict[str, Any]:
    """
    Uses Google's Gemini API to analyse a user's likely personality
    and collaboration style based on their email/username.
    """
    try:
        import httpx

        prompt = f"""Analyze this campus user and predict their collaboration personality:
- Email: {email}
- Username: {username}

Based on their email domain, username patterns, and likely academic background, provide:
1. Top 3-5 likely technical skills
2. 3-4 personality/vibe tags (e.g., "analytical", "creative", "driven", "empathetic")  
3. Collaboration style (one of: "methodical", "visual-thinker", "leader", "deep-diver", "generalist")
4. A 1-sentence personality summary
5. Estimated experience level (1-5 years)

Respond ONLY in this exact JSON format, no markdown:
{{"skills": [...], "vibe_tags": [...], "collab_style": "...", "personality_summary": "...", "experience_years": N}}"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 300,
                        "responseMimeType": "application/json",
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["candidates"][0]["content"]["parts"][0]["text"].strip()

            # Parse JSON response
            result = json.loads(content)
            result.setdefault("certifications", [])
            result.setdefault("domain", "general")
            return result

    except Exception as e:
        logger.warning(f"Gemini API call failed ({e}), falling back to local analysis")
        return _analyse_locally(email, username)


# ── Main public function ──

# Cache results to avoid repeated API calls for the same user
_analysis_cache: Dict[str, Dict[str, Any]] = {}


async def analyse_user_vibe(email: str = "", username: str = "", use_cache: bool = True) -> Dict[str, Any]:
    """
    Analyse a user's personality and collaboration vibe.

    Uses Gemini API when GEMINI_API_KEY is set, otherwise falls back
    to smart local analysis based on email/username patterns.

    Returns dict with: skills, vibe_tags, collab_style, personality_summary,
                        experience_years, certifications, domain
    """
    cache_key = f"{email}:{username}".lower()

    if use_cache and cache_key in _analysis_cache:
        return _analysis_cache[cache_key]

    if GEMINI_API_KEY:
        result = await _analyse_with_gemini(email, username)
    else:
        result = _analyse_locally(email, username)

    _analysis_cache[cache_key] = result
    return result


def analyse_user_vibe_sync(email: str = "", username: str = "") -> Dict[str, Any]:
    """
    Synchronous wrapper for use in non-async contexts.
    Always uses local analysis (no API call).
    """
    return _analyse_locally(email, username)
