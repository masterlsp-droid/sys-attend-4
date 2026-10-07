from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from server.db import engine, Base
from server import models
from server.routes_web import router as web_router
from server.routes_pi import router as pi_router
import os
from contextlib import asynccontextmanager
import asyncio
from server.recovery import recover_stale_sessions
from server.db import SessionLocal

@asynccontextmanager
async def lifespan(app: FastAPI):
    with SessionLocal() as db:
        recover_stale_sessions(db)
        
    async def run_recovery():
        while True:
            await asyncio.sleep(60)
            with SessionLocal() as db:
                recover_stale_sessions(db)
                
    task = asyncio.create_task(run_recovery())
    yield
    task.cancel()

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Attendance System API", lifespan=lifespan)

app.include_router(web_router, prefix="/api")
app.include_router(pi_router, prefix="/api/pi")

# Mount static files at the end
os.makedirs("website", exist_ok=True)
app.mount("/", StaticFiles(directory="website", html=True), name="website")

if __name__ == "__main__":
    import uvicorn
    from server.config import PORT
    uvicorn.run("server.main:app", host="0.0.0.0", port=PORT, reload=True)
