from app.database import SessionLocal
from app.models import Resource

db = SessionLocal()

resources = [
    # LABS
    {"name": "Chemistry Lab A1", "type": "lab"},
    {"name": "Physics Lab B2", "type": "lab"},
    {"name": "Computer Lab C3", "type": "lab"},
    {"name": "Electronics Lab D4", "type": "lab"},
    {"name": "Biology Lab E5", "type": "lab"},
    {"name": "AI Lab F6", "type": "lab"},
    {"name": "Robotics Lab G7", "type": "lab"},
    {"name": "Networking Lab H8", "type": "lab"},
    {"name": "Data Science Lab I9", "type": "lab"},
    {"name": "Software Engineering Lab J10", "type": "lab"},
    {"name": "Operating Systems Lab K11", "type": "lab"},
    {"name": "Cybersecurity Lab L12", "type": "lab"},

    # HALLS
    {"name": "Seminar Hall 101", "type": "hall"},
    {"name": "Seminar Hall 102", "type": "hall"},
    {"name": "Lecture Hall A", "type": "hall"},
    {"name": "Lecture Hall B", "type": "hall"},
    {"name": "Conference Room 1", "type": "hall"},
    {"name": "Conference Room 2", "type": "hall"},

    # SPORTS
    {"name": "Main Gym", "type": "sport"},
    {"name": "Basketball Court", "type": "sport"},
    {"name": "Football Field", "type": "sport"},
    {"name": "Volleyball Court", "type": "sport"},
    {"name": "Swimming Pool", "type": "sport"},
    {"name": "Fitness Room", "type": "sport"},
    {"name": "Table Tennis Room", "type": "sport"},
    {"name": "Badminton Court", "type": "sport"},
    {"name": "Martial Arts Hall", "type": "sport"},
]

# avoid duplicates
existing = {(r.name, r.type) for r in db.query(Resource).all()}

added = 0
for r in resources:
    if (r["name"], r["type"]) not in existing:
        db.add(Resource(**r))
        added += 1

db.commit()
db.close()

print(f"Seed completed. Added {added} resources.")
