from typing import List, Tuple, Literal
from decimal import  Decimal
from pathlib import Path

from orcav.core.base import ORCAJob
from orcav.core.opt import ORCAOpt
from orcav.core.structure import Structure

"""
ORCA scan block should start with
*    Relaxed Surface Scan    *

and end with
**** RELAXED SURFACE SCAN DONE ***
or
The optimization did not converge but reached the maximum number
"""

"""
Internally, atom indices are 0-based.
"""

"""
In each scan point, the data are parsed only when 
*** OPTIMIZATION RUN DONE ***
found.
"""

class ORCAScan(ORCAJob):
    JOB_TYPE = 'scan'
    def __init__(self, scan_block: List[str], parent_file: Path, name: str = 'scan'):
        super().__init__(parent_file=parent_file, name=name)
        self.dim: int = 0
        self.shape: List[int] = []  # [m,n] for m x n point scan, [m] for m point scan.
        # Following 3 should be in the same length. The same index elements indicate one scan parameter.
        self.scan_atom_indices_list: List[List[int]] = []  # 0-based atom indices
        self.scan_type_list: List[Literal['bond', 'angle', 'dihedral']] = []
        self.scan_range_list: List[Tuple[Decimal, Decimal]] = []   # (start, end)
        # Following 3 should be in the same length (scan step). The same index elements indicate one scan point.
        self.structure_list: List[Structure] = []
        self.energy_list: List[Decimal] = []
        self.parameters_list: List[List[Decimal]] = []
        # For getting atom type from index
        self.atoms: List[str] = []

        # Read initial block for scan types and steps.
        assert 'Relaxed Surface Scan' in scan_block[0]  # To avoid wrong parsing
        for i, line in enumerate(scan_block):
            if i <= 2:
                continue
            if line.strip() == '':
                break
            """
            Read following format...
            Dihedral (  8,   7,   4,   0):   range=  60.00000000 ..  90.00000000  steps =    5
            Bond (  7,   4):   range=   1.54000000 ..   1.70000000  steps =    5
            Angle (  0,   4,   7):   range= 109.50000000 .. 125.00000000  steps =    5
            """

            terms = line.strip().split()
            scan_type = terms[0].lower()
            scan_step = int(terms[-1])
            atom_indices = [int(i) for i in line.split('(')[1].split(')')[0].strip().replace(',', ' ').split()]
            range_start, range_end = line.split('range')[1].split('steps')[0].strip().strip('=').strip().split('..')
            self.dim += 1
            self.shape.append(scan_step)
            self.scan_atom_indices_list.append(atom_indices)
            self.scan_type_list.append(scan_type)
            self.scan_range_list.append((Decimal(range_start.strip()), Decimal(range_end.strip())))

        # Get atom list from first structure data
        for i, line in enumerate(scan_block):
            if line.startswith('CARTESIAN COORDINATES (ANGSTROEM)'):
                structure = Structure.read_structure(scan_block, i)
                self.atoms = structure.atoms
                break

        # Separate in steps
        start_lines = []
        end_lines = []
        unfinished_start_line = -1
        for i, line in enumerate(scan_block):
            if line.strip().startswith('*') and 'RELAXED SURFACE SCAN STEP' in line:
                assert int(line.strip().strip('*').strip().split()[-1]) == len(start_lines) + 1
                start_lines.append(i)
            if line.strip() == '*** OPTIMIZATION RUN DONE ***':
                end_lines.append(i)
        if len(start_lines) > len(end_lines):
            unfinished_start_line = start_lines.pop()
        assert len(start_lines) == len(end_lines)
        num_finished_steps = len(start_lines)

        # Read each step result
        for cycle in range(num_finished_steps):
            block = scan_block[start_lines[cycle]:end_lines[cycle]+1]
            # Extract current parameters (x self.dim)
            params = []
            for line in block[2:2+self.dim]:
                params.append(Decimal(line.strip().strip('*').strip().split(':')[1].strip()))
            self.parameters_list.append(params)
            # Extract final structure and energy
            current_energy = Decimal('0')
            current_structure_line = -1
            for i, line in enumerate(block):
                if line.startswith('CARTESIAN COORDINATES (ANGSTROEM)'):
                    current_structure_line = i
                elif 'FINAL SINGLE POINT ENERGY' in line:
                    current_energy = Decimal(line.split()[-1])
            self.structure_list.append(Structure.read_structure(block, current_structure_line))
            self.energy_list.append(current_energy)

        # Read unfinished opt as sub job
        if unfinished_start_line > 0:
            end_line = -1
            # Check end line
            for i in range(unfinished_start_line, len(scan_block)):
                if 'The optimization did not converge but reached the maximum number' in scan_block[i]:
                    end_line = i
                    break
            if end_line > 0:
                opt_block = scan_block[unfinished_start_line:end_line+1]
            else:
                opt_block = scan_block[unfinished_start_line:]
            self.sub_jobs.append(ORCAOpt(opt_block, parent_file=self.parent_dir / (self.file_stem + ".out"), name = 'last OPT (unfinished)'))
