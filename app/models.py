from sqlalchemy import Column, Integer, ForeignKey, Date, Time, String, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base
import enum

# USER AND ROLES
class UserRole(str, enum.Enum):
    student = "student"
    staff = "staff"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    pnumber = Column(String, unique=True, index=True, nullable=False)  # P1234567
    full_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)

# Resources
class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)

# Booking

class BookingStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)

    resource_id = Column(Integer, ForeignKey("resources.id"))
    user_id = Column(Integer, ForeignKey("users.id"))

    date = Column(Date, nullable=False)
    time_from = Column(Time, nullable=False)
    time_to = Column(Time, nullable=False)

    purpose = Column(String, nullable=False)
    status = Column(Enum(BookingStatus), default=BookingStatus.pending)

    resource = relationship("Resource")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint(
            "resource_id", "date", "time_from", "time_to",
            name="unique_resource_time_slot"
        ),
    )



