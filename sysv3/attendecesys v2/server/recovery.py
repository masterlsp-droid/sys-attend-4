import datetime
from sqlalchemy.orm import Session
from server.models import Session as DbSession

def recover_stale_sessions(db: Session):
    now = datetime.datetime.utcnow()
    stale = db.query(DbSession).filter(DbSession.status == "OPEN", DbSession.auto_close_at < now).all()
    for s in stale:
        s.status = "CLOSED"
        s.close_reason = "RECOVERED"
        s.end_time = s.auto_close_at
    if stale:
        db.commit()
    return len(stale)
