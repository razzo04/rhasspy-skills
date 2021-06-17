
#https://fastapi.tiangolo.com/tutorial/bigger-applications/#an-example-file-structure
from fastapi import APIRouter, Depends, HTTPException, Response, Form, status
from ..dependencies import get_db, ph
from app.database import DB
import re
mqtt_router = APIRouter(
    tags=["mqtt"],
    responses={404: {"detail": "Skill not found"}, 403: {"detail": "topic forbidden"}, 401: {"detail": "Incorrect password"}},
)

@mqtt_router.post("/login")
def login_mqtt(
    username: str = Form(None),
    password: str = Form(""),
    db: DB = Depends(get_db),
):
    #TODO improve security
    skill = db.get_skill(username)
    if skill == None:
        raise HTTPException(status_code=404, detail="Skill not found")
    else:
        try:
            ph.verify(skill.hashed_password, password=password)
        except:
            raise HTTPException(status_code=401, detail="Incorrect password")

@mqtt_router.post("/acl")
def acl_mqtt(
    response: Response,
    username: str = Form(None),
    topic: str = Form(""),
    acc: str = Form(""),
    db: DB = Depends(get_db),
):
    print(f" username: {username} topic {topic}, acc: {acc}")
    skill = db.get_skill(username)
    if skill == None:
        raise HTTPException(status_code=404, detail="Skill not found")
    match_intent_old = re.match(r"^hermes/intent/([^/]+)", topic)
    if match_intent_old is not None:
        #READ or SUBSCRIBE
        if int(acc) == 1 or int(acc) == 4:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
    match_intent = re.match(f"^hermes/intent/{username}/([^/]+)", topic)
    if match_intent is not None:
        #READ or SUBSCRIBE
        if int(acc) == 1 or int(acc) == 4:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
    match_dialogue = re.match(r"hermes/dialogueManager/([^/]+)", topic)
    if match_dialogue is not None:
        #WRITE
        if int(acc) == 2:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
    if skill.topic_access is None:
        raise HTTPException(status_code=403, detail="topic forbidden")
    #TODO change with regex 
    if topic in skill.topic_access:
        if skill.topic_access[topic] != int(acc):
            raise HTTPException(status_code=403, detail="topic forbidden")
    else:
        raise HTTPException(status_code=403, detail="topic forbidden")
    response.status_code = status.HTTP_204_NO_CONTENT


@mqtt_router.post("/superuser")
def super_user_mqtt(response: Response, username: str = Form("")):
    print(f"SuperUser: {username}")
    raise HTTPException(status_code=403, detail="Superuser not allowed")

