from typing import Union


class SkillInstallException(Exception):
    def __init__(
        self,
        status_code: int,
        error_code: Union[str, int],
        detail: str,
        clean: bool = False,
    ):
        self.status_code = status_code
        self.error_code = error_code
        self.detail = detail
