# Smart Attendance System - Website Frontend

This directory contains the HTML, CSS, and Vanilla JavaScript for the frontend of the Smart Attendance System.

## Recent Workflow & Architectural Decisions

During the development of the frontend and API, we made several key decisions that differ from the initial specification (v1):

### 1. Enrollment Uses Backend (Option B)
We decided to implement **Option B** for enrollment.
*   **Decision:** The backend (laptop/server) now handles face embeddings using local `face_recognition` and `dlib` installations, removing the burden from the Raspberry Pi during enrollment.
*   **Workflow:** When enrolling a new student or teacher, the website captures frames from the webcam and sends them directly to the backend via `POST /api/enroll` using `multipart/form-data`.
*   **Result:** The Pi is no longer required for the enrollment process to function. 

### 2. Session Management
*   **Decision:** We added the ability to manually start and end sessions directly from the website.
*   **Workflow:** The UI uses `POST /api/current-session/start` and `POST /api/current-session/end` to control the active session. This provides a fallback and more control if the Pi is unable to automatically start a session.

### 3. API Client Structure
The API calls in `js/api.js` are split logically:
*   **`backendApi`**: Communicates with the local server (same origin). It handles all core database tasks, enrollment, session management, and retrieving history.
*   **`piApi`**: Communicates directly with the Raspberry Pi (cross-origin). It is primarily used for checking the Pi's health and triggering any local recognition tasks on the Pi.

### 4. Tech Stack
*   **Vanilla JS (ES Modules):** The application logic is split into separate modules (`api.js`, `enrollment.js`, `reports.js`, etc.) for maintainability without needing a bundler.
*   **No Build Step:** The static files are served directly by the backend FastAPI/Python server.

## File Structure

*   `index.html`: The single-page application entry point containing the Enrollment and Reports tabs.
*   `css/`: Contains all Vanilla CSS styling.
*   `js/`:
    *   `app.js`: Main initialization and tab routing.
    *   `api.js`: All `fetch` wrappers for backend and Pi communication.
    *   `enrollment.js`: Webcam capture, form validation, and enrollment logic.
    *   `reports.js`: Live session polling and history rendering.
    *   `settings.js`, `status.js`, `utils.js`: Helpers for UI and local storage.
*   `vendor/`: Third-party libraries (e.g., jsPDF) stored locally for offline use.
