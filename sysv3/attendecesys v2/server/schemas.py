from pydantic import BaseModel
from typing import Optional, List

class EnrollStartRequest(BaseModel):
    role: str
    name: str
    person_id: str
    subject: Optional[str] = None
    
class EnrollCompleteRequest(BaseModel):
    enrollment_token: str
    embedding: List[float]
    model_id: str
    
class SessionCreateRequest(BaseModel):
    client_uuid: str
    teacher_person_id: str
    subject: str
    start_time: str
    auto_close_at: str

class SessionPatchRequest(BaseModel):
    status: str
    end_time: str
    close_reason: str

class AttendanceRequest(BaseModel):
    event_uuid: str
    session_client_uuid: str
    student_person_id: str
    time_recorded: str
    confidence: float
