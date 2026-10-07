import requests
import json

BACKEND_URL = "http://127.0.0.1:8000"
PI_URL = "http://127.0.0.1:5000"

print("1. Checking backend health...")
resp = requests.get(f"{BACKEND_URL}/api/health")
print(resp.json())

print("\n2. Checking Pi health...")
resp = requests.get(f"{PI_URL}/api/health")
print(resp.json())

print("\n3. Starting enrollment...")
start_data = {"role": "student", "name": "Test User", "person_id": "TEST_02"}
resp = requests.post(f"{BACKEND_URL}/api/enroll/start", json=start_data)
token = resp.json()["enrollment_token"]
print("Token:", token)

print("\n4. Triggering Pi /api/embed...")
files = [("images", ("face.jpg", b"fakeimage", "image/jpeg"))]
data = {"enrollment_token": token}
resp = requests.post(f"{PI_URL}/api/embed", data=data, files=files)
print("Pi response:", resp.status_code, resp.text)

print("\n5. Verifying DB state via /api/people...")
resp = requests.get(f"{BACKEND_URL}/api/people?role=student")
people = resp.json().get("people", [])
for p in people:
    if p["person_id"] == "TEST_02":
        print("Success! Person found in DB.")
        break
else:
    print("Person NOT found in DB!")

print("\n6. Verifying /api/pi/embeddings...")
resp = requests.get(f"{BACKEND_URL}/api/pi/embeddings", headers={"X-Device-Key": "default-dev-key"})
print("Embeddings version:", resp.json()["version"])
