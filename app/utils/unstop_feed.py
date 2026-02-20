import asyncio
import time
from typing import Dict, List

# Global cache to prevent spamming
_CACHE: Dict[str, any] = {"timestamp": 0.0, "data": []}
CACHE_TTL = 600  # 10 minutes

# Mock data since Unstop places strong bot-protection (Cloudflare/Akamai)
# on their endpoints which causes automated httpx requests to hang indefinitely.
# This serves to demonstrate the N.E.S.T external integration architecture!
MOCK_UNSTOP_EVENTS = [
    {
        "title": "Smart India Hackathon 2026",
        "url": "https://unstop.com/hackathons/smart-india-hackathon-2026",
        "type": "Hackathon",
        "source": "Unstop"
    },
    {
        "title": "Google Girl Hackathon",
        "url": "https://unstop.com/hackathons/google-girl-hackathon-2026",
        "type": "Hackathon",
        "source": "Unstop"
    },
    {
        "title": "Flipkart GRiD 6.0 - Software Development Track",
        "url": "https://unstop.com/competitions/flipkart-grid-6",
        "type": "Competition",
        "source": "Unstop"
    },
    {
        "title": "L'Oréal Brandstorm 2026",
        "url": "https://unstop.com/competitions/loreal-brandstorm",
        "type": "Competition",
        "source": "Unstop"
    },
    {
        "title": "Tata Imagination Challenge",
        "url": "https://unstop.com/competitions/tata-imagination-challenge",
        "type": "Competition",
        "source": "Unstop"
    },
    {
        "title": "Global AI Innovation Challenge",
        "url": "https://unstop.com/events/global-ai-challenge",
        "type": "Event",
        "source": "Unstop"
    }
]


async def get_unstop_events(query: str = "") -> List[Dict[str, str]]:
    """
    Get Unstop events, utilizing a 10-minute cache.
    Optionally filter by a keyword query.
    """
    global _CACHE
    now = time.time()
    
    # In a real scenario, this would fetch from Unstop. 
    # Due to bot protection, we use mock data representing their typical payload.
    events = MOCK_UNSTOP_EVENTS
        
    # Apply keyword filtering if provided
    if query:
        query_lower = query.lower()
        events = [e for e in events if query_lower in e["title"].lower()]
        
    return events
