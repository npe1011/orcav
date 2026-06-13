from typing import List
from pathlib import Path

class ORCAJob:
    JOB_TYPE: str = 'base'
    def __init__(self, parent_file: Path, name: str = 'base'):
        self.name = name
        self.sub_jobs: List[ORCAJob] = []
        p = parent_file.absolute()
        self.parent_dir = p.parent
        self.file_stem = p.stem

    def get_type(self) -> str:
        return self.JOB_TYPE
