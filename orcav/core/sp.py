from typing import List, Optional
from decimal import  Decimal
from pathlib import Path

from orcav.core.base import ORCAJob
from orcav.core.structure import Structure


class ORCASPJob(ORCAJob):
    JOB_TYPE = 'sp'

    def __init__(self, sp_block: List[str], parent_file: Path, name='sp'):
        super().__init__(parent_file=parent_file, name=name)
        self.structure: Optional[Structure] = None
        self.energy: Decimal = Decimal(0)

        for i, line in enumerate(sp_block):
            if line.strip().startswith('CARTESIAN COORDINATES (ANGSTROEM)') and self.structure is None:
                self.structure = Structure.read_structure(sp_block, i+2)
                continue
            if line.strip().startswith('FINAL SINGLE POINT ENERGY'):
                self.energy = Decimal(line.strip().split()[-1])
                break
