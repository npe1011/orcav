import os
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
                               QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                               QTabWidget, QFileDialog, QSplitter, QLabel, QInputDialog)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from orcav.core.result import ORCAResult
from orcav.core.structure import Structure
from orcav.core.freq import ORCAThermalData

class DataPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        
        # Metadata Tab -> Job Information
        self.meta_tab = QWidget()
        self.meta_layout = QVBoxLayout(self.meta_tab)
        
        self.meta_splitter = QSplitter(Qt.Orientation.Vertical)
        self.meta_layout.addWidget(self.meta_splitter)
        
        # Meta Table
        self.meta_table = QTableWidget()
        self.meta_table.setColumnCount(2)
        self.meta_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.meta_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.meta_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.meta_table.verticalHeader().setVisible(False)
        self.meta_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.meta_splitter.addWidget(self.meta_table)
        
        # Input Data wrapper
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.addWidget(QLabel("Job Input Data:"))
        self.input_text = QTextEdit()
        self.input_text.setReadOnly(True)
        self.input_text.setFont(font)
        self.input_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        input_layout.addWidget(self.input_text)
        
        self.meta_splitter.addWidget(input_widget)
        self.tabs.addTab(self.meta_tab, "Job Information")
        
        # Table Tab
        self.table_tab = QWidget()
        self.table_layout = QVBoxLayout(self.table_tab)
        
        # Plot button at the top of Table tab
        self.plot_btn = QPushButton("📊 Show Plot")
        font_large = self.plot_btn.font()
        font_large.setBold(True)
        self.plot_btn.setFont(font_large)
        self.plot_btn.setStyleSheet("padding: 8px; background-color: #2c3e50; color: white; border-radius: 4px;")
        self.plot_btn.hide() # Hidden by default, shown only for OPT/NEB
        self.table_layout.addWidget(self.plot_btn)
        
        # Shifted structure save tools (for FREQ)
        self.freq_tools_widget = QWidget()
        self.freq_tools_layout = QHBoxLayout(self.freq_tools_widget)
        self.freq_tools_layout.setContentsMargins(0, 0, 0, 0)
        self.freq_tools_layout.addWidget(QLabel("Shift Amount (Å):"))
        from PySide6.QtWidgets import QDoubleSpinBox
        self.shift_spin = QDoubleSpinBox()
        self.shift_spin.setRange(-5.0, 5.0)
        self.shift_spin.setSingleStep(0.05)
        self.shift_spin.setValue(0.05)
        self.freq_tools_layout.addWidget(self.shift_spin)
        
        self.save_shifted_xyz_btn = QPushButton("Save shifted xyz")
        self.save_shifted_xyz_btn.clicked.connect(self.save_shifted_xyz)
        self.save_shifted_inp_btn = QPushButton("Save shifted input")
        self.save_shifted_inp_btn.clicked.connect(self.save_shifted_inp)
        self.freq_tools_layout.addWidget(self.save_shifted_xyz_btn)
        self.freq_tools_layout.addWidget(self.save_shifted_inp_btn)
        self.freq_tools_layout.addStretch()
        self.freq_tools_widget.hide()
        self.table_layout.addWidget(self.freq_tools_widget)
        
        self.table_widget = QTableWidget()
        self.table_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_widget.verticalHeader().setVisible(False) # Hide row numbers
        self.table_layout.addWidget(self.table_widget)
        self.tabs.addTab(self.table_tab, "Table")
        
        # Structure Tab -> Coords
        self.structure_tab = QWidget()
        self.structure_layout = QVBoxLayout(self.structure_tab)
        
        self.save_btn_layout = QHBoxLayout()
        self.save_xyz_btn = QPushButton("Save xyz")
        self.save_xyz_btn.clicked.connect(self.save_structure_xyz)
        self.save_inp_btn = QPushButton("Save input")
        self.save_inp_btn.clicked.connect(self.save_structure_inp)
        self.save_btn_layout.addWidget(self.save_xyz_btn)
        self.save_btn_layout.addWidget(self.save_inp_btn)
        self.save_btn_layout.addStretch()
        
        self.structure_layout.addLayout(self.save_btn_layout)
        
        self.structure_text = QTextEdit()
        self.structure_text.setReadOnly(True)
        self.structure_text.setFont(font)
        self.structure_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.structure_layout.addWidget(self.structure_text)
        self.tabs.addTab(self.structure_tab, "Coords")
        
        # Thermodynamics Tab
        self.thermo_tab = QWidget()
        self.thermo_layout = QVBoxLayout(self.thermo_tab)
        
        self.thermo_table = QTableWidget()
        self.thermo_table.setColumnCount(2)
        self.thermo_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.thermo_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.thermo_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.thermo_table.verticalHeader().setVisible(False)
        self.thermo_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.thermo_layout.addWidget(self.thermo_table)
        
        self.tabs.addTab(self.thermo_tab, "Thermodynamics")
        
        self.current_structure: Structure = None
        self.current_result: ORCAResult = None
        self.current_freq_job = None

        self.clear()

    def clear(self):
        self.table_widget.clear()
        self.table_widget.setRowCount(0)
        self.table_widget.setColumnCount(0)
        
        self.meta_table.clearContents()
        self.meta_table.setRowCount(0)
        
        self.thermo_table.clearContents()
        self.thermo_table.setRowCount(0)
        
        self.structure_text.clear()
        self.current_structure = None
        self.current_freq_job = None
        # Tabs visibility will be updated externally

    def _add_table_row(self, table: QTableWidget, prop: str, value: str):
        row = table.rowCount()
        table.insertRow(row)
        prop_item = QTableWidgetItem(prop)
        val_item = QTableWidgetItem(value)
        prop_item.setFlags(prop_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        val_item.setFlags(val_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        table.setItem(row, 0, prop_item)
        table.setItem(row, 1, val_item)

    def show_metadata(self, result: ORCAResult):
        self.current_result = result
        self.meta_table.clearContents()
        self.meta_table.setRowCount(0)
        
        status = "Normal" if result.normal_termination else "Failed/Unfinished"
        time_str = result.total_run_time if result.total_run_time else "Unknown"
        
        self._add_table_row(self.meta_table, "File", result.log_file.as_posix())
        self._add_table_row(self.meta_table, "Status", status)
        self._add_table_row(self.meta_table, "Total Run Time", time_str)
        self._add_table_row(self.meta_table, "Charge", str(result.charge))
        self._add_table_row(self.meta_table, "Multiplicity", str(result.multi))
        
        self.input_text.setPlainText("".join(result.input_data))

    def show_table(self, headers: list, data: list):
        self.table_widget.clear()
        self.table_widget.setColumnCount(len(headers))
        self.table_widget.setHorizontalHeaderLabels(headers)
        self.table_widget.setRowCount(len(data))
        
        for row_idx, row_data in enumerate(data):
            for col_idx, col_data in enumerate(row_data):
                item = QTableWidgetItem(str(col_data))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table_widget.setItem(row_idx, col_idx, item)
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        if len(headers) > 0:
            self.table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

    def show_structure(self, structure: Structure):
        self.current_structure = structure
        xyz_data = structure.get_string()
        xyz_str = f"{structure.num_atom}\n\n" + xyz_data
        self.structure_text.setPlainText(xyz_str)
        
    def show_thermodynamics(self, thermo_list: list):
        self.thermo_table.clearContents()
        self.thermo_table.setRowCount(0)
        
        if not thermo_list:
            return
            
        # Display the last thermo data if multiple exist, or we can just append all.
        # Usually we only care about the single calculation result in the freq job.
        for i, t in enumerate(thermo_list):
            if len(thermo_list) > 1:
                self._add_table_row(self.thermo_table, f"--- Data {i+1} ---", "")
            self._add_table_row(self.thermo_table, "Temperature (K)", str(t.temperature))
            self._add_table_row(self.thermo_table, "Pressure (atm)", str(t.pressure))
            self._add_table_row(self.thermo_table, "Total Mass (amu)", str(t.total_mass))
            self._add_table_row(self.thermo_table, "Electronic Energy (Eh)", str(t.e_el))
            self._add_table_row(self.thermo_table, "Zero point energy (Eh)", str(t.zpve))
            self._add_table_row(self.thermo_table, "Thermal Energy U (Eh)", str(t.u))
            self._add_table_row(self.thermo_table, "Enthalpy H (Eh)", str(t.h))
            self._add_table_row(self.thermo_table, "Entropy S (Eh/K)", str(t.s))
            self._add_table_row(self.thermo_table, "Gibbs Free Energy G (Eh)", str(t.g))

    def update_tabs_visibility(self):
        # 0: Job Info, 1: Table, 2: Coords, 3: Thermo
        self.tabs.setTabEnabled(1, self.table_widget.rowCount() > 0)
        self.tabs.setTabEnabled(2, self.current_structure is not None)
        self.tabs.setTabEnabled(3, self.thermo_table.rowCount() > 0)

    def save_structure_xyz(self):
        if not self.current_structure:
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Structure XYZ", "", "XYZ Files (*.xyz);;All Files (*)")
        if file_path:
            xyz_data = self.current_structure.get_string()
            xyz_str = f"{self.current_structure.num_atom}\n\n" + xyz_data
            with open(file_path, 'w') as f:
                f.write(xyz_str)

    def save_structure_inp(self):
        if not self.current_structure or not self.current_result:
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Structure INP", "", "Input Files (*.inp);;All Files (*)")
        if file_path:
            inp = "".join(self.current_result.input_data)
            inp += f"* xyz {self.current_result.charge} {self.current_result.multi}\n"
            inp += self.current_structure.get_string()
            inp += "*\n"
            with open(file_path, 'w') as f:
                f.write(inp)

    def save_shifted_xyz(self):
        if not self.current_freq_job:
            return
        selected_items = self.table_widget.selectedItems()
        if not selected_items:
            return
        mode = selected_items[0].row()
        shift = self.shift_spin.value()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Shifted Structure", "", "XYZ Files (*.xyz);;All Files (*)")
        if file_path:
            structure = self.current_freq_job.get_shifted_structure(mode, max_shift=shift)
            xyz_str = f"{structure.num_atom}\n\n" + structure.get_string()
            with open(file_path, 'w') as f:
                f.write(xyz_str)

    def save_shifted_inp(self):
        if not self.current_freq_job:
            return
        selected_items = self.table_widget.selectedItems()
        if not selected_items:
            return
        mode = selected_items[0].row()
        shift = self.shift_spin.value()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Shifted Input", "", "Input Files (*.inp);;All Files (*)")
        if file_path:
            structure = self.current_freq_job.get_shifted_structure(mode, max_shift=shift)
            
            # Try to find parent result
            result = None
            if hasattr(self.current_freq_job, 'parent_file'):
                from orcav.core.result import ORCAResult
                try:
                    result = ORCAResult(self.current_freq_job.parent_file)
                except Exception:
                    pass
                    
            if result:
                inp = "".join(result.input_data)
                inp += f"* xyz {result.charge} {result.multi}\n"
            else:
                inp = "! OPT\n* xyz 0 1\n"
                
            inp += structure.get_string()
            inp += "*\n"
            with open(file_path, 'w') as f:
                f.write(inp)
