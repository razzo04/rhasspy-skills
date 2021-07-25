from app.models import DBFile, SkillModel
from typing import List, Union
import os


class DB:
    def __init__(self, path: str, use_cache=False) -> None:
        self.path = path
        self.use_cache = use_cache
        if not os.path.isfile(path):
            print("Genereting db...")
            par_dir = os.path.dirname(path)
            if not os.path.exists(par_dir):
                os.makedirs(par_dir, exist_ok=True)
            with open(path, "w") as f:
                f.write(DBFile(skills=[]).json())

    def insert_skill(self, skill: SkillModel, over_write=True) -> bool:
        data = self.read_file()
        for skill_json in data.skills:
            if skill_json.skill_name == skill.skill_name:
                if not over_write:
                    return False
                else:
                    data.skills.remove(skill_json)
        data.skills.append(skill)
        self.write_file(data)
        return True

    def read_file(self) -> DBFile:
        return DBFile.parse_file(self.path)

    def write_file(self, data: DBFile):
        with open(self.path, "w") as f:
            f.write(data.json())

    def get_skills(self) -> List[SkillModel]:
        return self.read_file().skills

    def get_skill(self, skill_name: str) -> Union[SkillModel, None]:
        for skill in self.get_skills():
            if skill.skill_name == skill_name:
                return skill

    def remove_skill(self, skill_name: str) -> bool:
        skill = self.get_skill(skill_name)
        if not skill:
            return False
        data = self.read_file()
        data.skills.remove(skill)
        self.write_file(data)
        return True
