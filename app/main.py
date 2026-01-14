from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date, time
from app.database import SessionLocal, engine
import app.models as models

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# -------------------- DB Dependency --------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------- ROOT --------------------
@app.get("/")
def root():
    return {"status": "ok"}

# ==================== USERS ====================

@app.post("/users/")
def create_user(
    full_name: str,
    role: models.UserRole,
    db: Session = Depends(get_db)
):
    user = models.User(full_name=full_name, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@app.get("/users/")
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()

# ==================== RESOURCES ====================

@app.post("/resources/")
def create_resource(
    name: str,
    type: str,
    db: Session = Depends(get_db)
):
    resource = models.Resource(name=name, type=type)
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource

@app.get("/resources/")
def list_resources(db: Session = Depends(get_db)):
    return db.query(models.Resource).all()

# ==================== AVAILABILITY ====================

@app.get("/resources/{resource_id}/availability")
def resource_availability(
    resource_id: int,
    booking_date: date,
    db: Session = Depends(get_db)
):
    bookings = db.query(models.Booking).filter(
        models.Booking.resource_id == resource_id,
        models.Booking.date == booking_date,
        models.Booking.status == models.BookingStatus.approved
    ).all()

    slots = []
    for hour in range(8, 20):
        start = time(hour, 0)
        end = time(hour + 1, 0)

        busy = any(
            b.time_from < end and b.time_to > start
            for b in bookings
        )

        slots.append({
            "from": start.strftime("%H:%M"),
            "to": end.strftime("%H:%M"),
            "status": "busy" if busy else "free"
        })

    return {
        "resource_id": resource_id,
        "date": booking_date,
        "slots": slots
    }

# ==================== BOOKINGS ====================

@app.post("/bookings/")
def create_booking(
    user_id: int,
    resource_id: int,
    booking_date: date,
    time_from: time,
    time_to: time,
    purpose: str,
    db: Session = Depends(get_db)
):
    user = db.query(models.User).get(user_id)
    if not user or user.role != models.UserRole.student:
        raise HTTPException(status_code=403, detail="Only students can book")

    conflict = db.query(models.Booking).filter(
        models.Booking.resource_id == resource_id,
        models.Booking.date == booking_date,
        models.Booking.time_from < time_to,
        models.Booking.time_to > time_from,
        models.Booking.status == models.BookingStatus.approved
    ).first()

    if conflict:
        raise HTTPException(status_code=400, detail="Time slot already booked")

    booking = models.Booking(
        user_id=user_id,
        resource_id=resource_id,
        date=booking_date,
        time_from=time_from,
        time_to=time_to,
        purpose=purpose,
        status=models.BookingStatus.pending
    )

    db.add(booking)
    db.commit()
    db.refresh(booking)

    return {"status": "booking request created", "booking_id": booking.id}

# ==================== STAFF ACTIONS ====================

@app.post("/bookings/{booking_id}/approve")
def approve_booking(
    booking_id: int,
    staff_id: int,
    db: Session = Depends(get_db)
):
    staff = db.query(models.User).get(staff_id)
    if not staff or staff.role != models.UserRole.staff:
        raise HTTPException(status_code=403, detail="Staff only")

    booking = db.query(models.Booking).get(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    conflict = db.query(models.Booking).filter(
        models.Booking.resource_id == booking.resource_id,
        models.Booking.date == booking.date,
        models.Booking.time_from < booking.time_to,
        models.Booking.time_to > booking.time_from,
        models.Booking.status == models.BookingStatus.approved
    ).first()

    if conflict:
        raise HTTPException(status_code=400, detail="Conflict detected")

    booking.status = models.BookingStatus.approved
    db.commit()

    return {"status": "booking confirmed"}

@app.post("/bookings/{booking_id}/reject")
def reject_booking(
    booking_id: int,
    staff_id: int,
    db: Session = Depends(get_db)
):
    staff = db.query(models.User).get(staff_id)
    if not staff or staff.role != models.UserRole.staff:
        raise HTTPException(status_code=403, detail="Staff only")

    booking = db.query(models.Booking).get(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    booking.status = models.BookingStatus.rejected
    db.commit()

    return {"status": "booking rejected"}

# ==================== HISTORY ====================

@app.get("/users/{user_id}/bookings/history")
def booking_history(
    user_id: int,
    db: Session = Depends(get_db)
):
    return db.query(models.Booking).filter(
        models.Booking.user_id == user_id
    ).all()
