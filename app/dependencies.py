from docker.client import DockerClient
from docker.models.containers import Container
from fastapi.param_functions import Depends
from app.models import SkillModel
import os
from . import config
from typing import Dict, List, Union
from app.database import DB
from argon2 import PasswordHasher
import docker
import secrets
from functools import lru_cache

ph = PasswordHasher()


@lru_cache()
def get_settings():
    return config.Settings()


def get_db(settings: config.Settings = Depends(get_settings)) -> DB:
    yield DB(os.path.join(settings.store_directory, "store.json"))


def get_skills_dir(settings: config.Settings = Depends(get_settings)):
    skills_dir = os.path.join(settings.store_directory, "skills")
    if not os.path.isdir(skills_dir):
        os.makedirs(skills_dir)
    return skills_dir


def get_docker() -> DockerClient:
    return docker.from_env()


def get_container_by_skill_name(
    docker: DockerClient, skill_name: str
) -> Union[Container, None]:
    containers: List[Container] = docker.containers.list(
        all=True, filters={"label": f"skill_name={skill_name}"}
    )
    if len(containers) != 0:
        return containers[0]
    return None


@lru_cache()
def get_temp_directory(settings: config.Settings = Depends(get_settings)) -> str:
    if os.path.isdir("/tmp"):
        return "/tmp"
    temp_dir = os.path.join(settings.store_directory, "temp")
    print(os.listdir())
    if not os.path.isdir(temp_dir):
        print("creating temp folder...")
        os.makedirs(temp_dir)
    return temp_dir


def create_skill(
    db: DB, slug: str, topic_access: Union[None, Dict[str, int]], start_on_boot: bool
) -> str:
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
    db.insert_skill(
        SkillModel(
            skill_name=slug,
            hashed_password=hash_password,
            topic_access=topic_access,
            start_on_boot=start_on_boot,
        )
    )
    return password
