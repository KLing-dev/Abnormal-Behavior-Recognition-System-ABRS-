from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from models.base import get_db
from models.absent import Person, AlarmAbsent


router = APIRouter(prefix="/absent", tags=["absent"])


class PersonInfo(BaseModel):
    person_id: str
    name: str
    post: str
    duty_period: str
    max_absent_min: int = 5
    face_img: Optional[str] = None


class PersonUpdateInfo(BaseModel):
    person_id: str
    name: Optional[str] = None
    post: Optional[str] = None
    duty_period: Optional[str] = None
    max_absent_min: Optional[int] = None
    face_feature: Optional[str] = None


@router.post("/person/add")
async def add_person(person: PersonInfo, db: Session = Depends(get_db)):
    db_person = Person(
        person_id=person.person_id,
        name=person.name,
        post=person.post,
        duty_period=person.duty_period,
        max_absent_min=person.max_absent_min,
        face_feature=person.face_img
    )
    db.add(db_person)
    db.commit()
    db.refresh(db_person)
    return {"message": "人员添加成功", "person_id": person.person_id}


@router.post("/person/update")
async def update_person(info: PersonUpdateInfo, db: Session = Depends(get_db)):
    db_person = db.query(Person).filter(Person.person_id == info.person_id).first()
    if not db_person:
        return {"error": "人员不存在", "person_id": info.person_id}
    
    if info.name:
        db_person.name = info.name
    if info.post:
        db_person.post = info.post
    if info.duty_period:
        db_person.duty_period = info.duty_period
    if info.max_absent_min is not None:
        db_person.max_absent_min = info.max_absent_min
    if info.face_feature:
        db_person.face_feature = info.face_feature
    
    db.commit()
    return {"message": "人员更新成功", "person_id": info.person_id}


@router.post("/person/delete")
async def delete_person(person_id: str, db: Session = Depends(get_db)):
    db_person = db.query(Person).filter(Person.person_id == person_id).first()
    if not db_person:
        return {"error": "人员不存在", "person_id": person_id}
    
    db.delete(db_person)
    db.commit()
    return {"message": "人员删除成功", "person_id": person_id}


@router.get("/person/query")
async def query_persons(person_id: Optional[str] = None, db: Session = Depends(get_db)):
    if person_id:
        persons = db.query(Person).filter(Person.person_id == person_id).all()
    else:
        persons = db.query(Person).all()
    
    result = []
    for p in persons:
        result.append({
            "person_id": p.person_id,
            "name": p.name,
            "post": p.post,
            "duty_period": p.duty_period,
            "max_absent_min": p.max_absent_min,
            "create_time": p.create_time.isoformat() if p.create_time else None
        })
    return {"persons": result}


@router.post("/source/switch")
async def switch_source(source_type: str, source_id: str, device_id: Optional[int] = None):
    return {"message": "source switched", "source_type": source_type, "source_id": source_id}


@router.post("/start")
async def start_detection(source_id: str):
    return {"message": "absent detection started", "source_id": source_id}


@router.post("/stop")
async def stop_detection():
    return {"message": "absent detection stopped"}


@router.get("/alarm/list")
async def get_alarms(
    person_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(AlarmAbsent)
    
    if person_id:
        query = query.filter(AlarmAbsent.content.contains(f'"person_id": "{person_id}"'))
    if start_time:
        query = query.filter(AlarmAbsent.alarm_time >= start_time)
    if end_time:
        query = query.filter(AlarmAbsent.alarm_time <= end_time)
    
    alarms = query.order_by(AlarmAbsent.alarm_time.desc()).all()
    
    result = []
    for a in alarms:
        result.append({
            "alarm_time": a.alarm_time.isoformat() if a.alarm_time else None,
            "event_id": a.event_id,
            "alarm_type": a.alarm_type,
            "content": a.content,
            "source_type": a.source_type,
            "source_id": a.source_id,
            "status": a.status
        })
    return {"alarms": result}
