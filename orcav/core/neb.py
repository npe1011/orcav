from pathlib import Path
from typing import List, Optional, Literal
from decimal import Decimal

from orcav.core.base import ORCAJob
from orcav.core.structure import Structure
from orcav.core.opt import ORCAOpt
from orcav.core.utils import check_file

"""
ORCA NEB block should start with
Nudged Elastic Band Calculation

and end with
STATISTICS
(TS opt in NEB-TS is also involved.)
"""

class ORCANEB(ORCAJob):
    JOB_TYPE = 'neb'
    def __init__(self, neb_block: List[str], parent_file: Path, name: str = 'neb'):
        super().__init__(parent_file=parent_file, name=name)
        # NEB conditions
        self.preopt: bool = False
        self.free_end: bool = False
        self.ci: bool = False
        self.zoom: bool = False
        self.num_images: int = 0
        self.num_path_length: int = 0
        self.peak_top_index: int = 0
        self.ts_optimization: bool = False
        # Reading files
        self.trajectory_history_file: Optional[Path] = None
        self.mep_file: Optional[Path] = None
        self.peak_top_file: Optional[Path] = None
        # Other parameters
        self.neb_converged: bool = False
        self.zoom_converged: bool = False
        self.num_iteration: int = 0
        self.num_zoom_iteration: int = 0
        # Keep text logs to show
        self.neb_opt_log:  List[str] = []
        self.zoom_opt_log: List[str] = []
        self.path_summary: List[str] = []
        # Main result data (should be read from xyz file)
        self.neb_path_structures_list: List[List[Structure]] = []
        self.neb_path_energies_list: List[List[Decimal]] = []
        self.zoom_path_structures_list: List[List[Structure]] = []
        self.zoom_path_energies_list: List[List[Decimal]] = []
        self.history_structures_list: List[List[Structure]] = []
        self.history_energies_list: List[List[Decimal]] = []

        # Check the conditions for NEB initial block
        for line in neb_block:
            if 'Constrained atoms' in line:
                break
            elif 'Number of intermediate images' in line:
                self.num_images = int(line.strip().split()[-1])
            elif 'Optimization of end points before NEB' in line:
                self.preopt = (line.strip().split()[-1].lower() == 'yes')

        # Extract preopt blocks
        start_reactant_opt = -1
        end_reactant_opt = -1
        start_product_opt = -1
        end_product_opt = -1
        current_block = 'none'
        for i, line in enumerate(neb_block):
            if line.strip() == 'REACTANT (ANGSTROEM)':
                break
            elif line.strip() == 'REACTANT OPTIMIZATION':
                start_reactant_opt = i
                current_block = 'reactant'
            elif line.strip() == 'PRODUCT OPTIMIZATION':
                start_product_opt = i
                current_block = 'product'
            elif line.strip() == '*** OPTIMIZATION RUN DONE ***' or 'The optimization did not converge but reached the maximum number' in line:
                if current_block == 'reactant':
                    end_reactant_opt = i
                    current_block = 'none'
                elif current_block == 'product':
                    end_product_opt = i
                    current_block = 'none'
        if start_reactant_opt > 0:
            if end_reactant_opt < 0:
                end_reactant_opt = len(neb_block)-1
            self.sub_jobs.append(ORCAOpt(opt_block=neb_block[start_reactant_opt:end_reactant_opt+1],
                                         parent_file=parent_file,
                                         name='Reactant Opt'))
        if start_product_opt > 0:
            if end_product_opt < 0:
                end_product_opt = len(neb_block)-1
            self.sub_jobs.append(ORCAOpt(opt_block=neb_block[start_product_opt:end_product_opt+1],
                                         parent_file=parent_file,
                                         name='Product OPT'))

        # Extract TS opt block
        start_ts_opt_line = -1
        end_ts_opt_line = -1
        for i, line in enumerate(neb_block):
            if line.strip().startswith('*') and 'TS OPTIMIZATION' in line:
                start_ts_opt_line = i
            elif start_ts_opt_line > 0 and (line.strip() == '*** OPTIMIZATION RUN DONE ***' or 'The optimization did not converge but reached the maximum number' in line):
                end_ts_opt_line = i
        if start_ts_opt_line > 0:
            self.ts_optimization = True
            if end_ts_opt_line < 0:
                end_ts_opt_line = len(neb_block)-1
            self.sub_jobs.append(ORCAOpt(opt_block=neb_block[start_ts_opt_line:end_ts_opt_line+1], parent_file=parent_file, name='TS OPT'))

        # Read NEB settings block
        start = 0
        for i, line in enumerate(neb_block):
            if line.strip().startswith('NEB settings'):
                start = i + 2
                break
        if start > 0:
            for line in neb_block[start:]:
                if line.strip().startswith('----'):
                    break
                elif 'Method type' in line and '....' in line:
                    mt = line.strip().split('....')[1].strip().lower()
                    if mt == 'regular':
                        self.ci = False
                        self.zoom = False
                    elif mt == 'climbing image':
                        self.ci = True
                        self.zoom = False
                    elif 'zoom' in mt:
                        self.ci = True
                        self.zoom = True
                elif 'Free endpoints' in line:
                    self.free_end = (line.strip().split()[-1].lower() == 'on')

        # Parse other information (case: regular, ci, zoom)
        if self.zoom:
            self._parse_zoom_neb(neb_block)
        elif self.ci:
            self._parse_neb_ci(neb_block)
        else:
            self._parse_neb_regular(neb_block)

    def _parse_neb_regular(self, neb_block: List[str]):
        in_block = False
        trajectory_history_file_candidates = [self.parent_dir / (self.file_stem + '_MEP_ALL_trj.xyz')]
        mep_file_candidates = [self.parent_dir / (self.file_stem + '_MEP_trj.xyz')]
        peak_top_file_candidates = [self.parent_dir / (self.file_stem + '_NEB-HEI_converged.xyz')]
        start_iteration = -1
        for i, line in enumerate(neb_block):
            if line.strip() == 'NEB OPTIMIZATION':
                in_block = True
            elif in_block and 'Current trajectory will be written to' in line:
                mep_file_candidates.append(self.parent_dir /line.strip().split('....')[1].strip())
            elif in_block and 'Trajectory history will be written to' in line:
                trajectory_history_file_candidates.append(self.parent_dir /line.strip().split('....')[1].strip())
            elif in_block and 'Highest energy image will be written to' in line:
                peak_top_file_candidates.append(self.parent_dir /line.strip().split('....')[1].strip())
            elif in_block and 'Starting iterations:' in line:
                start_iteration = i + 2
                break

        # Extract MEP Path
        for mep_file in mep_file_candidates:
            if mep_file.exists():
                self.mep_file = mep_file
                structures, energies = Structure.read_xyz_by_orca(self.mep_file)
                if len(structures) > 0:
                    self.neb_path_structures_list = [structures]
                    self.neb_path_energies_list = [energies]
                break
        
        for hist_file in trajectory_history_file_candidates:
            if hist_file.exists():
                self.trajectory_history_file = hist_file
                self._parse_history_file_dynamically()
                break

        for p in peak_top_file_candidates:
            if p.exists():
                self.peak_top_file = p
                break
    def _parse_neb_ci(self, neb_block: List[str]):
        in_block = False
        trajectory_history_file_candidates = [self.parent_dir / (self.file_stem + '_MEP_ALL_trj.xyz')]
        mep_file_candidates = [self.parent_dir / (self.file_stem + '_MEP_trj.xyz')]
        peak_top_file_candidates = [self.parent_dir / (self.file_stem + '_NEB-CI_converged.xyz')]
        start_iteration = -1
        for i, line in enumerate(neb_block):
            if line.strip() == 'NEB OPTIMIZATION':
                in_block = True
            elif in_block and 'Current trajectory will be written to' in line:
                mep_file_candidates.append(self.parent_dir /line.strip().split('....')[1].strip())
            elif in_block and 'Trajectory history will be written to' in line:
                trajectory_history_file_candidates.append(self.parent_dir /line.strip().split('....')[1].strip())
            elif in_block and 'Highest energy image will be written to' in line:
                peak_top_file_candidates.append(self.parent_dir /line.strip().split('....')[1].strip())
            elif in_block and 'Starting iterations:' in line:
                start_iteration = i + 2
                break

        # Extract MEP Path
        for mep_file in mep_file_candidates:
            if mep_file.exists():
                self.mep_file = mep_file
                structures, energies = Structure.read_xyz_by_orca(self.mep_file)
                if len(structures) > 0:
                    self.neb_path_structures_list = [structures]
                    self.neb_path_energies_list = [energies]
                break
        
        for hist_file in trajectory_history_file_candidates:
            if hist_file.exists():
                self.trajectory_history_file = hist_file
                self._parse_history_file_dynamically()
                break

        for p in peak_top_file_candidates:
            if p.exists():
                self.peak_top_file = p
                break

    def _parse_zoom_neb(self, neb_block: List[str]):
        in_block = False
        trajectory_history_file_candidates = [self.parent_dir / (self.file_stem + '_MEP_ALL_trj.xyz')]
        mep_file_candidates = [self.parent_dir / (self.file_stem + '_MEP_zoom.allxyz'), self.parent_dir / (self.file_stem + '_MEP_trj.xyz')]
        peak_top_file_candidates = [self.parent_dir / (self.file_stem + '_NEB-TS_converged.xyz'), self.parent_dir / (self.file_stem + '_NEB-CI_converged.xyz')]
        start_iteration = -1
        for i, line in enumerate(neb_block):
            if line.strip() == 'NEB OPTIMIZATION' or 'STARTING SECOND NEB OPTIMIZATION' in line:
                in_block = True
            elif in_block and 'Current trajectory will be written to' in line:
                mep_file_candidates.append(self.parent_dir / line.strip().split('....')[1].strip())
            elif in_block and 'Trajectory history will be appended to' in line:
                trajectory_history_file_candidates.append(self.parent_dir / line.strip().split('....')[1].strip())
            elif in_block and 'Highest energy image will be written to' in line:
                peak_top_file_candidates.append(self.parent_dir / line.strip().split('....')[1].strip())
            elif in_block and 'Converged TS will be written to' in line:
                peak_top_file_candidates.append(self.parent_dir / line.strip().split('....')[1].strip())
            elif in_block and 'Starting iterations:' in line:
                start_iteration = i + 2
                break

        # Extract MEP Path
        for mep_file in mep_file_candidates:
            if mep_file.exists():
                self.mep_file = mep_file
                structures, energies = Structure.read_xyz_by_orca(self.mep_file)
                if len(structures) > 0:
                    self.neb_path_structures_list = [structures]
                    self.neb_path_energies_list = [energies]
                break
        
        for hist_file in trajectory_history_file_candidates:
            if hist_file.exists():
                self.trajectory_history_file = hist_file
                self._parse_history_file_dynamically()
                break

        for p in peak_top_file_candidates:
            if p.exists():
                self.peak_top_file = p
                break

    def _parse_history_file_dynamically(self):
        hist_structs, hist_energies = Structure.read_xyz_by_orca(self.trajectory_history_file)
        if not hist_structs:
            return
        
        import numpy as np
        
        c_start = hist_structs[0].get_coordinates_np()
        boundaries = [0]
        for i in range(1, len(hist_structs)):
            c_i = hist_structs[i].get_coordinates_np()
            c_prev = hist_structs[i-1].get_coordinates_np()
            
            rmsd_to_start = np.sqrt(np.mean(np.sum((c_i - c_start)**2, axis=1)))
            rmsd_to_prev = np.sqrt(np.mean(np.sum((c_i - c_prev)**2, axis=1)))
            
            if rmsd_to_start < rmsd_to_prev:
                boundaries.append(i)
                c_start = c_i
                
        boundaries.append(len(hist_structs))
        
        self.history_structures_list = []
        self.history_energies_list = []
        for i in range(len(boundaries) - 1):
            start_idx = boundaries[i]
            end_idx = boundaries[i+1]
            self.history_structures_list.append(hist_structs[start_idx:end_idx])
            self.history_energies_list.append(hist_energies[start_idx:end_idx])










