import os
import copy
from pathlib import Path
from decimal import Decimal
from typing import List, Tuple

import numpy as np


class Structure:
    def __init__(self, atom_coordinates_block: List[str]):
        self.atoms: List[str] = []
        self.coordinates: List[Tuple[Decimal, Decimal, Decimal]] = []

        for line in atom_coordinates_block:
            if line.strip() == '':
                continue
            try:
                atom, x, y, z, *_ = line.strip().split()
            except:
                raise ValueError('Error reading structure line:', line.strip())
            atom = atom.strip().capitalize()
            x = Decimal(x.strip())
            y = Decimal(y.strip())
            z = Decimal(z.strip())
            self.atoms.append(atom)
            self.coordinates.append((x, y, z))

    @property
    def num_atom(self) -> int:
        return len(self.atoms)

    def get_atoms(self):
        return copy.deepcopy(self.atoms)

    def get_string(self) -> str:
        """
        return string:
        atom1 x1 y1 z1
        atom2 x2 y2 z2
        ...
        """
        data = [f'{self.atoms[i]:<4} {self.coordinates[i][0]:>20.12f} {self.coordinates[i][1]:>20.12f} {self.coordinates[i][2]:>20.12f}' for i in range(self.num_atom)]
        return '\n'.join(data) + '\n'

    def get_coordinates_np(self) -> np.ndarray:
        """
        return xyz coordinates as n*3 numpy array (float)
        :return: numpy array
        """
        coordinates = []
        for line in self.coordinates:
            coordinates.append([float(line[0]), float(line[1]), float(line[2])])
        return np.array(coordinates, dtype=float)

    def set_coordinates_np(self, coordinates: np.ndarray):
        """
        set positions with array (num_atoms * 3)
        """
        assert coordinates.shape == (self.num_atom, 3)
        new_atom_coordinates = []
        for line in coordinates:
            new_atom_coordinates.append([Decimal(line[0]), Decimal(line[1]), Decimal(line[2])])
        self.coordinates = new_atom_coordinates

    def save_xyz_file(self, file: os.PathLike, title: str =''):
        file = Path(file)
        with file.open(mode='w') as f:
            f.write(str(self.num_atom) + '\n')
            f.write(title.rstrip() + '\n')
            f.write(self.get_string())

    def __str__(self):
        return self.get_string()

    @classmethod
    def read_structure(cls, block_data: List[str], start_line: int = 0) -> 'Structure':
        block = []
        i = start_line
        l = len(block_data)
        while i < l:
            line = block_data[i]
            i += 1
            if line.strip() == 'CARTESIAN COORDINATES (ANGSTROEM)' or '--------------' in line:
                continue
            if line.strip() == '':
                break
            block.append(line)
        return cls(block)

    @classmethod
    def read_xyz_by_orca(cls, file: os.PathLike) -> Tuple[List['Structure'], List[Decimal]]:
        """
        Return structure and energy list
        """
        with open(file, 'r') as f:
            data = f.readlines()

        structure_list = []
        energy_list = []

        length = len(data)
        i = 0
        while i < length:
            line = data[i]
            if line.strip() in ['', '>']:
                i += 1
                continue
            try:
                num_atoms = int(line.strip())
            except ValueError:
                i += 1
                continue
            if i + 2 + num_atoms <= length:
                block = data[i+2:i+2+num_atoms]
                structure_list.append(cls(block))
                eline = data[i+1]
                try:
                    energy = Decimal(eline.strip().split()[-1])
                except:
                    energy = Decimal('0.0')
                energy_list.append(energy)
                i = i + 2 + num_atoms
            else:
                break

        return structure_list, energy_list




