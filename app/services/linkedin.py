"""Mock LinkedIn Scraper Service for generating Vibe and Skills data."""

from typing import List, Dict, Any

def extract_linkedin_profile(url: str) -> Dict[str, Any]:
    """
    Simulates extracting data from a LinkedIn profile.
    Since real scraping requires complex setups or paid APIs (and can be blocked),
    this mock function deterministically generates data based on the provided URL length and characters.
    """
    if not url or not url.strip() or "linkedin.com" not in url.lower():
        # Return generic neutral base if no valid URL is provided
        return {
            "skills": [],
            "experience_years": 0,
            "certifications": [],
            "vibe_tags": ["professional"],
            "recent_posts_summary": "No recent activity."
        }
        
    url_lower = url.lower()
    
    # 1. Generate Skills based on URL contents
    skills = []
    if "tech" in url_lower or "dev" in url_lower or len(url) % 2 == 0:
        skills.extend(["Python", "JavaScript", "React", "Cloud Computing"])
    if "design" in url_lower or "art" in url_lower or len(url) % 3 == 0:
        skills.extend(["UI/UX Design", "Figma", "User Research"])
    if "manage" in url_lower or "lead" in url_lower or len(url) % 5 == 0:
        skills.extend(["Project Management", "Agile", "Strategy"])
    
    if not skills:
         skills = ["Communication", "Teamwork", "Problem Solving"]
         
    # 2. Generate Experience Years (deterministic random-ish 1-10)
    experience_years = (len(url) % 10) + 1
    
    # 3. Generate Certifications
    certifications = []
    if "cloud" in url_lower or experience_years > 5:
        certifications.append("AWS Certified Solutions Architect")
    if "data" in url_lower:
        certifications.append("Google Data Analytics Professional")
        
    # 4. Generate Vibe Tags
    vibe_tags = []
    if "innovat" in url_lower or experience_years < 3:
        vibe_tags.extend(["energetic", "creative", "visionary"])
    if experience_years >= 5:
         vibe_tags.extend(["analytical", "structured", "mentorship"])
    if "lead" in url_lower or len(skills) > 3:
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
