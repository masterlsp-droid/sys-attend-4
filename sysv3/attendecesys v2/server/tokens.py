import uuid
import datetime
from sqlalchemy.orm import Session
from server import models

def create_enrollment_token(db: Session, role: str, person_id: str, name: str, subject: str = None, class_name: str = None) -> str:
    token = str(uuid.uuid4())
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=2)
    db_token = models.EnrollToken(token=token, role=role, person_id=person_id, name=name, subject=subject, class_name=class_name, expires_at=expires_at)
    db.add(db_token)
    db.commit()
    return token
