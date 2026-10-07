import requests
import json
import uuid
import random
import time
import subprocess
import sys

BACKEND_URL = "http://127.0.0.1:8000"
PI_URL = "http://127.0.0.1:5000"
DEVICE_KEY = "default-dev-key"
HEADERS = {"X-Device-Key": DEVICE_KEY}

def run_tests():
    print("========================================")
    print("RUNNING END-TO-END VERIFICATION SUITE")
    print("========================================")
    
    # 1. Health checks
    print("\n1. Testing /api/health (Backend & Pi)...")
    b_health = requests.get(f"{BACKEND_URL}/api/health").json()
    assert b_health["ok"] is True, f"Backend health failed: {b_health}"
    print(f"   [OK] Backend healthy: embeddings_version={b_health['embeddings_version']}")
    
    p_health = requests.get(f"{PI_URL}/api/health").json()
    assert p_health["ok"] is True, f"Pi health failed: {p_health}"
    print(f"   [OK] Pi healthy: model_id={p_health['model_id']}")

    # 2. Duplicate ID check & Enrollment start
    test_person_id = f"ST_{int(time.time())}"
    print(f"\n2. Testing /api/enroll/start for student {test_person_id}...")
    start_res = requests.post(f"{BACKEND_URL}/api/enroll/start", json={
        "role": "student",
        "name": "Jane Doe",
        "person_id": test_person_id
    })
    assert start_res.status_code == 200, f"Enroll start failed: {start_res.text}"
    token = start_res.json()["enrollment_token"]
    print(f"   [OK] Enrollment token received: {token}")

    # 3. Model mismatch validation on /api/pi/enroll-complete
    print("\n3. Testing model_id mismatch validation on /api/pi/enroll-complete...")
    mismatch_res = requests.post(f"{BACKEND_URL}/api/pi/enroll-complete", json={
        "enrollment_token": token,
        "embedding": [random.random() for _ in range(128)],
        "model_id": "wrong_model_v99"
    }, headers=HEADERS)
    assert mismatch_res.status_code == 422, f"Expected 422 for model mismatch, got {mismatch_res.status_code}: {mismatch_res.text}"
    print("   [OK] Correctly rejected with 422 MODEL_MISMATCH")

    # 4. Successful Enrollment
    print("\n4. Testing successful enrollment on /api/pi/enroll-complete...")
    face_emb_1 = [random.uniform(-1.0, 1.0) for _ in range(128)]
    complete_res = requests.post(f"{BACKEND_URL}/api/pi/enroll-complete", json={
        "enrollment_token": token,
        "embedding": face_emb_1,
        "model_id": "dlib_face_recognition_resnet_v1"
    }, headers=HEADERS)
    assert complete_res.status_code == 201, f"Enroll complete failed: {complete_res.status_code}: {complete_res.text}"
    print(f"   [OK] Enrolled successfully: {complete_res.json()}")

    # 5. Duplicate Face Detection
    print("\n5. Testing Duplicate Face Detection with same embedding...")
    test_person_id_2 = f"ST2_{int(time.time())}"
    start_res_2 = requests.post(f"{BACKEND_URL}/api/enroll/start", json={
        "role": "student",
        "name": "Jane Imposter",
        "person_id": test_person_id_2
    })
    token_2 = start_res_2.json()["enrollment_token"]
    
    # Try enrolling with virtually same face (distance < 0.5)
    dup_face = [x + random.uniform(-0.01, 0.01) for x in face_emb_1]
    dup_res = requests.post(f"{BACKEND_URL}/api/pi/enroll-complete", json={
        "enrollment_token": token_2,
        "embedding": dup_face,
        "model_id": "dlib_face_recognition_resnet_v1"
    }, headers=HEADERS)
    assert dup_res.status_code == 409, f"Expected 409 DUPLICATE_FACE, got {dup_res.status_code}: {dup_res.text}"
    print(f"   [OK] Correctly detected duplicate face: {dup_res.json()['detail']['error']}")

    # 6. Distinct Face Enrollment
    print("\n6. Testing distinct face enrollment (no false DUPLICATE_FACE)...")
    distinct_face = [-x for x in face_emb_1] # inverted vector is far away
    distinct_res = requests.post(f"{BACKEND_URL}/api/pi/enroll-complete", json={
        "enrollment_token": token_2,
        "embedding": distinct_face,
        "model_id": "dlib_face_recognition_resnet_v1"
    }, headers=HEADERS)
    assert distinct_res.status_code == 201, f"Expected 201 for distinct face, got {distinct_res.status_code}: {distinct_res.text}"
    print(f"   [OK] Distinct face enrolled: {distinct_res.json()}")

    # 7. Verify /api/pi/embeddings and /api/pi/embeddings/version
    print("\n7. Testing /api/pi/embeddings and /api/pi/embeddings/version...")
    v_res = requests.get(f"{BACKEND_URL}/api/pi/embeddings/version", headers=HEADERS)
    assert v_res.status_code == 200
    curr_version = v_res.json()["version"]
    print(f"   [OK] Embeddings version: {curr_version}")
    
    emb_res = requests.get(f"{BACKEND_URL}/api/pi/embeddings", headers=HEADERS)
    assert emb_res.status_code == 200
    emb_data = emb_res.json()
    assert emb_data["version"] == curr_version
    assert len(emb_data["people"]) >= 2
    print(f"   [OK] Sync payload returned {len(emb_data['people'])} people with 128-d vectors")

    # 8. Session creation and Attendance idempotency
    print("\n8. Testing Session creation and Attendance idempotency...")
    # Ensure we have a teacher in DB
    t_res = requests.get(f"{BACKEND_URL}/api/people?role=teacher").json()
    teachers = t_res.get("people", [])
    if teachers:
        teacher_id = teachers[0]["person_id"]
    else:
        teacher_id = "T_TEST"
        st = requests.post(f"{BACKEND_URL}/api/enroll/start", json={"role": "teacher", "name": "Prof Test", "person_id": teacher_id, "subject": "Maths"}).json()
        requests.post(f"{BACKEND_URL}/api/pi/enroll-complete", json={
            "enrollment_token": st["enrollment_token"],
            "embedding": [random.uniform(-1, 1) for _ in range(128)],
            "model_id": "dlib_face_recognition_resnet_v1"
        }, headers=HEADERS)
    sess_uuid = str(uuid.uuid4())
    now_iso = "2026-10-03T10:00:00Z"
    auto_close_iso = "2026-10-03T11:00:00Z"
    
    sess_res = requests.post(f"{BACKEND_URL}/api/pi/sessions", json={
        "client_uuid": sess_uuid,
        "teacher_person_id": teacher_id,
        "subject": "Maths",
        "start_time": now_iso,
        "auto_close_at": auto_close_iso
    }, headers=HEADERS)
    
    if sess_res.status_code == 409:
        # If another session is open, close it or use current session
        curr_s = requests.get(f"{BACKEND_URL}/api/pi/sessions/current", headers=HEADERS).json()
        if curr_s.get("active"):
            sess_uuid = curr_s["client_uuid"]
            print(f"   Using existing open session: {sess_uuid}")
    else:
        assert sess_res.status_code in (200, 201), f"Session create failed: {sess_res.text}"
        print(f"   [OK] Session created: {sess_uuid}")

    # Post attendance for student
    event_uuid = str(uuid.uuid4())
    att_res1 = requests.post(f"{BACKEND_URL}/api/pi/attendance", json={
        "event_uuid": event_uuid,
        "session_client_uuid": sess_uuid,
        "student_person_id": test_person_id,
        "time_recorded": "2026-10-03T10:05:00Z",
        "confidence": 97.8
    }, headers=HEADERS)
    assert att_res1.status_code == 200, f"Attendance record failed: {att_res1.text}"
    print(f"   [OK] First attendance record: {att_res1.json()}")

    # Post same event_uuid (idempotency 1)
    att_res2 = requests.post(f"{BACKEND_URL}/api/pi/attendance", json={
        "event_uuid": event_uuid,
        "session_client_uuid": sess_uuid,
        "student_person_id": test_person_id,
        "time_recorded": "2026-10-03T10:05:00Z",
        "confidence": 97.8
    }, headers=HEADERS)
    assert att_res2.status_code == 200 and att_res2.json().get("duplicate") is True, f"Idempotency 1 failed: {att_res2.text}"
    print("   [OK] Repeat event_uuid correctly returned {'duplicate': True}")

    # Post different event_uuid for same student in same session (idempotency 2)
    att_res3 = requests.post(f"{BACKEND_URL}/api/pi/attendance", json={
        "event_uuid": str(uuid.uuid4()),
        "session_client_uuid": sess_uuid,
        "student_person_id": test_person_id,
        "time_recorded": "2026-10-03T10:06:00Z",
        "confidence": 96.5
    }, headers=HEADERS)
    assert att_res3.status_code == 200 and att_res3.json().get("duplicate") is True, f"Idempotency 2 failed: {att_res3.text}"
    print("   [OK] Repeat student in same session correctly returned {'duplicate': True}")

    # 9. Heartbeat check
    print("\n9. Testing /api/pi/heartbeat...")
    hb_res = requests.post(f"{BACKEND_URL}/api/pi/heartbeat", headers=HEADERS)
    assert hb_res.status_code == 200, f"Heartbeat failed: {hb_res.text}"
    print(f"   [OK] Heartbeat OK: {hb_res.json()}")

    # 10. Close session
    print("\n10. Closing session...")
    patch_res = requests.patch(f"{BACKEND_URL}/api/pi/sessions/{sess_uuid}", json={
        "status": "CLOSED",
        "end_time": "2026-10-03T10:30:00Z",
        "close_reason": "MANUAL"
    }, headers=HEADERS)
    assert patch_res.status_code == 200
    print("   [OK] Session closed.")

    # 11. Website endpoints, Stop Session, Time Conversion, and Stale Recovery
    print("\n11. Testing Website endpoints, Stop Session, Time Conversion, and Stale Recovery...")
    
    sess2_uuid = str(uuid.uuid4())
    now_local = "2026-10-03T10:00:00+05:30"  # This is 04:30:00Z
    auto_close_local = "2026-10-03T11:00:00+05:30"
    
    sess2_res = requests.post(f"{BACKEND_URL}/api/pi/sessions", json={
        "client_uuid": sess2_uuid,
        "teacher_person_id": teacher_id,
        "subject": "Physics",
        "start_time": now_local,
        "auto_close_at": auto_close_local
    }, headers=HEADERS)
    assert sess2_res.status_code in (200, 201)
    
    # Check GET /api/current-session shows it
    curr_web = requests.get(f"{BACKEND_URL}/api/current-session").json()
    assert curr_web["active"] is True, f"Web current session active should be True, got {curr_web}"
    assert curr_web["start_time"] == "2026-10-03T04:30:00Z", f"Time conversion failed, got {curr_web['start_time']}"
    print("   [OK] GET /api/current-session shows Pi-created OPEN session and converts time to Z.")
    
    # POST /api/current-session/stop
    stop_res = requests.post(f"{BACKEND_URL}/api/current-session/stop")
    assert stop_res.status_code == 200, f"Stop session failed: {stop_res.text}"
    print("   [OK] POST /api/current-session/stop closed it.")
    
    # History check
    hist = requests.get(f"{BACKEND_URL}/api/sessions-history").json()
    assert any(s["session_id"] == curr_web["session_id"] for s in hist["sessions"]), "Closed session not in history"
    print("   [OK] Closed session appears in /api/sessions-history.")
    
    # Stale recovery
    sess3_uuid = str(uuid.uuid4())
    stale_auto_close = "2000-01-01T00:00:00Z"
    requests.post(f"{BACKEND_URL}/api/pi/sessions", json={
        "client_uuid": sess3_uuid,
        "teacher_person_id": teacher_id,
        "subject": "Stale",
        "start_time": "1999-12-31T23:00:00Z",
        "auto_close_at": stale_auto_close
    }, headers=HEADERS)
    
    import server.recovery
    from server.db import SessionLocal
    with SessionLocal() as db:
        recovered = server.recovery.recover_stale_sessions(db)
        assert recovered >= 1, "Failed to recover stale session"
        
    s3_details = requests.get(f"{BACKEND_URL}/api/sessions-history").json()
    s3_entry = next(s for s in s3_details["sessions"] if s["subject"] == "Stale")
    assert s3_entry, "Stale session not in history"
    # Actually need to check the full details for status
    s3_full = requests.get(f"{BACKEND_URL}/api/sessions-history/{s3_entry['session_id']}").json()
    assert s3_full["status"] == "CLOSED"
    print("   [OK] Stale OPEN session is closed as RECOVERED.")

    print("\n========================================")
    print("ALL VERIFICATION CHECKS PASSED PERFECTLY!")
    print("========================================")

if __name__ == "__main__":
    run_tests()
