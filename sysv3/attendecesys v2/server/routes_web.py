from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from server.db import get_db
from server import models, tokens
from typing import Optional, List
import struct
import math
from server.config import MATCH_THRESHOLD
import datetime
import uuid

router = APIRouter()

def format_time(dt: Optional[datetime.datetime]) -> Optional[str]:
    if not dt: return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return dt.isoformat() + "Z"

class ClassCreateRequest(BaseModel):
    name: str

class EnrollStartRequest(BaseModel):
    role: str
    name: str
    person_id: str
    subject: Optional[str] = None
    class_name: Optional[str] = None

@router.get("/classes")
def list_classes(db: Session = Depends(get_db)):
    classes = db.query(models.ClassGroup).order_by(models.ClassGroup.name.asc()).all()
    result = []
    for c in classes:
        student_count = db.query(models.Person).filter(
            models.Person.role == "student", 
            models.Person.class_name == c.name
        ).count()
        result.append({
            "id": c.id,
            "name": c.name,
            "student_count": student_count,
            "created_at": format_time(c.created_at)
        })
    return {"classes": result}

@router.post("/classes")
def create_class(req: ClassCreateRequest, db: Session = Depends(get_db)):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail={"error": "INVALID_NAME", "message": "Class name cannot be empty"})
    
    existing = db.query(models.ClassGroup).filter(models.ClassGroup.name.ilike(name)).first()
    if existing:
        raise HTTPException(status_code=409, detail={"error": "DUPLICATE_CLASS", "message": f"Class '{name}' already exists"})
    
    new_class = models.ClassGroup(name=name)
    db.add(new_class)
    db.commit()
    db.refresh(new_class)
    return {
        "id": new_class.id,
        "name": new_class.name,
        "student_count": 0,
        "created_at": format_time(new_class.created_at)
    }

@router.delete("/classes/{class_id}")
def delete_class(class_id: int, db: Session = Depends(get_db)):
    c = db.query(models.ClassGroup).filter(models.ClassGroup.id == class_id).first()
    if not c:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Class not found"})
    
    # Nullify class_name for enrolled students so they aren't deleted
    db.query(models.Person).filter(models.Person.class_name == c.name).update({"class_name": None})
    db.delete(c)
    db.commit()
    return {"status": "deleted", "id": class_id}

@router.get("/dashboard-stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_classes = db.query(models.ClassGroup).count()
    total_students = db.query(models.Person).filter(models.Person.role == "student").count()
    total_teachers = db.query(models.Person).filter(models.Person.role == "teacher").count()
    total_sessions = db.query(models.Session).count()
    
    return {
        "total_classes": total_classes,
        "total_students": total_students,
        "total_teachers": total_teachers,
        "total_sessions": total_sessions
    }

@router.post("/enroll/start")
def enroll_start(req: EnrollStartRequest, db: Session = Depends(get_db)):
    if req.role not in ["student", "teacher"]:
        raise HTTPException(status_code=422, detail={"error": "INVALID_PAYLOAD", "message": "role must be student or teacher"})
    
    existing = db.query(models.Person).filter(models.Person.role == req.role, models.Person.person_id == req.person_id).first()
    if existing:
        raise HTTPException(status_code=409, detail={"error": "DUPLICATE_ID", "message": "Duplicate ID"})
    
    token = tokens.create_enrollment_token(db, req.role, req.person_id, req.name, req.subject, req.class_name)
    return {"enrollment_token": token, "expires_in": 120}

@router.post("/current-session/stop")
def stop_session(db: Session = Depends(get_db)):
    active = db.query(models.Session).filter(models.Session.status == "OPEN").first()
    if not active:
        raise HTTPException(status_code=404, detail={"error": "NO_SESSION", "message": "No active session to end"})
    
    active.status = "CLOSED"
    active.end_time = datetime.datetime.utcnow()
    active.close_reason = "MANUAL_STOP"
    db.commit()
    return {"status": "ended", "session_id": active.id}

@router.get("/current-session")
def get_current_session(db: Session = Depends(get_db)):
    active = db.query(models.Session).filter(models.Session.status == "OPEN").first()
    if not active:
        return {"active": False}
    
    attendees = db.query(models.Attendance).filter(models.Attendance.session_id == active.id).all()
    present_list = []
    for att in attendees:
        present_list.append({
            "name": att.student_name_snapshot,
            "roll_no": att.student_person_id,
            "time_recorded": format_time(att.time_recorded),
            "confidence": att.confidence
        })
    
    return {
        "active": True,
        "session_id": active.id,
        "subject": active.subject,
        "teacher": {
            "employee_id": active.teacher_person_id,
            "person_id": active.teacher_person_id,
            "name": active.teacher_name_snapshot
        },
        "start_time": format_time(active.start_time),
        "auto_close_at": format_time(active.auto_close_at),
        "present_count": len(attendees),
        "present": present_list
    }

@router.get("/sessions-history")
def sessions_history(from_: Optional[str] = None, subject: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Session).filter(models.Session.status == "CLOSED")
    if from_:
        try:
            dt = datetime.datetime.strptime(from_, "%Y-%m-%d")
            query = query.filter(models.Session.start_time >= dt)
        except ValueError:
            pass
    if subject:
        query = query.filter(models.Session.subject.ilike(f"%{subject}%"))
    sessions = query.order_by(models.Session.start_time.desc()).all()
    result = []
    for s in sessions:
        att_count = db.query(models.Attendance).filter(models.Attendance.session_id == s.id).count()
        result.append({
            "session_id": s.id,
            "subject": s.subject,
            "teacher": {"name": s.teacher_name_snapshot, "person_id": s.teacher_person_id},
            "start_time": format_time(s.start_time),
            "end_time": format_time(s.end_time),
            "total_present": att_count
        })
    return {"sessions": result}

@router.get("/sessions-history/{session_id}")
def session_details(session_id: int, db: Session = Depends(get_db)):
    s = db.query(models.Session).filter(models.Session.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Session not found"})
    attendees = db.query(models.Attendance).filter(models.Attendance.session_id == s.id).all()
    present_list = []
    for att in attendees:
        present_list.append({
            "name": att.student_name_snapshot,
            "roll_no": att.student_person_id,
            "time_recorded": format_time(att.time_recorded),
            "confidence": att.confidence
        })
    return {
        "session_id": s.id,
        "subject": s.subject,
        "teacher": {"name": s.teacher_name_snapshot, "person_id": s.teacher_person_id},
        "start_time": format_time(s.start_time),
        "end_time": format_time(s.end_time),
        "status": s.status,
        "total_present": len(attendees),
        "attendance": present_list
    }

@router.delete("/sessions-history/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db)):
    s = db.query(models.Session).filter(models.Session.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Session not found"})
    
    # Delete associated attendance records first
    db.query(models.Attendance).filter(models.Attendance.session_id == session_id).delete()
    db.delete(s)
    db.commit()
    return {"status": "deleted", "session_id": session_id}

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    meta_v = db.query(models.Meta).filter(models.Meta.key == "embeddings_version").first()
    version = int(meta_v.value) if meta_v else 0
    return {
        "ok": True, 
        "server_time": format_time(datetime.datetime.utcnow()), 
        "db": "ok", 
        "embeddings_version": version
    }

@router.get("/pi-status")
def pi_status(db: Session = Depends(get_db)):
    meta_ls = db.query(models.Meta).filter(models.Meta.key == "pi_last_seen").first()
    meta_ev = db.query(models.Meta).filter(models.Meta.key == "pi_embeddings_version").first()
    last_seen = meta_ls.value if meta_ls else None
    
    online = False
    if last_seen:
        try:
            ls_dt = datetime.datetime.fromisoformat(last_seen.replace("Z", "+00:00")).replace(tzinfo=None)
            if (datetime.datetime.utcnow() - ls_dt).total_seconds() <= 30:
                online = True
        except:
            pass

    return {
        "last_seen": last_seen,
        "online": online,
        "embeddings_version_on_pi": int(meta_ev.value) if meta_ev else 0
    }

@router.get("/people")
def get_people(role: Optional[str] = None, class_name: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Person)
    if role:
        query = query.filter(models.Person.role == role)
    if class_name:
        query = query.filter(models.Person.class_name == class_name)
    people = query.all()
    result = []
    for p in people:
        result.append({
            "role": p.role,
            "person_id": p.person_id,
            "name": p.name,
            "subject": p.subject,
            "class_name": getattr(p, 'class_name', None),
            "created_at": format_time(p.created_at)
        })
    return {"people": result}

@router.delete("/people/{role}/{person_id}")
def delete_person(role: str, person_id: str, db: Session = Depends(get_db)):
    person = db.query(models.Person).filter(models.Person.role == role, models.Person.person_id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Person not found"})
    db.delete(person)
    
    meta_v = db.query(models.Meta).filter(models.Meta.key == "embeddings_version").first()
    if not meta_v:
        meta_v = models.Meta(key="embeddings_version", value="1")
        db.add(meta_v)
    else:
        meta_v.value = str(int(meta_v.value) + 1)
        
    db.commit()
    return {"status": "deleted"}
