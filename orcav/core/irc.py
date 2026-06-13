from pathlib import Path
from typing import List, Optional, Literal
from decimal import Decimal

from orcav.core.base import ORCAJob
from orcav.core.structure import Structure
from orcav.core.utils import check_file

"""
ORCA IRC block should start with
Intrinsic Reaction Coordinate Calculation

and end with
IRC PATH SUMMARY 

(Final path summary is not parsed)
"""

class ORCAIRC(ORCAJob):
    JOB_TYPE = 'irc'
    def __init__(self,  irc_block: List[str], init_structure: Structure, init_energy: Decimal, parent_file: Path, name: str = 'irc'):
        super().__init__(parent_file=parent_file, name=name)
        self.init_structure: Structure = init_structure
        self.init_energy: Decimal = init_energy
        self.irc_type: Literal['both', 'forward', 'backward', 'down'] = 'both'
        self.path1_energies: List[Decimal] = []       # forward / down
        self.path2_energies: List[Decimal] = []       # backward
        self.path1_trajectory_file: Optional[Path] = None
        self.path2_trajectory_file: Optional[Path] = None
        self.full_path_trajectory_file: Optional[Path] = None
        self.path1_status: Literal['converged', 'stopped', 'continue', 'none'] = 'none'
        self.path2_status: Literal['converged', 'stopped', 'continue', 'none'] = 'none'

        # Check IRC type and parse remaining logs
        for line in irc_block:
            if line.strip().startswith('Direction') and '....' in line:
                k = line.strip().split('....')[1].strip()
                if k == 'Forward and backward':
                    self.irc_type = 'both'
                    self._extract_both(irc_block)
                elif k == 'Forward-only':
                    self.irc_type = 'forward'
                    self._extract_forward(irc_block)
                elif k == 'Backward-only':
                    self.irc_type = 'backward'
                    self._extract_backward(irc_block)
                elif k == 'Downhill':
                    self.irc_type = 'down'
                    self._extract_down(irc_block)
                else:
                    raise RuntimeError(f'Error: unexpected IRC type: {k}')
                break
                
        self.structure_list: List[Structure] = []
        self.energy_list: List[Decimal] = []
        
        # Load structures and energies from XYZ if available
        if self.irc_type == 'both' and self.full_path_trajectory_file:
            self.structure_list, self.energy_list = Structure.read_xyz_by_orca(self.full_path_trajectory_file)
        elif self.irc_type in ['forward', 'down'] and self.path1_trajectory_file:
            self.structure_list, self.energy_list = Structure.read_xyz_by_orca(self.path1_trajectory_file)
        elif self.irc_type == 'backward' and self.path2_trajectory_file:
            self.structure_list, self.energy_list = Structure.read_xyz_by_orca(self.path2_trajectory_file)
        elif self.irc_type == 'both' and self.path1_trajectory_file and self.path2_trajectory_file:
            # Fallback to stitch if Full trj is missing
            s1, e1 = Structure.read_xyz_by_orca(self.path1_trajectory_file)
            s2, e2 = Structure.read_xyz_by_orca(self.path2_trajectory_file)
            # Path2 is usually TS -> Reactant, so reverse it
            # Path1 is TS -> Product
            # Skip the first element of path1 if it is the same TS
            self.structure_list = list(reversed(s2)) + s1[1:]
            self.energy_list = list(reversed(e2)) + e1[1:]

    def _extract_both(self, irc_block: List[str]):
        full_path_trajectory_file_candidates = [self.parent_dir / (self.file_stem + '_IRC_Full_trj.xyz')]
        for i, line in enumerate(irc_block):
            if 'Storing full IRC trajectory in' in line and '....' in line:
                full_path_trajectory_file_candidates.append(self.parent_dir / line.strip().split()[-1])
                break
        self.full_path_trajectory_file = check_file(full_path_trajectory_file_candidates, warnings=True)
        self._extract_forward(irc_block)
        self._extract_backward(irc_block)

    def _extract_forward(self, irc_block: List[str]):
        path_trajectory_file_candidates = [self.parent_dir / (self.file_stem + '_IRC_F_trj.xyz')]
        start_line = -1
        for i, line in enumerate(irc_block):
            if 'Storing forward trajectory in' in line and '....' in line:
                path_trajectory_file_candidates.append(self.parent_dir / line.strip().split()[-1])
            elif line.strip().startswith('*') and 'FORWARD IRC' in line:
                start_line = i + 5
                self.path1_status = 'continue'
            elif 'MAXIMUM NUMBER OF ITERATIONS REACHED - STOPPING IRC RUN' in line and self.path1_status == 'continue':
                self.path1_status = 'stopped'
            elif line.strip().startswith('*') and 'THE IRC HAS CONVERGED' in line and self.path1_status == 'continue':
                self.path1_status = 'converged'
            elif line.strip().startswith('*') and 'BACKWARD IRC' in line:
                break
        self.path1_trajectory_file = check_file(path_trajectory_file_candidates, warnings=True)

        if start_line < 0:
            return

        # Extract energies
        for i, line in enumerate(irc_block[start_line:]):
            if line.strip() == '':
                break
            terms = line.strip().split()
            assert int(terms[0]) == i
            self.path1_energies.append(Decimal(terms[1]))

    def _extract_backward(self, irc_block: List[str]):
        path_trajectory_file_candidates = [self.parent_dir / (self.file_stem + '_IRC_B_trj.xyz')]
        start_line = -1
        for i, line in enumerate(irc_block):
            if 'Storing backward trajectory in' in line and '....' in line:
                path_trajectory_file_candidates.append(self.parent_dir / line.strip().split()[-1])
            elif line.strip().startswith('*') and 'BACKWARD IRC' in line:
                start_line = i + 5
                self.path2_status = 'continue'
            elif 'MAXIMUM NUMBER OF ITERATIONS REACHED - STOPPING IRC RUN' in line and self.path2_status == 'continue':
                self.path2_status = 'stopped'
            elif line.strip().startswith('*') and 'THE IRC HAS CONVERGED' in line and self.path2_status == 'continue':
                self.path2_status = 'converged'
        self.path2_trajectory_file = check_file(path_trajectory_file_candidates, warnings=True)

        if start_line < 0:
            return

        # Extract energies
        for i, line in enumerate(irc_block[start_line:]):
            if line.strip() == '':
                break
            terms = line.strip().split()
            assert int(terms[0]) == i
            self.path2_energies.append(Decimal(terms[1]))

    def _extract_down(self, irc_block: List[str]):
        path_trajectory_file_candidates = [self.parent_dir / (self.file_stem + '_IRC_D_trj.xyz')]
        start_line = -1
        for i, line in enumerate(irc_block):
            if 'Storing downhill trajectory in' in line and '....' in line:
                path_trajectory_file_candidates.append(self.parent_dir / line.strip().split()[-1])
            elif line.strip().startswith('*') and 'DOWNHILL IRC' in line:
                start_line = i + 5
                self.path1_status = 'continue'
            elif 'MAXIMUM NUMBER OF ITERATIONS REACHED - STOPPING IRC RUN' in line and self.path1_status == 'continue':
                self.path1_status = 'stopped'
            elif line.strip().startswith('*') and 'THE IRC HAS CONVERGED' in line and self.path1_status == 'continue':
                self.path1_status = 'converged'
        self.path1_trajectory_file = check_file(path_trajectory_file_candidates, warnings=True)

        if start_line < 0:
            return

        # Extract energies
        for i, line in enumerate(irc_block[start_line:]):
            if line.strip() == '':
                break
            terms = line.strip().split()
            assert int(terms[0]) == i
            self.path1_energies.append(Decimal(terms[1]))
