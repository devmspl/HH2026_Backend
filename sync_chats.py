import requests

BASE_URL = "http://localhost:8000/api/v1"
payload = {
    "username": "admin@example.com",
    "password": "admin123"
}

response = requests.post(f"{BASE_URL}/login/access-token", data=payload)
if response.status_code == 200:
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    sync_response = requests.post(f"{BASE_URL}/chat/groups/auto-create", headers=headers)
    print(sync_response.json())
else:
    print(f"Login failed: {response.status_code} - {response.text}")
