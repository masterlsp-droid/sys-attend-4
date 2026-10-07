from fastapi import FastAPI, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import requests
import asyncio
import random

app = FastAPI(title="Mock Pi API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BACKEND_URL = "http://127.0.0.1:8000"
DEVICE_KEY = "default-dev-key"

@app.get("/api/health")
def health():
    return {"ok": True, "server_time": "2026-10-03T00:00:00Z", "model_id": "dlib_face_recognition_resnet_v1"}

@app.post("/api/embed")
async def embed(
    enrollment_token: str = Form(...),
    images: list[UploadFile] = File(...)
):
    await asyncio.sleep(2)
    embedding = [random.random() for _ in range(128)]
    
    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/pi/enroll-complete",
            json={
                "enrollment_token": enrollment_token,
                "embedding": embedding,
                "model_id": "dlib_face_recognition_resnet_v1"
            },
            headers={"X-Device-Key": DEVICE_KEY},
            timeout=5
        )
        return JSONResponse(status_code=resp.status_code, content=resp.json())
    except Exception as e:
        return JSONResponse(status_code=502, content={"error": "BACKEND_UNREACHABLE", "message": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
