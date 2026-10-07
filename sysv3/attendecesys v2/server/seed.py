import uuid
import struct
import datetime
from server.db import SessionLocal
from server.models import Person, Meta, Session, Attendance

def seed_db():
    db = SessionLocal()
    
    if db.query(Person).first():
        print("Database already seeded")
        return
        
    dummy_embedding = [0.1] * 128
    emb_bytes = struct.pack("128f", *dummy_embedding)
    
    t1 = Person(role="teacher", person_id="T01", name="Rane Mam", subject="Maths", embedding=emb_bytes, model_id="dlib_face_recognition_resnet_v1")
    t2 = Person(role="teacher", person_id="T02", name="Kale Sir", subject="Physics", embedding=emb_bytes, model_id="dlib_face_recognition_resnet_v1")
    s1 = Person(role="student", person_id="101", name="Asha Patil", embedding=emb_bytes, model_id="dlib_face_recognition_resnet_v1")
    s2 = Person(role="student", person_id="102", name="Rahul Desai", embedding=emb_bytes, model_id="dlib_face_recognition_resnet_v1")
    db.add_all([t1, t2, s1, s2])
    
    meta_v = Meta(key="embeddings_version", value="1")
    meta_m = Meta(key="model_id", value="dlib_face_recognition_resnet_v1")
    db.add_all([meta_v, meta_m])
    
    db.commit()
    
    now = datetime.datetime.utcnow()
    
    sess = Session(client_uuid=str(uuid.uuid4()), subject="Maths", teacher_person_id="T01", teacher_name_snapshot="Rane Mam",
                   start_time=now - datetime.timedelta(minutes=30), auto_close_at=now + datetime.timedelta(minutes=30), status="OPEN")
    db.add(sess)
    db.commit()
    
    att = Attendance(session_id=sess.id, student_person_id="101", student_name_snapshot="Asha Patil", time_recorded=now - datetime.timedelta(minutes=25), confidence=98.5, event_uuid=str(uuid.uuid4()))
    db.add(att)
    db.commit()
    
    print("Seeded database.")
    
if __name__ == "__main__":
    seed_db()
