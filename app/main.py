from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date, time
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError

from datetime import date as DateType
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from fastapi.middleware.cors import CORSMiddleware
from app.database import SessionLocal, engine
import app.models as models
from app.security import hash_password, verify_password, create_access_token, SECRET_KEY, ALGORITHM

# -------------------- FastAPI App --------------------
app = FastAPI()
models.Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- OAuth2 --------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# -------------------- DB Dependency --------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------- Authentication Helpers --------------------
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        pnumber = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(models.User).filter_by(pnumber=pnumber).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def student_only(user: models.User = Depends(get_current_user)):
    if user.role != models.UserRole.student:
        raise HTTPException(status_code=403, detail="Students only")
    return user

def staff_only(user: models.User = Depends(get_current_user)):
    if user.role != models.UserRole.staff:
        raise HTTPException(status_code=403, detail="Staff only")
    return user

# -------------------- ROOT --------------------
@app.get("/")
def root():
    return {"status": "ok"}

# ==================== AUTH ====================
@app.post("/auth/register")
def register(pnumber: str, full_name: str, password: str, role: models.UserRole, db: Session = Depends(get_db)):
    if db.query(models.User).filter_by(pnumber=pnumber).first():
        raise HTTPException(status_code=400, detail="P-number already exists")
    user = models.User(
        pnumber=pnumber,
        full_name=full_name,
        password_hash=hash_password(password),
        role=role
    )
    db.add(user)
    db.commit()
    return {"status": "user registered"}

@app.post("/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(pnumber=form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.pnumber, "role": user.role.value})
    return {"access_token": token, "token_type": "bearer"}

# ==================== USERS ====================
@app.get("/users/")
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()

# ==================== RESOURCES ====================
@app.post("/resources/")
def create_resource(name: str, type: str, staff: models.User = Depends(staff_only), db: Session = Depends(get_db)):
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
def resource_availability(resource_id: int, booking_date: date, db: Session = Depends(get_db)):
    bookings = db.query(models.Booking).filter(
        models.Booking.resource_id == resource_id,
        models.Booking.date == booking_date,
        models.Booking.status == models.BookingStatus.approved
    ).all()
    slots = []
    for hour in range(8, 20):
        start = time(hour, 0)
        end = time(hour + 1, 0)
        busy = any(b.time_from < end and b.time_to > start for b in bookings)
        slots.append({"from": start.strftime("%H:%M"), "to": end.strftime("%H:%M"), "status": "busy" if busy else "free"})
    return {"resource_id": resource_id, "date": booking_date, "slots": slots}

from sqlalchemy import func

@app.get("/dashboard/summary")
def dashboard_summary(day: date, db: Session = Depends(get_db)):
    # resources by type
    resources = db.query(models.Resource).all()

    def count_type(t: str) -> int:
        return sum(1 for r in resources if r.type == t)

    labs = count_type("lab")
    halls = count_type("hall")
    sports = count_type("sport")

    # approved bookings for that date
    approved = db.query(models.Booking).filter(
        models.Booking.date == day,
        models.Booking.status == models.BookingStatus.approved
    ).all()

    # For “today free/booked spaces”:
    # booked spaces = number of DISTINCT resources that have at least one approved booking that day
    booked_resource_ids = {b.resource_id for b in approved}
    booked_spaces = len(booked_resource_ids)

    total_spaces = len(resources)
    free_spaces = max(total_spaces - booked_spaces, 0)

    # breakdown booked by resource.type
    type_by_id = {r.id: r.type for r in resources}
    booked_labs = sum(1 for rid in booked_resource_ids if type_by_id.get(rid) == "lab")
    booked_halls = sum(1 for rid in booked_resource_ids if type_by_id.get(rid) == "hall")
    booked_sports = sum(1 for rid in booked_resource_ids if type_by_id.get(rid) == "sport")

    free_labs = labs - booked_labs
    free_halls = halls - booked_halls
    free_sports = sports - booked_sports

    return {
        "date": str(day),
        "totals": {
            "resources_total": total_spaces,
            "available_today": free_spaces,
            "booked_today": booked_spaces,
        },
        "by_type": {
            "lab": {"resources": labs, "free": free_labs, "booked": booked_labs},
            "hall": {"resources": halls, "free": free_halls, "booked": booked_halls},
            "sport": {"resources": sports, "free": free_sports, "booked": booked_sports},
        },
    }



# ==================== BOOKINGS ====================
@app.post("/bookings/")
def create_booking(
    resource_id: int,
    booking_date: date,
    time_from: time,
    time_to: time,
    purpose: str,
    student: models.User = Depends(student_only),
    db: Session = Depends(get_db)
):
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
        user_id=student.id,
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
def approve_booking(booking_id: int, staff: models.User = Depends(staff_only), db: Session = Depends(get_db)):
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
def reject_booking(booking_id: int, staff: models.User = Depends(staff_only), db: Session = Depends(get_db)):
    booking = db.query(models.Booking).get(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking.status = models.BookingStatus.rejected
    db.commit()
    return {"status": "booking rejected"}

# ==================== HISTORY ====================
@app.get("/users/{user_id}/bookings/history")
def booking_history(user_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Students can see only their own history
    if current_user.role == models.UserRole.student and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")
    return db.query(models.Booking).filter(models.Booking.user_id == user_id).all()

@app.get("/users/me")
def get_me(user: models.User = Depends(get_current_user)):
    return {
        "id": user.id,
        "pnumber": user.pnumber,
        "full_name": user.full_name,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
    }

@app.get("/me/bookings")
def my_bookings(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # return ALL bookings of current user (history + current)
    bookings = (
        db.query(models.Booking)
        .filter(models.Booking.user_id == user.id)
        .order_by(models.Booking.date.desc(), models.Booking.time_from.desc())
        .all()
    )

    return [
        {
            "id": b.id,
            "resource": {
                "id": b.resource.id if b.resource else b.resource_id,
                "name": b.resource.name if b.resource else None,
                "type": b.resource.type if b.resource else None,
            },
            "date": str(b.date),
            "time_from": b.time_from.strftime("%H:%M"),
            "time_to": b.time_to.strftime("%H:%M"),
            "purpose": b.purpose,
            "status": b.status.value if hasattr(b.status, "value") else str(b.status),
        }
        for b in bookings
    ]

@app.post("/me/bookings/{booking_id}/cancel")
def cancel_my_booking(
    booking_id: int,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    b = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")

    if b.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your booking")

    # only pending can be cancelled in this simple model
    if b.status != models.BookingStatus.pending:
        raise HTTPException(status_code=400, detail="Only pending bookings can be cancelled")

    # you don't have "cancelled" status -> delete record
    db.delete(b)
    db.commit()
    return {"status": "cancelled"}