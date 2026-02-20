"""Service logic for matching users to teams and vice versa."""

from typing import List, Optional
from app.models.user import User, ArchetypeEnum
from app.models.team import Team
from app.models.hackathon import Hackathon
from app.models.capability import ProficiencyEnum
from app.services.linkedin import extract_linkedin_profile

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
    """
    if existing_members is None:
        existing_members = []

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
                # Penalize if capability is already covered by an existing member
                if cap_name in covered_caps:
                    weight *= 0.5 # 50% penalty for overlap
                cap_score_total += weight
                
        # Check LinkedIn skills
        linkedin_data = extract_linkedin_profile(user.linkedin_url)
        li_skills = [s.lower() for s in linkedin_data.get("skills", [])]
        for skill in li_skills:
             if skill in req_caps and skill not in [c.lower() for c in matching_capabilities]:
                 # Add LinkedIn skills as "Intermediate" equivalent (0.5)
                 matching_capabilities.append(skill.title())
                 weight = 0.5
                 if skill in covered_caps:
                     weight *= 0.5
                 cap_score_total += weight
                 
        if linkedin_data.get("certifications"):
             cap_score_total += 0.25 * len(linkedin_data["certifications"])
             
        if linkedin_data.get("experience_years", 0) > 3:
             cap_score_total += 0.5
        
        cap_score = min(100.0, (cap_score_total / max_possible_cap_score) * 100.0)
    else:
        # If no explicit requirements, maybe base it on general skills or default to 50
        cap_score = 50.0

    # 2. Vibe Score
    vibe_score = 0.0
    if not existing_members:
        # No members yet, neutral vibe for the first joiner (or maybe the lead counts)
        vibe_score = 50.0
    elif user.archetype:
        compatible_archetypes = COMPATIBILITY_MATRIX.get(user.archetype, set())
        
        compat_count = 0
        valid_members_count = 0
        for member in existing_members:
            if member.archetype:
                valid_members_count += 1
                member_compatible_with = COMPATIBILITY_MATRIX.get(member.archetype, set())
                # Mutual or one-way compatibility works for a vibe boost
                if member.archetype in compatible_archetypes or user.archetype in member_compatible_with:
                    compat_count += 1
        
        if valid_members_count > 0:
            vibe_score = (compat_count / valid_members_count) * 100.0
        else:
            vibe_score = 50.0
    else:
        vibe_score = 50.0 # No archetype set

    # Evaluate LinkedIn Vibe Overlap
    # if we have linkedin data from the skill block
    li_url = user.linkedin_url if hasattr(user, 'linkedin_url') else None
    if li_url:
        linkedin_data = extract_linkedin_profile(li_url)
        user_vibe_set = set(linkedin_data.get("vibe_tags", []))
        
        team_vibe_tags = set()
        for member in existing_members:
             member_li = extract_linkedin_profile(member.linkedin_url if hasattr(member, 'linkedin_url') else None)
             team_vibe_tags.update(member_li.get("vibe_tags", []))
             
        # Boost based on shared vibe keywords
        overlap = user_vibe_set.intersection(team_vibe_tags)
        if overlap:
             vibe_score = min(100.0, vibe_score + (10.0 * len(overlap)))

    # Final Score enforcing the 60% Skills / 40% Vibe request
    final_score = (cap_score * 0.6) + (vibe_score * 0.4)
    
    return {
        "score": round(final_score, 1),
        "capability_score": round(cap_score, 1),
        "vibe_score": round(vibe_score, 1),
        "matching_capabilities": matching_capabilities
    }
