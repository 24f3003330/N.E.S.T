import re

with open("app/routers/ideajam.py", "r") as f:
    text = f.read()

# I am going to apply a global try-except patch to surface the traceback.
def patch_endpoint(match):
    header = match.group(1)
    body = match.group(2)
    new_body = "\n".join("    " + line for line in body.split("\n"))
    return f"{header}\n    try:\n{new_body}\n    except Exception as e:\n        import traceback\n        err = traceback.format_exc()\n        raise HTTPException(status_code=500, detail=f'IdeaJam Crash: {{str(e)}} \\n{{err}}')"

new_text = re.sub(r'(@router\.[a-z]+\([^)]*\)\s+async def [a-z0-9_]+\([^)]*\):)\n(.*?)(?=\n@router|\Z)', patch_endpoint, text, flags=re.DOTALL)

with open("app/routers/ideajam.py", "w") as f:
    f.write(new_text)

