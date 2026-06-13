from typing import List, Optional
from decimal import  Decimal
from pathlib import Path

from orcav.core.base import ORCAJob
from orcav.core.freq import ORCAFreq
from orcav.core.structure import Structure

"""
ORCA Opt block should start with
* Geometry Optimization Run *

and end with
*** OPTIMIZATION RUN DONE ***
or
The optimization did not converge but reached the maximum number..
"""


class ORCAOpt(ORCAJob):
    JOB_TYPE = 'opt'

    def __init__(self, opt_block: List[str], parent_file: Path, name: str = 'opt'):
        super().__init__(parent_file=parent_file, name=name)
        self.num_opt_cycle: int = 0
        self.structure_list: List[Structure] = []
        self.energy_list: List[Decimal] = []
        self.energy_change_list: List[Decimal] = []
        self.energy_change_converged_list: List[bool] = []
        self.energy_change_threshold_list: List[Decimal] = []
        self.rms_grad_list: List[Decimal] = []
        self.rms_grad_converged_list: List[bool] = []
        self.rms_grad_threshold_list: List[Decimal] = []
        self.max_grad_list: List[Decimal] = []
        self.max_grad_converged_list: List[bool] = []
        self.max_grad_threshold_list: List[Decimal] = []
        self.rms_step_list: List[Decimal] = []
        self.rms_step_converged_list: List[bool] = []
        self.rms_step_threshold_list: List[Decimal] = []
        self.max_step_list: List[Decimal] = []
        self.max_step_converged_list: List[bool] = []
        self.max_step_threshold_list: List[Decimal] = []
        self.freq_data_list: List[ORCAFreq] = []
        self.optimized_structure: Optional[Structure] = None
        self.optimized_energy: Decimal = Decimal(0)
        self.converged: bool = False

        # Split in blocks with optimization cycle
        # Only read finished cycle to avoid errors
        cycle_start_lines: List[int] = []
        cycle_end_lines: List[int] = []
        for i, line in enumerate(opt_block):
            if 'GEOMETRY OPTIMIZATION CYCLE' in line:
                assert int(line.strip().strip('*').strip().split()[-1]) == len(cycle_start_lines) + 1
                cycle_start_lines.append(i)
            elif line.strip().startswith('The optimization has not yet converged'):
                cycle_end_lines.append(i)
            elif 'THE OPTIMIZATION HAS CONVERGED' in line:
                cycle_end_lines.append(i)
                self.converged = True

        if len(cycle_end_lines) < len(cycle_start_lines):
            cycle_start_lines.pop()
        if not len(cycle_start_lines) == len(cycle_end_lines):
            raise RuntimeError('Opt cycle log is in an unexpected form. Failed to split cycles.')
        self.num_opt_cycle = len(cycle_start_lines)

        # Read each cycle
        for cycle in range(self.num_opt_cycle):
            block = opt_block[cycle_start_lines[cycle]:cycle_end_lines[cycle]]
            freq: Optional[ORCAFreq] = None

            for i, line in enumerate(block):

                if line.startswith('CARTESIAN COORDINATES (ANGSTROEM)'):
                    self.structure_list.append(Structure.read_structure(block, i + 2))

                elif 'FINAL SINGLE POINT ENERGY' in line:
                    self.energy_list.append(Decimal(line.split()[-1]))

                elif line.startswith('VIBRATIONAL FREQUENCIES'):
                    freq = ORCAFreq.read_freq(self.structure_list[-1], block, parent_file=parent_file, start_line=i, name=f'freq at cyc.{cycle+1}')

                elif 'Geometry convergence' in line:
                    if cycle == 0:  # No energy change in the fist step
                        self.energy_change_list.append(Decimal('0.0000000000'))
                        self.energy_change_converged_list.append(False)
                        self.energy_change_threshold_list.append(Decimal('0.0000000000'))

                        assert 'RMS gradient' in block[i + 3]
                        terms = block[i + 3].strip().split()
                        self.rms_grad_list.append(Decimal(terms[-3]))
                        self.rms_grad_converged_list.append(terms[-1] == 'YES')
                        self.rms_grad_threshold_list.append(Decimal(terms[-2]))

                        assert 'MAX gradient' in block[i + 4]
                        terms = block[i + 4].strip().split()
                        self.max_grad_list.append(Decimal(terms[-3]))
                        self.max_grad_converged_list.append(terms[-1] == 'YES')
                        self.max_grad_threshold_list.append(Decimal(terms[-2]))

                        assert 'RMS step' in block[i + 5]
                        terms = block[i + 5].strip().split()
                        self.rms_step_list.append(Decimal(terms[-3]))
                        self.rms_step_converged_list.append(terms[-1] == 'YES')
                        self.rms_step_threshold_list.append(Decimal(terms[-2]))

                        assert 'MAX step' in block[i + 6]
                        terms = block[i + 6].strip().split()
                        self.max_step_list.append(Decimal(terms[-3]))
                        self.max_step_converged_list.append(terms[-1] == 'YES')
                        self.max_step_threshold_list.append(Decimal(terms[-2]))

                    else:

                        assert 'Energy change' in block[i + 3]
                        terms = block[i + 3].strip().split()
                        self.energy_change_list.append(Decimal(terms[-3]))
                        self.energy_change_converged_list.append(terms[-1] == 'YES')
                        self.energy_change_threshold_list.append(Decimal(terms[-2]))

                        assert 'RMS gradient' in block[i + 4]
                        terms = block[i + 4].strip().split()
                        self.rms_grad_list.append(Decimal(terms[-3]))
                        self.rms_grad_converged_list.append(terms[-1] == 'YES')
                        self.rms_grad_threshold_list.append(Decimal(terms[-2]))

                        assert 'MAX gradient' in block[i + 5]
                        terms = block[i + 5].strip().split()
                        self.max_grad_list.append(Decimal(terms[-3]))
                        self.max_grad_converged_list.append(terms[-1] == 'YES')
                        self.max_grad_threshold_list.append(Decimal(terms[-2]))

                        assert 'RMS step' in block[i + 6]
                        terms = block[i + 6].strip().split()
                        self.rms_step_list.append(Decimal(terms[-3]))
                        self.rms_step_converged_list.append(terms[-1] == 'YES')
                        self.rms_step_threshold_list.append(Decimal(terms[-2]))

                        assert 'MAX step' in block[i + 7]
                        terms = block[i + 7].strip().split()
                        self.max_step_list.append(Decimal(terms[-3]))
                        self.max_step_converged_list.append(terms[-1] == 'YES')
                        self.max_step_threshold_list.append(Decimal(terms[-2]))

            self.freq_data_list.append(freq)

        # Set freq data in sub_jobs
        for freq in self.freq_data_list:
            if freq is not None:
                self.sub_jobs.append(freq)

        # If converged, try to read final geometry and energy
        if self.converged:
            check = False
            after_opt_block = opt_block[cycle_end_lines[-1]:]
            for i, line in enumerate(after_opt_block):
                if 'FINAL ENERGY EVALUATION AT THE STATIONARY POINT' in line:
                    check = True
                    continue
                if 'CARTESIAN COORDINATES (ANGSTROEM)' in line and self.optimized_structure is None and check:
                    self.optimized_structure = Structure.read_structure(after_opt_block, i + 2)
                    continue
                if 'FINAL SINGLE POINT ENERGY ' in line and self.optimized_structure is not None and check:
                    self.optimized_energy = Decimal(line.strip().split()[-1])
                    break

