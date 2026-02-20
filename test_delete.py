import urllib.request
import urllib.error

try:
    req = urllib.request.Request("http://127.0.0.1:8000/teams/3/delete", method="POST")
    with urllib.request.urlopen(req) as response:
        print("Status", response.status)
        print("Success")
except urllib.error.HTTPError as e:
    print(f"HTTP Return: {e.code}")
    print(e.read().decode())
except Exception as e:
    print(f"Error: {e}")
