"""Mock LinkedIn Scraper Service for generating Vibe and Skills data."""

from typing import List, Dict, Any

def extract_linkedin_profile(url: str, name: str = "") -> Dict[str, Any]:
    """
    Simulates extracting data from a LinkedIn profile.
    Since real scraping requires complex setups or paid APIs (and can be blocked),
    this mock function deterministically generates data based on the provided URL or name.
    """
    seed_str = url if url and url.strip() else name
    
    if not seed_str or not seed_str.strip():
        # Return generic neutral base if no valid URL or name is provided
        return {
            "skills": [],
            "experience_years": 0,
            "certifications": [],
            "vibe_tags": ["professional"],
            "recent_posts_summary": "No recent activity."
        }
        
    seed_lower = seed_str.lower()
    
    # 1. Generate Skills based on contents
    skills = []
    if "tech" in seed_lower or "dev" in seed_lower or len(seed_str) % 2 == 0:
        skills.extend(["Python", "JavaScript", "React", "Cloud Computing"])
    if "design" in seed_lower or "art" in seed_lower or len(seed_str) % 3 == 0:
        skills.extend(["UI/UX Design", "Figma", "User Research"])
    if "manage" in seed_lower or "lead" in seed_lower or len(seed_str) % 5 == 0:
        skills.extend(["Project Management", "Agile", "Strategy"])
    
    if not skills:
         skills = ["Communication", "Teamwork", "Problem Solving"]
         
    # 2. Generate Experience Years (deterministic random-ish 1-10)
    experience_years = (len(seed_str) % 10) + 1
    
    # 3. Generate Certifications
    certifications = []
    if "cloud" in seed_lower or experience_years > 5:
        certifications.append("AWS Certified Solutions Architect")
    if "data" in seed_lower:
        certifications.append("Google Data Analytics Professional")
        
    # 4. Generate Vibe Tags
    vibe_tags = []
    if "innovat" in seed_lower or experience_years < 3:
        vibe_tags.extend(["energetic", "creative", "visionary"])
    if experience_years >= 5:
         vibe_tags.extend(["analytical", "structured", "mentorship"])
    if "lead" in seed_lower or len(skills) > 3:
        vibe_tags.extend(["collaborative", "communicative", "driven"])
        
    if not vibe_tags:
        vibe_tags = ["professional", "focused"]
        
    return {
        "skills": list(set(skills)),
        "experience_years": experience_years,
        "certifications": list(set(certifications)),
        "vibe_tags": list(set(vibe_tags)),
        "recent_posts_summary": f"User frequently posts about topics related to {skills[0]} and teamwork."
    }
