from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
import datetime
import math
import struct
from typing import Optional
from server.db import get_db
from server import models
from server.config import DEVICE_KEY, MATCH_THRESHOLD

router = APIRouter()

def verify_device_key(x_device_key: str = Header(None)):
    if x_device_key != DEVICE_KEY:
        raise HTTPException(status_code=401, detail={"error": "BAD_DEVICE_KEY", "message": "Invalid device key"})

class EnrollCompleteRequest(BaseModel):
    enrollment_token: str
    embedding: list[float]
    model_id: str

def euclidean_distance(a, b):
    a_floats = struct.unpack(f"{len(a)//4}f", a) if isinstance(a, (bytes, bytearray)) else a
    b_floats = struct.unpack(f"{len(b)//4}f", b) if isinstance(b, (bytes, bytearray)) else b
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a_floats, b_floats)))

def parse_time(ts: str) -> datetime.datetime:
    dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return dt

@router.get("/embeddings/version", dependencies=[Depends(verify_device_key)])
def get_embeddings_version(db: Session = Depends(get_db)):
    meta_v = db.query(models.Meta).filter(models.Meta.key == "embeddings_version").first()
    return {"version": int(meta_v.value) if meta_v else 0}

@router.get("/embeddings", dependencies=[Depends(verify_device_key)])
def get_embeddings(db: Session = Depends(get_db)):
    meta_v = db.query(models.Meta).filter(models.Meta.key == "embeddings_version").first()
    meta_model = db.query(models.Meta).filter(models.Meta.key == "model_id").first()
    version = int(meta_v.value) if meta_v else 0
    model_id = meta_model.value if meta_model else "dlib_face_recognition_resnet_v1"
    
    people = db.query(models.Person).all()
    people_list = []
    for p in people:
        emb_floats = struct.unpack(f"{len(p.embedding)//4}f", p.embedding)
        people_list.append({
            "role": p.role,
            "person_id": p.person_id,
            "name": p.name,
            "subject": p.subject,
            "class_name": getattr(p, 'class_name', None),
            "embedding": list(emb_floats)
        })
    return {
        "version": version,
        "model_id": model_id,
        "match_threshold": MATCH_THRESHOLD,
        "people": people_list
    }

@router.post("/enroll-complete", status_code=201, dependencies=[Depends(verify_device_key)])
def enroll_complete(req: EnrollCompleteRequest, db: Session = Depends(get_db)):
    if len(req.embedding) != 128 or not all(math.isfinite(x) for x in req.embedding):
        raise HTTPException(status_code=422, detail={"error": "INVALID_PAYLOAD", "message": "Embedding must be 128 finite numbers"})

    meta_model = db.query(models.Meta).filter(models.Meta.key == "model_id").first()
    expected_model = meta_model.value if meta_model else "dlib_face_recognition_resnet_v1"
    if req.model_id != expected_model:
        raise HTTPException(status_code=422, detail={"error": "MODEL_MISMATCH", "message": "Model mismatch"})

    token_record = db.query(models.EnrollToken).filter(models.EnrollToken.token == req.enrollment_token).first()
    if not token_record or token_record.used:
        raise HTTPException(status_code=401, detail={"error": "BAD_ENROLL_TOKEN", "message": "Token invalid or used"})
    if token_record.expires_at < datetime.datetime.utcnow():
        raise HTTPException(status_code=410, detail={"error": "TOKEN_EXPIRED", "message": "Token expired"})
    
    # duplicate face check
    all_people = db.query(models.Person).all()
    for p in all_people:
        if euclidean_distance(req.embedding, p.embedding) < MATCH_THRESHOLD:
            raise HTTPException(status_code=409, detail={
                "error": "DUPLICATE_FACE", 
                "message": "Face already enrolled", 
                "existing": {"role": p.role, "person_id": p.person_id, "name": p.name}
            })
    
    # Save person
    embedding_bytes = struct.pack(f"{len(req.embedding)}f", *req.embedding)
    person = models.Person(
        role=token_record.role,
        person_id=token_record.person_id,
        name=token_record.name,
        subject=token_record.subject,
        class_name=getattr(token_record, 'class_name', None),
        embedding=embedding_bytes,
        model_id=req.model_id
    )
    db.add(person)
    token_record.used = 1
    
    # bump version
    meta_v = db.query(models.Meta).filter(models.Meta.key == "embeddings_version").first()
    if not meta_v:
        meta_v = models.Meta(key="embeddings_version", value="1")
        db.add(meta_v)
    else:
        meta_v.value = str(int(meta_v.value) + 1)
    
    db.commit()
    return {"status": "enrolled", "role": person.role, "person_id": person.person_id, "name": person.name}


class SessionCreateRequest(BaseModel):
    client_uuid: str
    teacher_person_id: str
    subject: str
    start_time: str
    auto_close_at: str

@router.post("/sessions", status_code=201, dependencies=[Depends(verify_device_key)])
def create_session(req: SessionCreateRequest, db: Session = Depends(get_db)):
    existing = db.query(models.Session).filter(models.Session.client_uuid == req.client_uuid).first()
    if existing:
        return {"session_id": existing.id}
        
    active = db.query(models.Session).filter(models.Session.status == "OPEN").first()
    if active:
        raise HTTPException(status_code=409, detail={"error": "SESSION_ALREADY_OPEN", "message": "Another session is open", "session_id": active.id})
        
    teacher = db.query(models.Person).filter(models.Person.role == "teacher", models.Person.person_id == req.teacher_person_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail={"error": "TEACHER_NOT_FOUND", "message": "Teacher not found"})
        
    new_session = models.Session(
        client_uuid=req.client_uuid,
        subject=req.subject,
        teacher_person_id=req.teacher_person_id,
        teacher_name_snapshot=teacher.name,
        start_time=parse_time(req.start_time),
        auto_close_at=parse_time(req.auto_close_at),
        status="OPEN"
    )
    db.add(new_session)
    db.commit()
    return {"session_id": new_session.id}

class SessionPatchRequest(BaseModel):
    status: str
    end_time: str
    close_reason: str

@router.patch("/sessions/{client_uuid}", dependencies=[Depends(verify_device_key)])
def patch_session(client_uuid: str, req: SessionPatchRequest, db: Session = Depends(get_db)):
    session = db.query(models.Session).filter(models.Session.client_uuid == client_uuid).first()
    if not session:
        raise HTTPException(status_code=404, detail={"error": "SESSION_NOT_FOUND", "message": "Session not found"})
    session.status = req.status
    session.end_time = parse_time(req.end_time)
    session.close_reason = req.close_reason
    db.commit()
    return {"status": "ok"}

@router.get("/sessions/current", dependencies=[Depends(verify_device_key)])
def get_current_session(db: Session = Depends(get_db)):
    active = db.query(models.Session).filter(models.Session.status == "OPEN").first()
    if active:
        return {"active": True, "session_id": active.id, "client_uuid": active.client_uuid}
    return {"active": False}

class AttendanceRequest(BaseModel):
    event_uuid: str
    session_client_uuid: str
    student_person_id: str
    time_recorded: str
    confidence: float

@router.post("/attendance", status_code=200, dependencies=[Depends(verify_device_key)])
def post_attendance(req: AttendanceRequest, db: Session = Depends(get_db)):
    session = db.query(models.Session).filter(models.Session.client_uuid == req.session_client_uuid).first()
    if not session:
        raise HTTPException(status_code=404, detail={"error": "SESSION_NOT_FOUND", "message": "Session not found"})
    
    student = db.query(models.Person).filter(models.Person.role == "student", models.Person.person_id == req.student_person_id).first()
    if not student:
        raise HTTPException(status_code=404, detail={"error": "STUDENT_NOT_FOUND", "message": "Student not found"})
        
    try:
        dt = parse_time(req.time_recorded)
    except:
        dt = datetime.datetime.utcnow()
        
    existing_event = db.query(models.Attendance).filter(models.Attendance.event_uuid == req.event_uuid).first()
    if existing_event:
        return {"duplicate": True}
        
    existing_att = db.query(models.Attendance).filter(
        models.Attendance.session_id == session.id,
        models.Attendance.student_person_id == student.person_id
    ).first()
    if existing_att:
        return {"duplicate": True}

    att = models.Attendance(
        session_id=session.id,
        student_person_id=student.person_id,
        student_name_snapshot=student.name,
        time_recorded=dt,
        confidence=req.confidence,
        event_uuid=req.event_uuid
    )
    db.add(att)
    try:
        db.commit()
    except Exception as e:
        db.rollback() 
        return {"duplicate": True}
    return {"status": "recorded"}

class HeartbeatRequest(BaseModel):
    embeddings_version: Optional[int] = None
    queued_events: Optional[int] = None

@router.post("/heartbeat", dependencies=[Depends(verify_device_key)])
def post_heartbeat(req: HeartbeatRequest = None, db: Session = Depends(get_db)):
    now_str = datetime.datetime.utcnow().isoformat() + "Z"
    
    meta_ls = db.query(models.Meta).filter(models.Meta.key == "pi_last_seen").first()
    if not meta_ls:
        db.add(models.Meta(key="pi_last_seen", value=now_str))
    else:
        meta_ls.value = now_str
        
    if req and req.embeddings_version is not None:
        meta_ev = db.query(models.Meta).filter(models.Meta.key == "pi_embeddings_version").first()
        if not meta_ev:
            db.add(models.Meta(key="pi_embeddings_version", value=str(req.embeddings_version)))
        else:
            meta_ev.value = str(req.embeddings_version)
            
    db.commit()
    
    meta_v = db.query(models.Meta).filter(models.Meta.key == "embeddings_version").first()
    version = int(meta_v.value) if meta_v else 0
    return {"ok": True, "server_time": now_str, "embeddings_version": version, "queued_events": 0}
