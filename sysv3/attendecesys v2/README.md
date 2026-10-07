# Smart Attendance System: Specification v2 (Backend + Website)

> **Audience:** the AI IDE (Antigravity) that will build the **backend and website**.
> **Scope:** the **backend server** (database + API + static file hosting) and the **website**. Do NOT write Raspberry Pi code. The Pi is a client of the backend and must follow the contracts in Sections 6 and 7. A short, non-binding list of Pi-side work is in Section 17.
>
> **What changed from v1:** the **laptop (later a cloud server) now owns all data**. The Pi no longer stores people, embeddings, sessions or attendance. It pulls embeddings from the backend, recognizes faces locally, and pushes sessions and attendance back. The website is no longer static-only: it needs a small backend with a database.
>
> **Decision recorded:** enrollment uses **Option A** (the Pi computes the embedding). The embedding step sits behind one interface so it can be swapped to **Option B** (backend computes) for the cloud with no UI changes. See Section 5.

---

## 1. Project Summary

A classroom attendance system that uses face recognition.

- A **Raspberry Pi 3 Model B** in the classroom watches the room through a USB webcam, recognizes faces, decides which lecture is running, and reports attendance to the backend.
- A **laptop** runs the **backend** (database + API) and serves the **website** the admin / teacher uses to **enroll** people and to **view and download attendance reports**.
- The Pi and the laptop talk over the **same local WiFi / hotspot**. **No internet is required** at runtime. Later, the backend moves to a cloud server with the same API.

### What the website does

| # | Responsibility |
|---|---|
| 1 | **Enrollment tab**: enroll students and teachers using the **laptop's webcam** (browser `getUserMedia`) |
| 2 | **Reports tab**: show the **live current session** and **past sessions**, read from the backend |
| 3 | Generate **PDF** and **CSV** attendance reports for any closed session (client-side) |
| 4 | Show **Backend** and **Pi** connection status, and let the user set the Pi's address |
| 5 | Optional: list and remove enrolled people |

### What the website does NOT do

- It does **not** compute face embeddings or run face recognition.
- It does **not** start or stop sessions by default. Sessions are started by the Pi when it recognizes a teacher (Section 4).
- It never sees or handles raw embeddings (Section 5 explains how).

### What the backend does

- Stores people, embeddings, sessions and attendance in a database (SQLite now, Postgres later).
- Serves the website files and the **Website API** (same origin, no CORS needed).
- Serves the **Pi↔Backend API** (`/api/pi/*`) protected by a device key.
- Runs the **duplicate-ID** and **duplicate-face** checks at enrollment.

---

## 2. System Context

```
 Browser (http://localhost:8000)          LAPTOP / future CLOUD                       RASPBERRY PI 3
 ┌──────────────────┐   same-origin    ┌──────────────────────────────┐  HTTP + X-Device-Key  ┌───────────────────────┐
 │ Enrollment tab   │ ───────────────► │ Backend (port 8000)          │ ◄──────────────────── │ Recognition loop      │
 │ Reports tab      │ ◄─────────────── │  • serves website/           │  pulls embeddings     │ in-memory embedding   │
 └──────────────────┘                  │  • Website API  /api/*       │  pushes sessions +    │ cache (+ disk backup) │
        │                              │  • Pi API       /api/pi/*    │  attendance           │ offline event queue   │
        │                              │  • DB (SQLite → Postgres)    │                       │ face_recognition+dlib │
        │                              └──────────────────────────────┘                       └───────────────────────┘
        │                                         ▲                                                      │
        └── enrollment frames (CORS) ─────────────┼──────────────► Pi: POST /api/embed                   │
                                                  └────── Pi relays embedding to backend /api/pi/enroll-complete ◄┘
```

### Who owns what

| Concern | Owner |
|---|---|
| Storage of people, embeddings, sessions, attendance | **Backend (DB)** |
| Duplicate-ID and duplicate-face checks | **Backend** |
| Face detection, quality check, embedding creation | **Pi** (Option A) |
| Live recognition, teacher→subject lookup, session start, 60-min timer | **Pi** |
| Local embedding cache and offline event queue | **Pi** |
| Webcam capture for enrollment | **Website** |
| Forms, validation, UI, status display | **Website** |
| PDF and CSV generation | **Website** |

---

## 3. Fixed Facts About the Pi (design around these)

| Item | Value |
|---|---|
| Device | Raspberry Pi 3 Model B v1.2 (1 GB RAM, quad-core Cortex-A53) |
| OS | Raspberry Pi OS 32-bit, headless |
| Hostname | `attendance-pi.local` (mDNS) |
| Python env | Python 3 venv at `~/attendance/venv` |
| Libraries | OpenCV 4.10.0, dlib 20.0.1, `face_recognition` 1.3.0 + `face_recognition_models`, Flask |
| Embedding model | dlib ResNet via `face_recognition`: **128-d**, Euclidean distance |
| Camera | 720p USB webcam (classroom side) |
| Network | Same local WiFi / hotspot as the laptop, no internet |
| Pi API framework | **Flask**, port **5000** (only `/api/health` and `/api/embed` are needed now) |

### Compatibility rules

1. **The Pi is slow.** Encoding photos can take several seconds. Show a loading state, use a **30 s timeout** for `/api/embed`, never fire parallel heavy requests.
2. **Flask on a Pi 3 handles little concurrency.** The website talks to the Pi only for health checks (every 10 s) and enrollment. Reports never depend on the Pi.
3. **Keep payloads small.** Downscale enrollment frames to about **640×480 JPEG (quality ~0.85)**, send **3 frames**.
4. **Browser→Pi calls are cross-origin** (`localhost:8000` → `attendance-pi.local:5000`). The Pi must enable CORS for the browser origin, including `X-API-Key` if used. On failure show "Cannot reach Pi".
5. **Webcam needs a secure context.** Open the website at `http://localhost:8000` on the laptop (not via a LAN IP), otherwise `getUserMedia` is blocked.
6. **`attendance-pi.local` may not resolve** on some laptops/hotspots. The Pi address must be editable in Settings, with a plain IP as fallback.
7. **The Pi must reach the backend.** The backend binds to `0.0.0.0`, the laptop firewall allows the port, and the Pi is configured with the laptop's **IP** (not `localhost`). Use a fixed IP or DHCP reservation for the laptop on the hotspot.

---

## 4. Session Model (Pi-driven)

```
1. A teacher stands in front of the camera.
2. The Pi recognizes the teacher (using its cached embeddings) and reads the teacher's SUBJECT.
3. The Pi opens a session on the backend: subject = teacher's subject, duration = 60 minutes.
4. While open, every recognized student is posted to the backend as present (once per session).
5. After 60 minutes the Pi closes the session on the backend (AUTO_TIMEOUT).
6. The website shows the live session on the Reports tab and the finished session in history.
```

Consequences for the UI:

- The **teacher enrollment form has a Subject field** (the teacher→subject mapping, stored in the DB).
- The Reports tab shows the **current session read-only**, with a countdown to auto-close.
- Optional **[Stop Session]** button: calls `POST /api/current-session/stop` on the backend. The Pi sees the closed state on its next sync. Hide the button if the backend returns `404`.
- Only **one session is open at a time** (one camera).
- A recognized teacher is recorded as the session's teacher. It is **not** counted in student attendance.
- **Sessions survive Pi or laptop outages:** if the backend is unreachable, the Pi queues events and replays them later (Section 7.5), so the backend may receive a session or attendance rows late. The website must show whatever the backend currently has.

---

## 5. Enrollment Design (Option A)

### Why the Pi creates the embedding

The embedding made at **enrollment** and the one made at **recognition** must come from the **same model, preprocessing and library version**, or matching fails silently. The Pi already runs `face_recognition` + dlib, so the Pi creates enrollment embeddings too. The laptop needs **no dlib install**.

### Why the browser never sees the embedding

The Pi sends the embedding **directly to the backend** using a **one-time enrollment token**. The browser only receives a status or error code.

### Flow

```
Browser                          Backend                               Pi
  │ fill form, capture 3 frames    │                                     │
  │── POST /api/enroll/start ─────►│ validate fields                     │
  │   {role,name,person_id,subject}│ reject DUPLICATE_ID                 │
  │◄── {enrollment_token, ttl} ────│ store token (single-use, 2 min,     │
  │                                │ bound to the submitted fields)      │
  │── POST /api/embed (multipart: token + 3 JPEGs) ─────────────────────►│ 1. exactly ONE face per image
  │                                │                                     │ 2. quality check
  │                                │                                     │ 3. average embedding
  │                                │◄── POST /api/pi/enroll-complete ────│ 4. send {token, embedding, model_id}
  │                                │    (X-Device-Key)                   │    straight to backend
  │                                │ verify + burn token                 │
  │                                │ duplicate-face check vs everyone    │
  │                                │ save person, bump embeddings_version│
  │                                │── 201 / 409 DUPLICATE_FACE ────────►│
  │◄── relayed status + body (no embedding) ─────────────────────────────│ 5. relay result to browser
```

The Pi gets its backend URL and device key from **its own configuration**, never from the browser.

### Swap path to Option B (cloud)

Define one backend function:

```
embed(images: list[bytes]) -> { embedding: float[128], quality: {...} } | EmbedError
```

- **Option A (now):** implemented by calling the Pi.
- **Option B (later):** implemented by running `face_recognition` inside the backend (use Docker; pin the exact library versions the Pi uses).
- Under B the browser calls one backend endpoint (`POST /api/enroll`, multipart) and `/api/enroll/start`, `/api/embed` and `/api/pi/enroll-complete` are no longer used. The UI states in the table below stay identical.

### Rules the UI must follow

- **Unique tag** = unique `roll_no` (students) or `employee_id` (teachers) plus a unique face. The backend enforces both; the UI shows the result.
- A person cannot be both student and teacher (the face check spans both groups).
- Client-side checks before upload: required fields not empty, ID trimmed, name length limit, at least 1 captured frame, consent ticked.
- Optional lightweight quality hints (too dark, too blurry, no face in oval). They never block; the real check is on the Pi.
- Stop the webcam stream when leaving the tab, after enrollment, or on error.
- Never keep captured photos after upload. Nothing is saved on the laptop's disk.
- Enrollment requires **both** backend and Pi online. If either is offline, disable [Enroll] and say which one.

### Enrollment result states

| Response | UI message |
|---|---|
| `201` created | "Enrolled: <name>" and reset the form |
| `409 DUPLICATE_ID` (from `/enroll/start`) | "This Roll No / Employee ID is already enrolled" |
| `409 DUPLICATE_FACE` | "This face is already enrolled as <existing_name> (<existing_id>)" |
| `422 NO_FACE` | "No face found. Look at the camera and retry" |
| `422 MULTIPLE_FACES` | "More than one face in frame. Only the person enrolling should be visible" |
| `422 LOW_QUALITY` | Show the Pi's message (blurry / dark / too small) and offer Retake |
| `422 INVALID_PAYLOAD` | Show field-level errors if provided |
| `401 / 410 BAD_ENROLL_TOKEN`, `TOKEN_EXPIRED` | "Enrollment timed out. Please try again" (restart the flow) |
| `401 BAD_API_KEY` | "API key rejected. Check Settings" |
| `502 BACKEND_UNREACHABLE` (Pi could not reach backend) | "Pi cannot reach the server. Check that the Pi is configured with the laptop's address" |
| Timeout / network error to Pi | "Pi is not responding. Check WiFi and Pi address in Settings" |

---

## 6. API Contract: Website API (Backend, same origin)

**Base URL:** same origin as the website (`/api/...`). No CORS required.
**Format:** JSON. **Timestamps:** ISO 8601 with timezone, e.g. `2026-10-03T10:15:00+05:30`.
**Error body (always):** `{ "error": "ERROR_CODE", "message": "Human readable text" }`
**Auth:** none for the local demo. Optional `ADMIN_PASSWORD` (env) enabling HTTP Basic or a simple login before the backend is exposed beyond the demo network.

### Required endpoints

#### 6.1 `GET /api/health`
```json
{ "ok": true, "server_time": "2026-10-03T10:15:00+05:30", "db": "ok", "embeddings_version": 12 }
```

#### 6.2 `GET /api/pi-status`
Backend's view of the Pi, from the Pi's heartbeats.
```json
{ "last_seen": "2026-10-03T10:14:50+05:30", "online": true, "embeddings_version_on_pi": 12 }
```
`online` = heartbeat within the last 30 s. Used on the Reports tab ("Pi last seen 10 s ago").

#### 6.3 `POST /api/enroll/start`
Request JSON: `{ "role": "student|teacher", "name": "...", "person_id": "...", "subject": "... (teacher only)" }`

Success `200`: `{ "enrollment_token": "<random>", "expires_in": 120 }`
Errors: `409 DUPLICATE_ID`, `422 INVALID_PAYLOAD` (with `fields` map).

#### 6.4 `GET /api/current-session`
Open session (read from the DB, written by the Pi):
```json
{
  "active": true,
  "session_id": 3,
  "subject": "Maths",
  "teacher": { "employee_id": "T01", "name": "Rane Mam" },
  "start_time": "2026-10-03T10:00:00+05:30",
  "auto_close_at": "2026-10-03T11:00:00+05:30",
  "present_count": 2,
  "present": [
    { "roll_no": "101", "name": "Asha Patil", "time_recorded": "2026-10-03T10:02:11+05:30", "confidence": 94.2 }
  ]
}
```
No session: `{ "active": false }`

#### 6.5 `GET /api/sessions-history`
Query: `limit` (default 20), `offset` (default 0), optional `from`, `to` (`YYYY-MM-DD`), optional `subject`. Returns **closed** sessions, newest first.
```json
{
  "total": 37,
  "sessions": [
    {
      "session_id": 2, "subject": "Physics",
      "teacher": { "employee_id": "T02", "name": "Kale Sir" },
      "start_time": "2026-10-02T09:00:00+05:30", "end_time": "2026-10-02T10:00:00+05:30",
      "status": "CLOSED", "close_reason": "AUTO_TIMEOUT", "total_present": 41
    }
  ]
}
```

#### 6.6 `GET /api/sessions-history/{session_id}`
Same fields as a summary item plus `"attendance": [ { "roll_no", "name", "time_recorded", "confidence" } ]`.
`404 SESSION_NOT_FOUND` if missing.

#### 6.7 `GET /api/people?role=student|teacher`
```json
{ "people": [ { "role": "student", "person_id": "101", "name": "Asha Patil", "subject": null, "created_at": "2026-10-01T09:00:00+05:30" } ] }
```
**Embeddings are never returned on this endpoint.**

#### 6.8 `DELETE /api/people/{role}/{person_id}`
Deletes the person and bumps `embeddings_version` so the Pi refreshes its cache. Past attendance rows keep the person's name (see schema `student_name_snapshot`). Deleting a teacher with sessions is allowed; sessions keep `teacher_name_snapshot`.

### Optional endpoint (website degrades gracefully on `404`)

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/current-session/stop` | Manually close the open session (`close_reason = MANUAL_STOP`) |

---

## 7. API Contract: Pi API and Pi↔Backend API

### 7.1 Pi API (served by the Pi on port 5000, called by the browser)

**Optional auth:** `X-API-Key: <key>` if set in Settings.

#### `GET /api/health`
```json
{ "ok": true, "server_time": "...", "model_id": "dlib_face_recognition_resnet_v1" }
```
Used for the Pi badge (poll every 10 s, plus once on load and after saving Settings).

#### `POST /api/embed`
`multipart/form-data`:

| Field | Type | Notes |
|---|---|---|
| `enrollment_token` | string | from `/api/enroll/start`, required |
| `images` | file × 1 to 5 | JPEG, repeated field name, each under about 300 KB |

The Pi creates the embedding, POSTs it to the backend (7.2), and **relays the backend's result** to the browser. It stores nothing.

- `201` → `{ "status": "enrolled", "role": "...", "person_id": "...", "name": "..." }`
- `409` → `{ "error": "DUPLICATE_FACE", "message": "...", "existing": { "role": "student", "person_id": "087", "name": "Rohan Shah" } }`
- Pi-side errors: `NO_FACE` (422), `MULTIPLE_FACES` (422), `LOW_QUALITY` (422), `INVALID_PAYLOAD` (422), `BAD_API_KEY` (401), `BACKEND_UNREACHABLE` (502).

### 7.2 Pi↔Backend API (`/api/pi/*`, served by the backend)

**Auth:** header `X-Device-Key: <key>` on every call. The key comes from the backend's env var `DEVICE_KEY` and the Pi's config. The **browser never receives this key**, and `/api/pi/*` is the **only** place embeddings are served or accepted. Wrong or missing key → `401 BAD_DEVICE_KEY`.

#### Embedding sync

`GET /api/pi/embeddings/version` → `{ "version": 12 }`

`GET /api/pi/embeddings` →
```json
{
  "version": 12,
  "model_id": "dlib_face_recognition_resnet_v1",
  "match_threshold": 0.5,
  "people": [
    { "role": "student", "person_id": "101", "name": "Asha Patil", "subject": null, "embedding": [0.0123, "... 128 floats ..."] },
    { "role": "teacher", "person_id": "T01", "name": "Rane Mam", "subject": "Maths", "embedding": [ "... 128 floats ..." ] }
  ]
}
```
The Pi keeps this in memory (and on disk as a fallback), checks `/version` every **30 to 60 s**, and downloads again only when it changes. It never queries the DB per frame. `match_threshold` is central so it can be tuned without touching the Pi.

#### Enrollment completion

`POST /api/pi/enroll-complete`
```json
{ "enrollment_token": "<token>", "embedding": [ "... 128 floats ..." ], "model_id": "dlib_face_recognition_resnet_v1" }
```
Backend: verify the token (exists, unused, unexpired), check `model_id` matches the stored model, run the **duplicate-face check** (Euclidean distance below the threshold against every stored embedding, both roles), save, bump `embeddings_version`, burn the token.

- `201` → `{ "status": "enrolled", "role", "person_id", "name" }`
- `409 DUPLICATE_FACE` → includes `existing`
- `409 DUPLICATE_ID` (race condition) / `410 TOKEN_EXPIRED` / `401 BAD_ENROLL_TOKEN` / `422 MODEL_MISMATCH`

#### Sessions

`POST /api/pi/sessions`
```json
{ "client_uuid": "6f1c...", "teacher_person_id": "T01", "subject": "Maths",
  "start_time": "2026-10-03T10:00:00+05:30", "auto_close_at": "2026-10-03T11:00:00+05:30" }
```
→ `{ "session_id": 3 }`. **Idempotent on `client_uuid`**: repeating the call returns the same session. If another session is already open, respond `409 SESSION_ALREADY_OPEN` with the open session's id.

`PATCH /api/pi/sessions/{client_uuid}`
```json
{ "status": "CLOSED", "end_time": "2026-10-03T11:00:00+05:30", "close_reason": "AUTO_TIMEOUT" }
```

`GET /api/pi/sessions/current` → open session (or `{ "active": false }`), so the Pi can notice a manual stop from the website.

#### Attendance

`POST /api/pi/attendance`
```json
{ "event_uuid": "a91b...", "session_client_uuid": "6f1c...", "student_person_id": "101",
  "time_recorded": "2026-10-03T10:02:11+05:30", "confidence": 94.2 }
```
**Idempotent** on `event_uuid` and on `(session, student)`: duplicates return `200` with `"duplicate": true` and are ignored. Accepts a batch form `{ "events": [ ... ] }` for queue replay.

#### Heartbeat

`POST /api/pi/heartbeat` → `{ "embeddings_version": 12, "queued_events": 0 }`, sent every 10 to 15 s. Returns `{ "ok": true, "server_time": "..." }`.

### 7.3 Rules for the website's API client

- All calls go through **one API client module** with two clients: `backend` (same origin) and `pi` (configurable address, optional `X-API-Key`). No raw `fetch` elsewhere.
- Default timeout **8 s**; `/api/embed` timeout **30 s**.
- Retry GET requests once on network failure. **Never auto-retry** `POST /api/enroll/start` or `POST /api/embed`. Let the user press the button again.
- Treat any non-2xx response as `{ error, message }`. If the body is not JSON, show a generic error.

### 7.4 Rules for the Pi's use of the backend (contract, not Pi code)

- Treat the backend as the source of truth. Use the cached embeddings for recognition, and match against `match_threshold`.
- Generate `client_uuid` / `event_uuid` locally so events are replay-safe.

### 7.5 Offline queue (Pi side, required for reliability)

If the backend is unreachable, the Pi appends session and attendance events to a local queue (disk-backed) and replays them in order when the backend returns. Without this, a laptop sleeping mid-lecture loses attendance. The backend's idempotency rules (7.2) make replay safe.

---

## 8. Database

SQLite now, Postgres later. Use an ORM (SQLAlchemy or Prisma) with migrations, so the move is a connection-string change.

```sql
people (
  id INTEGER PK,
  role TEXT CHECK (role IN ('student','teacher')),
  person_id TEXT NOT NULL,           -- roll no or employee id
  name TEXT NOT NULL,
  subject TEXT NULL,                 -- teachers only
  embedding BLOB NOT NULL,           -- 128 x float32, little-endian = 512 bytes
  model_id TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL,
  UNIQUE (role, person_id)
);

sessions (
  id INTEGER PK,
  client_uuid TEXT UNIQUE NOT NULL,  -- generated by the Pi, for idempotency
  subject TEXT NOT NULL,
  teacher_person_id TEXT NULL,
  teacher_name_snapshot TEXT NOT NULL,
  start_time TIMESTAMP NOT NULL,
  auto_close_at TIMESTAMP NOT NULL,
  end_time TIMESTAMP NULL,
  status TEXT CHECK (status IN ('OPEN','CLOSED')),
  close_reason TEXT NULL             -- AUTO_TIMEOUT | MANUAL_STOP | RECOVERED
);

attendance (
  id INTEGER PK,
  session_id INTEGER REFERENCES sessions(id),
  student_person_id TEXT NOT NULL,
  student_name_snapshot TEXT NOT NULL,
  time_recorded TIMESTAMP NOT NULL,
  confidence REAL NOT NULL,          -- 0 to 100
  event_uuid TEXT UNIQUE NOT NULL,
  UNIQUE (session_id, student_person_id)
);

enroll_tokens (
  token TEXT PK, role TEXT, person_id TEXT, name TEXT, subject TEXT,
  expires_at TIMESTAMP, used INTEGER DEFAULT 0
);

meta (key TEXT PK, value TEXT);      -- embeddings_version, model_id, pi_last_seen, ...
```

Rules:
- Store timestamps in UTC; return them with the local offset.
- Bump `embeddings_version` in the **same transaction** as every enroll or delete.
- Only one `OPEN` session may exist (enforce in code and with a partial unique index where supported).
- A session still `OPEN` long after `auto_close_at` (Pi crashed) is closed by the backend with `close_reason = RECOVERED` (check on startup and periodically).
- Duplicate-face check is a linear scan over all embeddings, which is fine for classroom scale. Revisit with a vector index only at large scale.

---

## 9. Website Pages

Single-page app, header and two main tabs. Desktop-first, responsive down to tablet width.

### 9.1 Header (always visible)

- App name: **Smart Attendance System**
- Tabs: **Enrollment** | **Reports**
- **Two status badges:**
  - **Server:** from `GET /api/health` (green / red / grey "Checking…")
  - **Pi:** from the Pi's `/api/health` via the browser (green / red / grey). Reports also shows "Pi last seen …" from `/api/pi-status`.
- **Settings** (gear): Pi address and optional Pi API key, saved in `localStorage`; **[Test connection]** button. The backend address is not configurable (same origin).

### 9.2 Enrollment tab

- Role toggle: **Student | Teacher**
- Fields: Name; Roll No (student) or Employee ID + **Subject** (teacher)
- Live webcam preview with a face-guide oval, camera selector if several cameras exist
- **[Capture Face]** (grabs 3 frames), thumbnails with **Retake**
- Consent checkbox: "The person has agreed to their face being used for attendance"
- **[Enroll]** with spinner and full result-state handling from Section 5. Disabled with a reason if the server or Pi is offline.
- Handle camera errors: permission denied, no camera found, camera busy
- **Enrolled people** table (uses `GET /api/people` and `DELETE`, which are now part of the backend; delete asks for confirmation)

### 9.3 Reports tab

**A. Live session card (top)**
- If `active`: big **Present count**, subject, teacher, start time, **countdown to auto-close**, scrolling list of students (newest first)
- If not active: "No lecture running. A session starts automatically when a teacher is recognized."
- Polls `/api/current-session` every **5 s**, **only while the tab is visible** (Page Visibility API)
- When a session ends it moves into history without a manual refresh
- Shows "Pi last seen …" and a warning if the Pi is offline during an active session ("Attendance may be delayed")

**B. History table**
- Columns: Session ID, Date, Subject, Teacher, Start, End, Total Present, Actions
- Filters: date range, subject; pagination (20 per page)
- Row click opens a detail view (`/api/sessions-history/{id}`) showing every student row
- Row actions: **[Download PDF]** and **[Download CSV]**
- Empty state: "No sessions yet"
- **Works with the Pi off**, since all data comes from the backend

### 9.4 States every view needs

Loading skeleton, empty state, error state with **Retry**, a clear **"Server offline"** banner (blocks everything) and a **"Pi offline"** banner (disables enrollment only).

---

## 10. Report Output (generated in the browser)

Use **jsPDF + jspdf-autotable** for PDF and plain JS for CSV, built from `GET /api/sessions-history/{id}`. Only **closed** sessions get download buttons (a live session may be exported, labelled "in progress").

### PDF layout

```
Smart Attendance System
Official Lecture Attendance Sheet – <Subject>

Subject: <Subject>                     Teacher: <Teacher Name>
Start Time: <YYYY-MM-DD HH:MM:SS>      End Time: <YYYY-MM-DD HH:MM:SS>
Session ID: #<N>                       Total Present: <count> students
Status: CLOSED

# | Roll No. | Student Name | Time Recorded | Match Confidence | Status
1 | 101      | ...          | 10:02:11      | 94%              | Present

(If nobody: "No students recorded for this session")

Report generated automatically on <timestamp> via Smart Attendance System.
```

- No "Camera Source" field. **Total Present** is a clear count in the header.
- Multi-page tables repeat the header row and show page numbers.
- Times in local time `HH:MM:SS`; dates `YYYY-MM-DD`.

### CSV columns

```
session_id,subject,teacher,date,start_time,end_time,total_present,sr_no,roll_no,student_name,time_recorded,match_confidence,status
```

- One row per present student; session fields repeat on every row.
- Escape commas and quotes; add a UTF-8 BOM for Excel.
- If nobody was present, output one row with session fields and empty student columns.

### File names

`Attendance_<Subject>_<YYYY-MM-DD>_S<session_id>.pdf` and `.csv` (replace spaces and unsafe characters in the subject with `_`).

---

## 11. Tech Stack

| Layer | Choice |
|---|---|
| Backend | **Python FastAPI** (preferred, matches the Pi's Python stack) or Node/Express. Runs on `0.0.0.0:8000` |
| Database | SQLite file now → Postgres later, via **SQLAlchemy** + Alembic (or Prisma) |
| Website | HTML + CSS + vanilla JS (ES modules), served by the backend as static files. React + Vite acceptable if the build output is served the same way |
| Webcam | `navigator.mediaDevices.getUserMedia`, frame grab via `<canvas>` → JPEG blob |
| PDF / CSV | jsPDF + jspdf-autotable / plain JS |
| Settings storage | `localStorage` (Pi address, Pi API key only) |
| Config | Backend `.env`: `DEVICE_KEY`, `DATABASE_URL`, `PORT`, optional `ADMIN_PASSWORD`, `MATCH_THRESHOLD` |
| Run locally | `python -m server` (or `uvicorn`), open `http://localhost:8000` |

No third-party services. **Vendor all libraries locally** so the site works offline.

---

## 12. Dev Tools (required)

### 12.1 Mock Pi (`tools/mock-pi/`)
Implements the **Pi API** only (`/api/health`, `/api/embed`) on port `5000` with CORS enabled.
- `/api/embed` simulates 3 to 6 s latency, generates a **fake 128-d embedding**, and calls the real backend's `/api/pi/enroll-complete` with the token, relaying the result.
- Failure modes via env var or query flag: `NO_FACE`, `MULTIPLE_FACES`, `LOW_QUALITY`, Pi offline, slow response, bad API key.
- `DUPLICATE_FACE` and `DUPLICATE_ID` come from the **real backend logic** (seed the DB so they can be triggered).

### 12.2 Pi simulator (`tools/pi-simulator/`)
A script that behaves like the Pi toward the backend: authenticates with `X-Device-Key`, syncs embeddings, opens a session for a seeded teacher, posts attendance over time, closes the session after a configurable duration, sends heartbeats, and can **simulate an outage** and replay a queue to test idempotency.

### 12.3 Seed data
Seed script creating sample students and teachers (with fake embeddings), one open session with a 60-minute countdown, and about 10 closed sessions with attendance. Seed data lives **only** in the seed script, never in the final website code.

Switching from mock to the real Pi must require **only changing the Pi address in Settings**.

---

## 13. UI / UX Guidelines

- Clean, modern, professional; suitable for a college demo. Light and dark theme (follow system).
- Clear visual hierarchy; the **live Present count** is the most prominent element on the Reports tab.
- Status colors: green (online / success), amber (warning), red (offline / error).
- Large primary buttons; disabled and loading states on every async action.
- Accessible: labelled inputs, keyboard navigation, sufficient contrast, `aria-live` for status and result messages.

---

## 14. Security and Privacy

- Face images are biometric data. They go **only to the Pi**, are held in browser memory just long enough to upload, and are never written to disk, `localStorage` or logs on the laptop. The backend never receives images under Option A.
- **Embeddings are biometric data too.** They exist only in the DB and on `/api/pi/*`. Never show or log them. Never return them from website endpoints.
- `/api/pi/*` requires `X-Device-Key`. The key is never sent to the browser, never committed to git (use `.env`).
- Enrollment tokens are single-use, short-lived (2 min), and bound to the submitted fields. The Pi gets the backend URL from its own config, never from the request.
- Consent checkbox is mandatory before enrolling.
- Escape all server-supplied text before rendering (names, subjects).
- Validate and trim inputs on the client; the backend validates again (length limits, allowed characters for IDs).
- The backend binds to `0.0.0.0` so the Pi can reach it, which also exposes it to everyone on the same hotspot. Use `ADMIN_PASSWORD` if the network is shared.
- DB file and `.env` go in `.gitignore`. Add a simple backup (copy the DB file on a schedule or on startup).
- **Before moving to the cloud:** HTTPS, real admin authentication, per-device keys with rotation, rate limiting on enrollment, and a data retention / deletion policy for biometric data.

---

## 15. Project Structure

```
attendance-project/
├── server/
│   ├── main.py                 # app, static hosting, router wiring
│   ├── config.py               # env settings
│   ├── db.py                   # engine, session
│   ├── models.py               # SQLAlchemy models (Section 8)
│   ├── schemas.py              # request/response models
│   ├── routes_web.py           # Website API (Section 6)
│   ├── routes_pi.py            # /api/pi/* (Section 7.2)
│   ├── embedder.py             # embed() interface: PiEmbedder now, LocalEmbedder later
│   ├── matching.py             # duplicate-face check
│   ├── tokens.py               # enrollment tokens
│   ├── recovery.py             # closes stale OPEN sessions
│   ├── seed.py                 # sample data (dev only)
│   └── migrations/
├── website/
│   ├── index.html
│   ├── css/styles.css
│   ├── js/
│   │   ├── app.js              # tab routing, init
│   │   ├── api.js              # backend + Pi clients (Section 7.3)
│   │   ├── settings.js         # Pi address / key
│   │   ├── status.js           # server + Pi badges
│   │   ├── enrollment.js       # form, capture, 3-step flow
│   │   ├── camera.js           # getUserMedia, capture, JPEG resize
│   │   ├── people.js           # enrolled people list
│   │   ├── reports.js          # live card, history, detail
│   │   ├── pdf.js
│   │   ├── csv.js
│   │   └── utils.js
│   └── vendor/                 # jsPDF, autotable (local)
├── tools/
│   ├── mock-pi/
│   └── pi-simulator/
├── .env.example
├── .gitignore
└── README.md                   # run backend, run mocks, point the Pi at the laptop, switch to the real Pi
```

---

## 16. Build Order

1. Backend skeleton, config, DB models and migrations, static hosting of `website/`.
2. Website API (health, people, sessions, history) plus the seed script.
3. Website shell: header, tabs, Settings, API client, status badges.
4. Reports tab (live card with 5 s polling and countdown, history, detail).
5. PDF and CSV generation.
6. `/api/pi/*` endpoints (embeddings sync, sessions, attendance, heartbeat) and the **Pi simulator**.
7. Enrollment: `/api/enroll/start`, **mock Pi** `/api/embed`, `/api/pi/enroll-complete`, the browser flow and every result state.
8. Enrolled people list, delete, `embeddings_version` bump verified.
9. Error, empty, loading and offline states everywhere; stale-session recovery; polish; README.
10. Integration with the real Pi: Pi-side work (Section 17), then change only the Pi address in Settings and the Pi's backend URL.

---

## 17. Pi-Side Work (reference only, not built by this project)

For whoever updates the Pi. Antigravity should not write this, but the backend must be built so this works:

1. Config file with `BACKEND_URL` (laptop IP, port 8000) and `DEVICE_KEY`.
2. Flask: add `POST /api/embed` per Section 7.1, enable CORS for the browser origin (`http://localhost:8000`) including `X-API-Key`.
3. Embedding cache: download `/api/pi/embeddings`, hold in memory, save to disk, re-check `/version` every 30 to 60 s.
4. Recognition loop uses the cache and `match_threshold`.
5. On teacher recognized: `POST /api/pi/sessions`; on student recognized: `POST /api/pi/attendance`; at 60 min: `PATCH` to close.
6. Heartbeat every 10 to 15 s.
7. Disk-backed offline queue with replay (Section 7.5).
8. Remove local storage of people and attendance.

---

## 18. Acceptance Criteria

- [ ] Backend runs on the laptop, serves the website, and stores everything in a DB file. Restarting loses nothing.
- [ ] Works fully **offline** (no internet) on the local network.
- [ ] Switching mock ↔ real Pi requires only changing the Pi address in Settings (and the Pi's own backend URL).
- [ ] Student and teacher enrollment work with the laptop webcam; the teacher form includes Subject.
- [ ] The browser never receives an embedding, and no photos or embeddings are stored or logged on the laptop outside the DB.
- [ ] Duplicate ID and duplicate face are caught by the backend; every Section 5 result state shows a clear message; the form never freezes.
- [ ] Enrolling or deleting a person bumps `embeddings_version`, and the Pi simulator picks up the change.
- [ ] `/api/pi/*` rejects requests without the correct `X-Device-Key`; website endpoints never expose embeddings.
- [ ] Replaying the same attendance or session events twice creates no duplicates.
- [ ] Live session card updates every 5 s only while the tab is visible, with a countdown to auto-close.
- [ ] History supports date/subject filters, pagination, per-session detail, and works with the Pi off.
- [ ] PDF matches Section 10 and CSV has exactly the listed columns; file names follow the pattern.
- [ ] A session left open after a Pi crash is closed as `RECOVERED`.
- [ ] Server offline / Pi offline / slow responses show clear messages, not a blank screen.

---

## 19. Out of Scope

- Pi code (Section 17 lists it for reference only).
- Running dlib / `face_recognition` on the laptop under Option A (it becomes in scope only if switching to Option B).
- Cloud deployment, HTTPS and multi-tenant auth (Section 14 lists the prerequisites).
- The production scale-up vision (repurposed Android phone with ML Kit + MobileFaceNet, optional CCTV/RTSP). Presentation only.

---

## 20. Assumptions to Confirm

1. The Pi will add `POST /api/embed` and relay results as described in Sections 5 and 7.1.
2. The Pi enables CORS for `http://localhost:8000`.
3. The Pi can reach the laptop by a stable IP, and the laptop firewall allows port 8000.
4. A shared `DEVICE_KEY` is acceptable for the demo.
5. Each teacher maps to **one** subject.
6. Session length is fixed at 60 minutes and closes automatically.
7. Confidence is reported by the Pi as a 0 to 100 percentage.
8. The match threshold (default 0.5, stricter than the library's 0.6) is tuned on real classroom data and stored centrally on the backend.

---

## 21. Setup and Run Instructions

### 1. Start the server
Run the following exact command from the project folder:
```bash
python -m server.main
```
The server will start and listen on `0.0.0.0:8000`.

### 2. Find the laptop IP
To connect the Raspberry Pi or other devices on the same network to the backend, you need your laptop's IP address.
Run the following command in PowerShell:
```bash
ipconfig
```
Look for `IPv4 Address` under your active Wi-Fi or Ethernet adapter.

### 3. Windows Firewall Configuration
To allow inbound connections to the server on port 8000, run this command in **PowerShell as Administrator**:
```powershell
New-NetFirewallRule -DisplayName "Attendance 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Any
```

### 4. Seed Data (Optional)
If you want to pre-load the database with test data (teachers, students, past sessions, etc.), you can run the seed script.
This is optional and **never automatic**.
```bash
python -m server.seed
```