from sqlalchemy import Column, Integer, String, Float, DateTime, LargeBinary, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from server.db import Base
import datetime

class ClassGroup(Base):
    __tablename__ = "classes"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

class Person(Base):
    __tablename__ = "people"
    id = Column(Integer, primary_key=True, index=True)
    role = Column(String, nullable=False) # 'student' or 'teacher'
    person_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    subject = Column(String, nullable=True) # teachers only
    class_name = Column(String, nullable=True) # e.g. 'Division A'
    embedding = Column(LargeBinary, nullable=False)
    model_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    __table_args__ = (UniqueConstraint('role', 'person_id', name='uq_role_person_id'),)

class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    client_uuid = Column(String, unique=True, nullable=False)
    subject = Column(String, nullable=False)
    class_name = Column(String, nullable=True)
    teacher_person_id = Column(String, nullable=True)
    teacher_name_snapshot = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False)
    auto_close_at = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    status = Column(String, nullable=True) # 'OPEN' or 'CLOSED'
    close_reason = Column(String, nullable=True)

class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    student_person_id = Column(String, nullable=False)
    student_name_snapshot = Column(String, nullable=False)
    time_recorded = Column(DateTime, nullable=False)
    confidence = Column(Float, nullable=False)
    event_uuid = Column(String, unique=True, nullable=False)
    
    __table_args__ = (UniqueConstraint('session_id', 'student_person_id', name='uq_session_student'),)

class EnrollToken(Base):
    __tablename__ = "enroll_tokens"
    token = Column(String, primary_key=True, index=True)
    role = Column(String)
    person_id = Column(String)
    name = Column(String)
    subject = Column(String)
    class_name = Column(String, nullable=True)
    expires_at = Column(DateTime)
    used = Column(Integer, default=0)

class Meta(Base):
    __tablename__ = "meta"
    key = Column(String, primary_key=True)
    value = Column(String)
