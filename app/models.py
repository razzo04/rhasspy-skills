from typing import Dict, List, Optional
from enum import IntEnum
from pydantic.main import BaseModel


class TopicAccess(IntEnum):
    READ = 1
    WRITE = 2
    READWRITE = 3
    SUBSCRIBE = 4
    DENY = 5


class SkillModel(BaseModel):
    skill_name: str
    hashed_password: str
    start_on_boot: bool = False
    topic_access: Optional[Dict[str, TopicAccess]] = {}

    class Config:
        use_enum_values = True


class DBFile(BaseModel):
    skills: List[SkillModel]
