import os
from typing import List
from pathlib import Path

from decimal import Decimal

from orcav.core.utils import print_warnings
from orcav.core.structure import Structure
from orcav.core.base import ORCAJob
from orcav.core.sp import ORCASPJob
from orcav.core.freq import ORCAFreq
from orcav.core.opt import ORCAOpt
from orcav.core.irc import ORCAIRC
from orcav.core.neb import ORCANEB
from orcav.core.scan import ORCAScan



class ORCAResult:
    def __init__(self, log_file: os.PathLike):
        self.log_file: Path = Path(log_file).absolute()
        self.job_name: str = self.log_file.stem
        self.log_data: List[str] = []
        self.job_data: List[ORCAJob] = []
        self.input_data: List[str] = []
        self.input_structure_data: List[str] = []
        self.normal_termination: bool = False
        self.charge: int = 0
        self.multi: int = 1

        start_input_line: int = -1
        end_input_line: int = -1

        self.total_run_time: str = ""

        # Parse log data for extract basic information
        with self.log_file.open() as f:
            self.log_data = f.readlines()
        for i, line in enumerate(self.log_data):
            if '****ORCA TERMINATED NORMALLY****' in line:
                self.normal_termination = True
            if start_input_line < 0 and line.strip() == 'INPUT FILE':
                start_input_line = i + 3
            if '****END OF INPUT****' in line and start_input_line > 0 > end_input_line:
                end_input_line = i
            if 'TOTAL RUN TIME:' in line:
                self.total_run_time = line.strip().split('TOTAL RUN TIME:')[1].strip()

        # Parse input block
        if start_input_line > 0 and end_input_line > 0:
            self._parse_input_block(self.log_data[start_input_line:end_input_line])
        else:
            print_warnings('Warning: No input block found in the log.')

        # Extract first-class blocks
        current_block_data = []
        current_block_type = ''  # sp, opt, freq, neb, scan, irc
        current_structure_start_line = -1  # for isolated freq block
        current_energy: Decimal = Decimal('0.000000')  # For IRC calculation
        for i, line in enumerate(self.log_data):
            if line.strip().startswith('CARTESIAN COORDINATES (ANGSTROEM)'):
                current_structure_start_line = i + 2
            if line.strip().startswith('FINAL SINGLE POINT ENERGY'):
                current_energy = Decimal(line.strip().split()[-1])
            # When starting new first-class block
            if not current_block_type:
                if line.strip() == '* Single Point Calculation *':
                    current_block_type = 'sp'
                    current_block_data = [line]
                elif line.strip() == '* Geometry Optimization Run *' or ('*' in line and 'TS OPTIMIZATION' in line and 'CONVERGED' not in line):
                    current_block_type = 'opt'
                    current_block_data = [line]
                elif line.strip() == 'VIBRATIONAL FREQUENCIES':
                    current_block_type = 'freq'
                    current_block_data = [line]
                elif line.strip() == 'Nudged Elastic Band Calculation':
                    current_block_type = 'neb'
                    current_block_data = [line]
                elif line.strip() == '*    Relaxed Surface Scan    *':
                    current_block_type = 'scan'
                    current_block_data = [line]
                elif line.strip() == 'Intrinsic Reaction Coordinate Calculation':
                    current_block_type = 'irc'
                    current_block_data = [line]
                else:
                    continue
            # When already in a block
            else:
                current_block_data.append(line)
                if current_block_type == 'sp':
                    if line.strip().startswith('FINAL SINGLE POINT ENERGY'):
                        self.job_data.append(ORCASPJob(sp_block=current_block_data, parent_file=self.log_file, name='SP'))
                        current_block_data = []
                        current_block_type = ''
                elif current_block_type == 'opt':
                    if line.strip() == '*** OPTIMIZATION RUN DONE ***' or 'The optimization did not converge but reached the maximum number' in line:
                        self.job_data.append(ORCAOpt(opt_block=current_block_data, parent_file=self.log_file, name='OPT'))
                        current_block_data = []
                        current_block_type = ''
                elif current_block_type == 'freq':
                    if line.strip().startswith('Maximum memory used throughout the entire PROP-calculation:'):
                        init_structure = Structure.read_structure(self.log_data, start_line=current_structure_start_line)
                        self.job_data.append(ORCAFreq(init_structure=init_structure,
                                                      freq_block=current_block_data,
                                                      parent_file=self.log_file,
                                                      name='FREQ'))
                        current_block_data = []
                        current_block_type = ''
                elif current_block_type == 'neb':
                    if '*' in line and 'TS OPTIMIZATION' in line and 'CONVERGED' not in line:
                        current_block_data.pop()
                        self.job_data.append(ORCANEB(neb_block=current_block_data, parent_file=self.log_file, name='NEB'))
                        current_block_data = [line]
                        current_block_type = 'opt'
                    elif line.strip() == 'STATISTICS':
                        self.job_data.append(ORCANEB(neb_block=current_block_data, parent_file=self.log_file, name='NEB'))
                        current_block_data = []
                        current_block_type = ''
                elif current_block_type == 'scan':
                    if line.strip() == '**** RELAXED SURFACE SCAN DONE ***' or 'The optimization did not converge but reached the maximum number' in line:
                        self.job_data.append(ORCAScan(current_block_data, parent_file=self.log_file, name='Scan'))
                        current_block_data = []
                        current_block_type = ''
                elif current_block_type == 'irc':
                    if line.strip() == 'IRC PATH SUMMARY ':
                        init_structure = Structure.read_structure(self.log_data, start_line=current_structure_start_line)
                        self.job_data.append(ORCAIRC(irc_block=current_block_data,
                                                     init_structure=init_structure,
                                                     init_energy=current_energy,
                                                     parent_file=self.log_file,
                                                     name='IRC'))
                        current_block_data = []
                        current_block_type = ''

        # When some block does not end until the last line (assume continuing data)
        if current_block_type == 'sp':
            self.job_data.append(ORCASPJob(sp_block=current_block_data, parent_file=self.log_file, name='SP'))
        elif current_block_type == 'opt':
            self.job_data.append(ORCAOpt(opt_block=current_block_data, parent_file=self.log_file, name='OPT'))
        elif current_block_type == 'freq':
            init_structure = Structure.read_structure(self.log_data, start_line=current_structure_start_line)
            self.job_data.append(ORCAFreq(freq_block=current_block_data,
                                          init_structure=init_structure,
                                          parent_file=self.log_file,
                                          name='FREQ'))
        elif current_block_type == 'neb':
            self.job_data.append(ORCANEB(neb_block=current_block_data, parent_file=self.log_file, name='NEB'))
        elif current_block_type == 'scan':
            self.job_data.append(ORCAScan(scan_block=current_block_data, parent_file=self.log_file, name='Scan'))
        elif current_block_type == 'irc':
            init_structure = Structure.read_structure(self.log_data, start_line=current_structure_start_line)
            self.job_data.append(ORCAIRC(irc_block=current_block_data,
                                         init_structure=init_structure,
                                         init_energy=current_energy,
                                         parent_file=self.log_file,
                                         name='IRC'))


    def _parse_input_block(self, input_block: List[str]):
        data = []
        for line in input_block:
            terms = line.split('> ', maxsplit=1)
            if len(terms) == 1:
                data.append('\n')
            else:
               data.append(terms[1])

        # Extract extract charge/multi
        structure_flag = False
        for line in data:
            if structure_flag:
                if line.strip().startswith('*') :
                    structure_flag = False
                else:
                    self.input_structure_data.append(line)
            elif line.strip().startswith('*'):
                terms = line.strip().strip('*').strip().split()
                self.charge = int(terms[-2])
                self.multi = int(terms[-1])
                structure_flag = True
            else:
                self.input_data.append(line)
