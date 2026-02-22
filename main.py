from fastapi import FastAPI
from database import engine
from models import Base
from datetime import date
from database import SessionLocal
from models import User
from models import Event
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

Base.metadata.create_all(bind=engine)

def seed_users():
    db = SessionLocal()

    existing_user = db.query(User).filter(User.name == "Dad").first()

    if existing_user is None:
        users = [
            User(name="Dad", role="adult"),
            User(name="Mom", role="adult"),
            User(name="Nathaniel", role="child")
        ]
        db.add_all(users)
        db.commit()

    db.close()

def seed_events():
    db = SessionLocal()

    existing_event = db.query(Event).filter(Event.title == "Physical Therapy").first()

    if existing_event is None:
        events = [
            Event(
                title="Physical Therapy",
                type="appointment",
                owner_id=1,  # Dad
                start_date=date(2025, 8, 7),
                end_date=date(2025, 8, 7),
                all_day=False
            ),
            Event(
                title="Trip to Amanda’s",
                type="trip",
                owner_id=1,  # Dad
                start_date=date(2025, 8, 14),
                end_date=date(2025, 8, 17),
                all_day=True
            )
        ]

        db.add_all(events)
        db.commit()

    db.close()

seed_users()
seed_events()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()

family_members = [
    {"id": 1, "name": "Dad", "role": "adult"},
    {"id": 2, "name": "Mom", "role": "adult"},
    {"id": 3, "name": "Nathaniel", "role": "child"}
]

events = [
    {
        "id": 1,
        "title": "Physical Therapy",
        "type": "appointment",
        "owner_id": 1, # Dad
        "start_date": "2025-08-07",
        "end_date": "2025-08-07",
        "all_day": False
    },
    {
        "id": 2,
        "title": "Trip to Amanda's",
        "type": "trip",
        "owner_id": 1, # Dad
        "start_date": "2025-08-14",
        "end_date": "2025-08-17",
        "all_day": True
    }
]

class EventCreate(BaseModel):
    title: str
    type: str
    owner_id: int
    start_date: date
    end_date: date
    all_day: bool = False

class EventUpdate(BaseModel):
    title: str
    type: str
    owner_id: int
    start_date: date
    end_date: date
    all_day: bool

@app.get("/")
def home():
    return {"message": "Family Hub is running"}

@app.get("/users")
def get_users():
    db = SessionLocal()
    users = db.query(User).all()
    db.close()
    return users

@app.get("/events")
def get_events(month: str | None = None, user_id: int | None = None):
    db = SessionLocal()
    query = db.query(Event)

    if month is not None:
        year, month_num = month.split("-")
        query = query.filter(
            Event.start_date >= date(int(year), int(month_num), 1),
            Event.start_date < date(int(year), int(month_num) + 1, 1)
        )

    if user_id is not None:
        query = query.filter(Event.owner_id == user_id)

    events = query.all()
    db.close()
    return events

@app.post("/events")
def create_event(event: EventCreate):
    db = SessionLocal()

    new_event = Event(
        title=event.title,
        type=event.type,
        owner_id=event.owner_id,
        start_date=event.start_date,
        end_date=event.end_date,
        all_day=event.all_day
    )

    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    db.close()

    return new_event

@app.put("/events/{event_id}")
def update_event(event_id: int, updated: EventUpdate):
    db = SessionLocal()

    event = db.query(Event).filter(Event.id == event_id).first()

    if event is None:
        db.close()
        return {"error": "Event not found"}

    event.title = updated.title
    event.type = updated.type
    event.owner_id = updated.owner_id
    event.start_date = updated.start_date
    event.end_date = updated.end_date
    event.all_day = updated.all_day

    db.commit()
    db.refresh(event)
    db.close()

    return event

@app.delete("/events/{event_id}")
def delete_event(event_id: int):
    db = SessionLocal()

    event = db.query(Event).filter(Event.id == event_id).first()

    if event is None:
        db.close()
        return {"error": "Event not found"}

    db.delete(event)
    db.commit()
    db.close()

    return {"message": "Event deleted"}




