import os
import copy
import dataclasses
from typing import List, Optional
from decimal import  Decimal
from pathlib import Path

import numpy as np

from orcav.core.base import ORCAJob
from orcav.core.structure import Structure

"""
ORCA FREQ block should start with
VIBRATIONAL FREQUENCIES

and end with 
Maximum memory used throughout the entire PROP-calculation
"""

class ORCAFreq(ORCAJob):
    JOB_TYPE = 'freq'

    def __init__(self, freq_block: List[str], init_structure: Structure, parent_file: Path, name: str = 'freq'):
        super().__init__(parent_file=parent_file, name=name)
        self.init_structure: Structure = init_structure
        self.num_atom = self.init_structure.num_atom
        self.num_imaginary_freq: int = 0
        self.scaling_factor: Decimal = Decimal(1.000000000)
        self.freq_list: List[Decimal] = []  # frequency value list
        self.freq_matrix_list: List[np.ndarray] = []  # List of array(num_atom, 3)
        self.thermal_data_list: List[ORCAThermalData] = [] # List of thermal data

        # check start lines of sub data blocks. Multiple Thermal data are possible.
        assert freq_block[0].strip() == 'VIBRATIONAL FREQUENCIES'
        start_normal_modes = None
        start_thermal_data_lines = []
        for i, line in enumerate(freq_block):
            if line.strip() == 'NORMAL MODES':
                start_normal_modes = i
            if line.strip().startswith('THERMOCHEMISTRY AT'):
                start_thermal_data_lines.append(i)

        # Get scaling factor
        assert freq_block[3].strip().startswith('Scaling factor for frequencies')
        self.scaling_factor = Decimal(freq_block[3].split('=')[1].strip().split()[0].strip())

        # read frequencies from line 5 to next blank line
        # 0:         0.00 cm**-1
        # 1: ...
        assert freq_block[5].strip().startswith('0:')
        assert 'cm**-1' in freq_block[5]
        i = 5
        while True:
            line = freq_block[i].strip()
            i+= 1
            if line == '':
                break
            self.freq_list.append(Decimal(line.split(':')[1].strip().split()[0]))
            if 'imaginary' in line:
                self.num_imaginary_freq += 1

        # Separate normal modes logs in blocks (1 block, 6 data)
        num_freq = len(self.freq_list)
        if num_freq % 6 == 0:
            num_block = num_freq // 6
        else:
            num_block = num_freq // 6 + 1
        blocks = []
        for n in range(num_block):
            start = start_normal_modes + 7 + n * (num_freq + 1)
            end = start + num_freq + 1
            blocks.append(freq_block[start:end])

        # vib_vector_list[n] > n's vibrational vector (3*num_atoms)
        vib_vector_list = []
        for block in blocks:
            header = block.pop(0)
            n_modes = len(header.strip().split())  # number of data in this block (6 except for the final block)
            temp_vector_list = [[] for _ in range(n_modes)]
            for line in block:
                for (i, x) in enumerate(line.strip().split()[1:]):  # 0      -0.000012  -0.044812  -0.006221  -0.101069   0.061635   0.122936
                    temp_vector_list[i].append(float(x))
            vib_vector_list.extend(temp_vector_list)
        # Convert to num_atoms*3 array for each data
        self.freq_matrix_list = [np.array(v).reshape((-1,3)) for v in vib_vector_list]
        assert self.num_atom == self.freq_matrix_list[0].shape[0]

        # Read thermal data; first get each blocks
        for start_line in start_thermal_data_lines:
            temperature = pressure = total_mass = cutoff_freq = e_el = zpe = u = h = s = g = g_corr = Decimal(0)
            quasi_rrho = True
            for line in freq_block[start_line:]:
                line = line.strip()
                # Data for calc. conditions
                if line.startswith('Temperature') and '...' in line:
                    temperature = Decimal(line.split()[-2])
                elif line.startswith('Pressure') and '...' in line:
                    pressure = Decimal(line.split()[-2])
                elif line.startswith('Total Mass') and '...' in line:
                    total_mass = Decimal(line.split()[-2])
                elif line.startswith('Quasi RRHO') and '...' in line:
                     quasi_rrho = line.split()[-1].strip() == 'True'
                elif line.startswith('Cut-Off Frequency') and '...' in line:
                    cutoff_freq = Decimal(line.split()[-2])
                # Thermochemistry data
                elif line.startswith('Electronic energy') and  '...' in line:
                    e_el = Decimal(line.split()[-2])
                elif line.startswith('Zero point energy') and '...' in line:
                    zpe = Decimal(line.split()[-4])
                elif line.startswith('Total thermal energy') and '...' not in line:
                    u = Decimal(line.split()[-2])
                elif line.startswith('Total Enthalpy') and '...' in line:
                    h = Decimal(line.split()[-2])
                elif line.startswith('Final entropy term') and '...' in line:
                    s = Decimal(line.split()[-4])
                elif line.startswith('Final Gibbs free energy') and '...' in line:
                    g = Decimal(line.split()[-2])
                elif line.startswith('G-E(el)') and '...' in line:
                    g_corr = Decimal(line.split()[-4])
                    assert abs(g_corr + e_el - g) < Decimal('0.0000001')
                    break
            thermal = ORCAThermalData(temperature,
                                      pressure,
                                      total_mass,
                                      quasi_rrho,
                                      cutoff_freq,
                                      e_el,
                                      zpe,
                                      u,
                                      u-e_el,
                                      h,
                                      h-e_el,
                                      s,
                                      g,
                                      g_corr)
            self.thermal_data_list.append(thermal)

    def save_animation_xyz(self, normal_mode: int, file: os.PathLike, step: int = 20, max_shift: float = 0.5):
        """
        save a xyz file for visualization of normal mode animation.
        :param normal_mode: number of normal mode (0,1,...)
        :param file: output file
        :param step: step for each direction
        :param max_shift:  max shift for atoms in angstrom
        """

        # weight: move move_matrix * weight in each step
        move_matrix = self.freq_matrix_list[normal_mode]
        max_vector_size = np.sqrt(np.max(np.sum(move_matrix * move_matrix, axis=1)))
        weight = max_shift / (max_vector_size * step)

        init_coordinate = self.init_structure.get_coordinates_np()
        atoms = self.init_structure.get_atoms()
        output_num_atom = self.num_atom

        file = Path(file)

        with file.open(mode='w') as f:
            forward_coordinates = [init_coordinate + s * weight * move_matrix for s in range(1, step+1)]
            backward_coordinates = [init_coordinate - s * weight * move_matrix for s in range(1, step+1)]

            # forward
            f.write(str(output_num_atom) + '\n')
            f.write('Initial Structure\n')
            f.write(self._structure_string_from_atoms_and_coordinate_array(atoms, init_coordinate))
            for coordinate in forward_coordinates:
                f.write(str(output_num_atom) + '\n')
                f.write('\n')
                f.write(self._structure_string_from_atoms_and_coordinate_array(atoms, coordinate))
            for coordinate in reversed(forward_coordinates):
                f.write(str(output_num_atom) + '\n')
                f.write('\n')
                f.write(self._structure_string_from_atoms_and_coordinate_array(atoms, coordinate))

            # backward
            f.write(str(output_num_atom) + '\n')
            f.write('Initial Structure\n')
            f.write(self._structure_string_from_atoms_and_coordinate_array(atoms, init_coordinate))
            for coordinate in backward_coordinates:
                f.write(str(output_num_atom) + '\n')
                f.write('\n')
                f.write(self._structure_string_from_atoms_and_coordinate_array(atoms, coordinate))
            for coordinate in reversed(backward_coordinates):
                f.write(str(output_num_atom) + '\n')
                f.write('\n')
                f.write(self._structure_string_from_atoms_and_coordinate_array(atoms, coordinate))

            f.write(str(output_num_atom) + '\n')
            f.write('Initial Structure\n')
            f.write(self._structure_string_from_atoms_and_coordinate_array(atoms, init_coordinate))

    def get_shifted_structure(self, normal_mode: int, max_shift: float = 0.05) -> Structure:
        structure = copy.deepcopy(self.init_structure)
        # weight: move move_matrix * weight in each step
        move_matrix = self.freq_matrix_list[normal_mode]
        max_vector_size = np.sqrt(np.max(np.sum(move_matrix * move_matrix, axis=1)))
        weight = max_shift / max_vector_size
        new_coordinates = structure.get_coordinates_np() + weight * move_matrix
        structure.set_coordinates_np(new_coordinates)
        return structure

    @staticmethod
    def _structure_string_from_atoms_and_coordinate_array(atoms: List[str], coordinate_array: np.ndarray):
        structure_string = ''
        assert len(atoms) == coordinate_array.shape[0]
        for i in range(len(atoms)):
            structure_string += '{0:<4} {1:>20.12f} {2:>20.12f} {3:>20.12f}\n'.format(
                atoms[i], coordinate_array[i,0], coordinate_array[i,1], coordinate_array[i,2])
        return structure_string

    @classmethod
    def read_freq(cls, init_structure: Structure, block_data: List[str], parent_file: Path, start_line: int = 0, name: str = 'freq') -> Optional['ORCAFreq']:
        i = start_line
        l = len(block_data)
        start_freq = -1
        end_freq = -1
        while i < l:
            line = block_data[i]
            in_block = False
            if line.strip().startswith('VIBRATIONAL FREQUENCIES'):
                start_freq = i
            elif start_freq > 0 and 'Maximum memory used throughout the entire PROP-calculation:' in line:
                end_freq = i
                break
            i += 1
        if start_freq > 0 and end_freq > 0:
            return cls(freq_block=block_data[start_freq:end_freq+1], init_structure=init_structure, parent_file=parent_file, name=name)
        else:
            return None


@dataclasses.dataclass
class ORCAThermalData:
    temperature : Decimal
    pressure : Decimal
    total_mass: Decimal
    quasi_rrho: bool
    cutoff_freq_rrho: Decimal
    e_el : Decimal
    zpve : Decimal
    u: Decimal
    u_corr: Decimal
    h : Decimal
    h_corr : Decimal
    s: Decimal
    g : Decimal
    g_corr : Decimal
