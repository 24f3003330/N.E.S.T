"""Service logic for matching users to teams and vice versa."""

from typing import List, Optional
from app.models.user import User, ArchetypeEnum
from app.models.team import Team
from app.models.hackathon import Hackathon
from app.models.capability import ProficiencyEnum
from app.services.chatgpt_vibe import analyse_user_vibe_sync

# Archetype Compatibility Matrix
# Builder + (Designer, Researcher)
# Designer + (Builder, Communicator)
# Researcher + (Builder, Strategist)
# Communicator + (all)
# Strategist + (Researcher, Communicator)
COMPATIBILITY_MATRIX = {
    ArchetypeEnum.BUILDER: {ArchetypeEnum.DESIGNER, ArchetypeEnum.RESEARCHER},
    ArchetypeEnum.DESIGNER: {ArchetypeEnum.BUILDER, ArchetypeEnum.COMMUNICATOR},
    ArchetypeEnum.RESEARCHER: {ArchetypeEnum.BUILDER, ArchetypeEnum.STRATEGIST},
    ArchetypeEnum.COMMUNICATOR: {
        ArchetypeEnum.BUILDER, 
        ArchetypeEnum.DESIGNER, 
        ArchetypeEnum.RESEARCHER, 
        ArchetypeEnum.STRATEGIST, 
        ArchetypeEnum.COMMUNICATOR
    },
    ArchetypeEnum.STRATEGIST: {ArchetypeEnum.RESEARCHER, ArchetypeEnum.COMMUNICATOR},
}

# Collaboration style compatibility (from ChatGPT analysis)
COLLAB_STYLE_COMPAT = {
    "methodical": {"leader", "deep-diver", "visual-thinker"},
    "visual-thinker": {"methodical", "leader", "generalist"},
    "leader": {"methodical", "visual-thinker", "deep-diver", "generalist"},
    "deep-diver": {"methodical", "leader", "generalist"},
    "generalist": {"leader", "visual-thinker", "deep-diver", "methodical"},
}

PROFICIENCY_WEIGHTS = {
    ProficiencyEnum.BEGINNER: 0.25,
    ProficiencyEnum.INTERMEDIATE: 0.5,
    ProficiencyEnum.ADVANCED: 0.75,
    ProficiencyEnum.EXPERT: 1.0,
}

def score_user_for_team(user: User, team: Team, hackathon: Hackathon, existing_members: Optional[List[User]] = None) -> dict:
    """
    Calculate a match score (0-100) for a user joining a specific team for a hackathon.
    Returns a dict with 'score', 'capability_score', 'vibe_score', and 'matching_capabilities'.
    
    Uses ChatGPT-based personality analysis (via email/username) for vibe scoring.
    """
    if existing_members is None:
        existing_members = []

    # ── Get ChatGPT personality analysis for the user ──
    user_analysis = analyse_user_vibe_sync(
        email=user.email or "",
        username=user.full_name or ""
    )

    # 1. Capability Score
    req_caps = set(tag.lower() for tag in hackathon.required_capabilities) if hackathon and hackathon.required_capabilities else set()
    user_caps = user.capabilities or []
    
    covered_caps = set()
    for member in existing_members:
        if member.capabilities:
            for cap in member.capabilities:
                covered_caps.add(cap.name.lower())

    cap_score_total = 0.0
    max_possible_cap_score = len(req_caps) * 1.0 if req_caps else 1.0
    matching_capabilities = []

    if req_caps:
        # Check platform capabilities
        for cap in user_caps:
            cap_name = cap.name.lower()
            if cap_name in req_caps:
                matching_capabilities.append(cap.name)
                weight = PROFICIENCY_WEIGHTS.get(cap.proficiency_level, 0.25)
                if cap_name in covered_caps:
                    weight *= 0.5
                cap_score_total += weight
                
        # Check ChatGPT-detected skills (replaces LinkedIn skills)
        chatgpt_skills = [s.lower() for s in user_analysis.get("skills", [])]
        for skill in chatgpt_skills:
             if skill in req_caps and skill not in [c.lower() for c in matching_capabilities]:
                 matching_capabilities.append(skill.title())
                 weight = 0.5  # ChatGPT-inferred skills treated as Intermediate
                 if skill in covered_caps:
                     weight *= 0.5
                 cap_score_total += weight
                 
        # Bonus for experience
        if user_analysis.get("experience_years", 0) > 3:
             cap_score_total += 0.5
        
        cap_score = min(100.0, (cap_score_total / max_possible_cap_score) * 100.0)
    else:
        cap_score = 50.0

    # 2. Vibe Score (Archetype Matrix + ChatGPT Personality Analysis)
    vibe_score = 0.0
    
    if user.archetype and existing_members:
        compatible_archetypes = COMPATIBILITY_MATRIX.get(user.archetype, set())
        
        compat_count = 0
        valid_members_count = 0
        for member in existing_members:
            if member.archetype:
                valid_members_count += 1
                member_compatible_with = COMPATIBILITY_MATRIX.get(member.archetype, set())
                if member.archetype in compatible_archetypes or user.archetype in member_compatible_with:
                    compat_count += 1
        
        if valid_members_count > 0:
            vibe_score = (compat_count / valid_members_count) * 100.0
        else:
            vibe_score = 50.0
    else:
        import random
        random.seed(user.id + (team.id if team else 0))
        vibe_score = random.uniform(45.0, 75.0)

    # ── ChatGPT Vibe Analysis (replaces LinkedIn vibe tags) ──
    user_vibe_set = set(user_analysis.get("vibe_tags", []))
    user_collab_style = user_analysis.get("collab_style", "generalist")
    
    team_vibe_tags = set()
    team_collab_styles = []
    for member in existing_members:
        member_analysis = analyse_user_vibe_sync(
            email=member.email or "",
            username=member.full_name or ""
        )
        team_vibe_tags.update(member_analysis.get("vibe_tags", []))
        team_collab_styles.append(member_analysis.get("collab_style", "generalist"))
         
    # Boost based on shared personality/vibe tags
    overlap = user_vibe_set.intersection(team_vibe_tags)
    if overlap:
         vibe_score = min(100.0, vibe_score + (12.0 * len(overlap)))
    
    # Boost based on collaboration style compatibility
    compatible_styles = COLLAB_STYLE_COMPAT.get(user_collab_style, set())
    style_matches = sum(1 for s in team_collab_styles if s in compatible_styles)
    if style_matches:
        vibe_score = min(100.0, vibe_score + (10.0 * style_matches))
         
    # Add a slight deterministic nudge to break ties
    import random
    random.seed(user.id + (team.id if team else 0))
    vibe_score = min(100.0, max(0.0, vibe_score + random.uniform(-5.0, 15.0)))

    # Final Score: 60% Skills / 40% Vibe
    final_score = (cap_score * 0.6) + (vibe_score * 0.4)
    
    return {
        "score": round(final_score, 1),
        "capability_score": round(cap_score, 1),
        "vibe_score": round(vibe_score, 1),
        "matching_capabilities": matching_capabilities
    }

