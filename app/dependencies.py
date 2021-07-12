from app.models import SkillModel
import os
from typing import Dict, Optional, Tuple, Union
from app.database import DB
from .config import settings
from argon2 import PasswordHasher
import docker
import secrets
from functools import lru_cache

ph = PasswordHasher()
db = DB(os.path.join(settings.store_directory, "store.json"))


def get_db():
    yield db


def get_skills_dir():
    skills_dir = os.path.join(settings.store_directory, "skills")
    if not os.path.isdir(skills_dir):
        os.makedirs(skills_dir)
    return skills_dir


def get_docker():
    return docker.from_env()

@lru_cache()
def get_temp_directory():
    if os.path.isdir("/tmp"):
        return "/tmp"
    temp_dir = os.path.join(settings.store_directory, "temp")
    print(os.listdir())
    if not os.path.isdir(temp_dir):
        print("creating temp folder...")
        os.makedirs(temp_dir)
    return temp_dir


def create_skill(db: DB, slug: str, topic_access: Union[None, Dict[str, int]]) -> str:
    """create a skill and then insert in the database

    Args:
        db (DB): the database instances
        slug (str): the skill name
        topic_access (Union[None, Dict[str, str]]): topics that the skills can access

    Returns:
        str: plain password
    """
    password = secrets.token_hex(32)
    hash_password = ph.hash(password)
    success = db.insert_skill(
        SkillModel(
            skill_name=slug,
            hashed_password=hash_password,
            topic_access=topic_access,
        )
    )
    return password
