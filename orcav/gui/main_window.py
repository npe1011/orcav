import os
from pathlib import Path
from PySide6.QtWidgets import (QMainWindow, QTreeView, QSplitter, QWidget,
                               QVBoxLayout, QFileDialog, QTextEdit,
                               QDialog, QToolBar, QMessageBox)
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QAction, QFontDatabase, QIcon
from PySide6.QtCore import Qt, QItemSelection, QModelIndex

from orcav.core.result import ORCAResult
from orcav.core.base import ORCAJob
from orcav.core.freq import ORCAFreq
from orcav.gui.tree_model import ResultTreeModel
from orcav.gui.viewer3d import Viewer3D
from orcav.gui.plot_widget import PlotWidget
from orcav.gui.data_panel import DataPanel

class TextLogDialog(QDialog):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Text Log")
        self.resize(800, 600)
        layout = QVBoxLayout(self)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        # Use Monospace font
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.text_edit.setFont(font)
        self.text_edit.setPlainText(text)
        layout.addWidget(self.text_edit)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ORCA 6 Log Visualizer")
        self.resize(1200, 800)
        self.setAcceptDrops(True)
        
        self.current_result = None

        # Main splitter (Left: Tree, Center: 3D Viewer, Right: DataPanel)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.main_splitter)

        # Left Panel: Tree View
        self.tree_view = QTreeView()
        self.tree_model = ResultTreeModel(self)
        self.tree_view.setModel(self.tree_model)
        self.tree_view.selectionModel().selectionChanged.connect(self.on_tree_selection_changed)
        self.main_splitter.addWidget(self.tree_view)

        # Center Panel: 3D Viewer
        self.viewer_3d = Viewer3D()
        self.main_splitter.addWidget(self.viewer_3d)
        
        # Right Panel: DataPanel
        self.data_panel = DataPanel()
        self.main_splitter.addWidget(self.data_panel)
        
        self.main_splitter.setSizes([300, 600, 300])

        # Separate window for plots
        self.plot_window = QDialog(self)
        self.plot_window.setWindowTitle("Plot Viewer")
        self.plot_window.resize(600, 600)
        plot_layout = QVBoxLayout(self.plot_window)
        self.plot_widget = PlotWidget()
        plot_layout.addWidget(self.plot_widget)

        # Connect Table selection in DataPanel to Viewer3D animation
        self.data_panel.table_widget.itemSelectionChanged.connect(self.on_table_selection_changed)

        # Menu
        menu = self.menuBar()
        file_menu = menu.addMenu("File")
        open_action = file_menu.addAction("Open ORCA Log")
        open_action.triggered.connect(self.open_file)
        
        # Toolbar
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        self.show_log_action = QAction("Show Log Text", self)
        self.show_log_action.triggered.connect(self.show_log_text)
        self.show_log_action.setEnabled(False)
        toolbar.addAction(self.show_log_action)
        


        # Connect new plot button in DataPanel
        self.data_panel.plot_btn.clicked.connect(self.plot_window.show)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                self.load_log(file_path)
                break # Only load first for now

    def open_file(self):
        # Open file dialog
        file_path, _ = QFileDialog.getOpenFileName(self, "Open ORCA Log", "", "ORCA Output (*.out *.log);;All Files (*)")
        if file_path:
            self.load_log(file_path)

    def load_log(self, file_path: str):
        try:
            result = ORCAResult(file_path)
            self.current_result = result
            self.tree_model.clear()
            self.tree_model.setHorizontalHeaderLabels(['Job / Step'])
            self.tree_model.add_result(result)
            self.tree_view.expandAll()
            
            def collapse_history_nodes(parent_idx):
                for i in range(self.tree_model.rowCount(parent_idx)):
                    child_idx = self.tree_model.index(i, 0, parent_idx)
                    data = child_idx.data(Qt.ItemDataRole.UserRole)
                    if isinstance(data, dict) and (data.get("history_root") or "neb_iteration" in data):
                        self.tree_view.collapse(child_idx)
                    collapse_history_nodes(child_idx)
                    
            collapse_history_nodes(QModelIndex())
            
            self.show_log_action.setEnabled(True)
            self.data_panel.show_metadata(result)
            self.data_panel.plot_btn.hide()
            self.plot_window.hide()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load {file_path}:\n{e}")

    def show_log_text(self):
        if self.current_result:
            dialog = TextLogDialog("".join(self.current_result.log_data), self)
            dialog.show()

    def on_tree_selection_changed(self, selected: QItemSelection, deselected: QItemSelection):
        indexes = selected.indexes()
        if not indexes:
            return
        index = indexes[0]
        data = self.tree_model.data(index, Qt.ItemDataRole.UserRole)
        self.data_panel.clear()
        
        # Determine the root ORCAResult to show metadata
        current_idx = index
        while current_idx.parent().isValid():
            current_idx = current_idx.parent()
        result_data = self.tree_model.data(current_idx, Qt.ItemDataRole.UserRole)
        if isinstance(result_data, ORCAResult):
            self.data_panel.show_metadata(result_data)
        
        self.data_panel.plot_btn.hide()
        self.data_panel.freq_tools_widget.hide()
        self.data_panel.current_freq_job = None
        
        if isinstance(data, ORCAResult):
            pass
            
        elif isinstance(data, ORCAJob):
            if data.JOB_TYPE == 'opt':
                self.data_panel.plot_btn.show()
                self.plot_widget.plot_opt_convergence(
                    data.energy_list,
                    data.rms_grad_list, data.max_grad_list,
                    data.rms_step_list, data.max_step_list,
                    data.rms_grad_threshold_list, data.max_grad_threshold_list,
                    data.rms_step_threshold_list, data.max_step_threshold_list
                )
                
                headers = ["Step", "Energy", "RMS grad", "MAX grad", "RMS step", "MAX step"]
                table_data = []
                for i in range(len(data.energy_list)):
                    table_data.append([
                        i+1,
                        data.energy_list[i] if i < len(data.energy_list) else "",
                        data.rms_grad_list[i] if i < len(data.rms_grad_list) else "",
                        data.max_grad_list[i] if i < len(data.max_grad_list) else "",
                        data.rms_step_list[i] if i < len(data.rms_step_list) else "",
                        data.max_step_list[i] if i < len(data.max_step_list) else ""
                    ])
                self.data_panel.show_table(headers, table_data)

                if data.optimized_structure:
                    self.viewer_3d.load_structure(data.optimized_structure)
                    self.data_panel.show_structure(data.optimized_structure)
                elif data.structure_list:
                    self.viewer_3d.load_structure(data.structure_list[-1])
                    self.data_panel.show_structure(data.structure_list[-1])
                    
            elif data.JOB_TYPE == 'neb':
                self.data_panel.plot_btn.show()
                if data.neb_path_energies_list:
                    headers = ["Image", "Energy (Eh)", "Rel. Energy (kcal/mol)"]
                    from decimal import Decimal
                    e_react = data.neb_path_energies_list[0][0]
                    eh_to_kcal = Decimal('627.509')
                    table_data = []
                    rel_energies = []
                    for i, e in enumerate(data.neb_path_energies_list[0]):
                        rel_e = (e - e_react) * eh_to_kcal
                        table_data.append([i, str(e), f"{rel_e:.2f}"])
                        rel_energies.append(float(rel_e))
                    self.data_panel.show_table(headers, table_data)
                    self.plot_widget.plot_energy(rel_energies, title="NEB Path Energy", xlabel="Image", ylabel="Relative Energy to Reactant (kcal/mol)")
                    
                if data.neb_path_structures_list:
                    max_idx = data.neb_path_energies_list[0].index(max(data.neb_path_energies_list[0]))
                    self.viewer_3d.load_structure(data.neb_path_structures_list[0][max_idx])
                    self.data_panel.show_structure(data.neb_path_structures_list[0][max_idx])
            elif data.JOB_TYPE == 'scan':
                if data.structure_list:
                    self.viewer_3d.load_structure(data.structure_list[0])
                    self.data_panel.show_structure(data.structure_list[0])
                if hasattr(data, 'energy_list') and len(data.energy_list) > 0:
                    headers = ["Point"]
                    for i in range(data.dim):
                        idx_str = ",".join(map(str, data.scan_atom_indices_list[i]))
                        p_name = f"{data.scan_type_list[i].capitalize()} ({idx_str})"
                        headers.append(p_name)
                    headers.extend(["Energy (Eh)", "Rel. Energy (kcal/mol)"])
                    from decimal import Decimal
                    e0 = data.energy_list[0]
                    eh_to_kcal = Decimal('627.509')
                    table_data = []
                    for i in range(len(data.energy_list)):
                        row = [i+1]
                        if i < len(data.parameters_list):
                            params = data.parameters_list[i]
                            for p in params:
                                row.append(str(p))
                        else:
                            for _ in range(data.dim):
                                row.append("")
                        e = data.energy_list[i]
                        rel_e = (e - e0) * eh_to_kcal
                        row.append(str(e))
                        row.append(f"{rel_e:.2f}")
                        table_data.append(row)
                    self.data_panel.show_table(headers, table_data)
                    rel_energies = [float((e - e0) * eh_to_kcal) for e in data.energy_list]
                    if getattr(data, 'dim', 0) == 1:
                        self.data_panel.plot_btn.show()
                        if len(data.parameters_list) == len(data.energy_list):
                            x_vals = [float(p[0]) for p in data.parameters_list]
                        else:
                            x_vals = list(range(1, len(data.energy_list) + 1))
                        self.plot_widget.plot_energy(rel_energies, x_vals=x_vals, title="Scan Path Energy", xlabel=headers[1], ylabel="Relative Energy (kcal/mol)")
                    elif getattr(data, 'dim', 0) == 2:
                        self.data_panel.plot_btn.show()
                        if len(data.parameters_list) == len(data.energy_list):
                            x_vals = [float(p[0]) for p in data.parameters_list]
                            y_vals = [float(p[1]) for p in data.parameters_list]
                            self.plot_widget.plot_2d_scan(x_vals, y_vals, rel_energies, title="2D Scan Energy Surface", xlabel=headers[1], ylabel=headers[2], zlabel="Relative Energy (kcal/mol)")
            elif data.JOB_TYPE == 'irc':
                if hasattr(data, 'structure_list') and data.structure_list:
                    if hasattr(data, 'energy_list') and len(data.energy_list) > 0:
                        max_idx = data.energy_list.index(max(data.energy_list))
                    else:
                        max_idx = 0
                    self.viewer_3d.load_structure(data.structure_list[max_idx])
                    self.data_panel.show_structure(data.structure_list[max_idx])
                    
                    if hasattr(data, 'energy_list') and len(data.energy_list) > 0:
                        self.data_panel.plot_btn.show()
                        headers = ["Point", "Energy (Eh)", "Rel. Energy (kcal/mol)"]
                        from decimal import Decimal
                        e_ts = max(data.energy_list)
                        eh_to_kcal = Decimal('627.509')
                        table_data = []
                        for i, e in enumerate(data.energy_list):
                            rel_e = (e - e_ts) * eh_to_kcal
                            table_data.append([i+1, str(e), f"{rel_e:.2f}"])
                        self.data_panel.show_table(headers, table_data)
                        
                        rel_energies = [float((e - e_ts) * eh_to_kcal) for e in data.energy_list]
                        self.plot_widget.plot_energy(rel_energies, title="IRC Path Energy", xlabel="Point", ylabel="Relative Energy to TS (kcal/mol)")

            elif data.JOB_TYPE == 'freq':
                self.viewer_3d.load_structure(data.init_structure)
                self.data_panel.show_structure(data.init_structure)
                self.data_panel.current_freq_job = data # Save for animation and shift
                
                if getattr(data, 'freq_list', None):
                    self.data_panel.freq_tools_widget.show()
                    headers = ["Mode", "Frequency (cm-1)"]
                    table_data = [[i, f] for i, f in enumerate(data.freq_list)]
                    self.data_panel.show_table(headers, table_data)
                
                if getattr(data, 'thermal_data_list', None) and len(data.thermal_data_list) > 0:
                    self.data_panel.show_thermodynamics(data.thermal_data_list)
                
        elif isinstance(data, dict):
            job = data.get("job")
            if "step" in data and hasattr(job, 'structure_list'):
                step = data["step"]
                self.viewer_3d.load_structure(job.structure_list[step])
                self.data_panel.show_structure(job.structure_list[step])
                if hasattr(job, 'energy_list'):
                    self.data_panel.plot_btn.show()
                    
                    # Update plot content as well so it's consistent
                    if hasattr(job, 'rms_grad_list'):
                        self.plot_widget.plot_opt_convergence(
                            job.energy_list,
                            job.rms_grad_list, job.max_grad_list,
                            job.rms_step_list, job.max_step_list,
                            job.rms_grad_threshold_list, job.max_grad_threshold_list,
                            job.rms_step_threshold_list, job.max_step_threshold_list
                        )
                        
                    headers = ["Step", "Energy", "RMS grad", "MAX grad", "RMS step", "MAX step"]
                    table_data = []
                    for i in range(len(job.energy_list)):
                        table_data.append([
                            i+1,
                            job.energy_list[i] if i < len(job.energy_list) else "",
                            job.rms_grad_list[i] if i < len(job.rms_grad_list) else "",
                            job.max_grad_list[i] if i < len(job.max_grad_list) else "",
                            job.rms_step_list[i] if i < len(job.rms_step_list) else "",
                            job.max_step_list[i] if i < len(job.max_step_list) else ""
                        ])
                    self.data_panel.show_table(headers, table_data)
            elif "image" in data and "neb_iteration" not in data and hasattr(job, 'neb_path_structures_list'):
                img = data["image"]
                self.viewer_3d.load_structure(job.neb_path_structures_list[0][img])
                self.data_panel.show_structure(job.neb_path_structures_list[0][img])
                if hasattr(job, 'neb_path_energies_list') and job.neb_path_energies_list:
                    self.data_panel.plot_btn.show()
                    headers = ["Image", "Energy (Eh)", "Rel. Energy (kcal/mol)"]
                    from decimal import Decimal
                    e_react = job.neb_path_energies_list[0][0]
                    eh_to_kcal = Decimal('627.509')
                    table_data = []
                    rel_energies = []
                    for i, e in enumerate(job.neb_path_energies_list[0]):
                        rel_e = (e - e_react) * eh_to_kcal
                        table_data.append([i, str(e), f"{rel_e:.2f}"])
                        rel_energies.append(float(rel_e))
                    self.data_panel.show_table(headers, table_data)
                    self.plot_widget.plot_energy(rel_energies, title="NEB Path Energy", xlabel="Image", ylabel="Relative Energy to Reactant (kcal/mol)")
            elif "neb_iteration" in data and "image" in data:
                iter_idx = data["neb_iteration"]
                img_idx = data["image"]
                hist_path = job.history_structures_list[iter_idx]
                hist_energies = job.history_energies_list[iter_idx]
                
                if hist_path and img_idx < len(hist_path):
                    self.viewer_3d.load_structure(hist_path[img_idx])
                    self.data_panel.show_structure(hist_path[img_idx])
                
                if hist_energies:
                    self.data_panel.plot_btn.show()
                    headers = ["Image", "Energy (Eh)", "Rel. Energy (kcal/mol)"]
                    from decimal import Decimal
                    e_react = hist_energies[0]
                    eh_to_kcal = Decimal('627.509')
                    table_data = []
                    rel_energies = []
                    for i, e in enumerate(hist_energies):
                        rel_e = (e - e_react) * eh_to_kcal
                        table_data.append([i, str(e), f"{rel_e:.2f}"])
                        rel_energies.append(float(rel_e))
                    self.data_panel.show_table(headers, table_data)
                    self.plot_widget.plot_energy(rel_energies, title=f"NEB Path Energy (Iter {iter_idx})", xlabel="Image", ylabel="Relative Energy to Reactant (kcal/mol)")

            elif "neb_iteration" in data:
                iter_idx = data["neb_iteration"]
                hist_path = job.history_structures_list[iter_idx]
                hist_energies = job.history_energies_list[iter_idx]
                
                if hist_path:
                    max_idx = hist_energies.index(max(hist_energies)) if hist_energies else 0
                    self.viewer_3d.load_structure(hist_path[max_idx])
                    self.data_panel.show_structure(hist_path[max_idx])
                    
                if hist_energies:
                    self.data_panel.plot_btn.show()
                    headers = ["Image", "Energy (Eh)", "Rel. Energy (kcal/mol)"]
                    from decimal import Decimal
                    e_react = hist_energies[0]
                    eh_to_kcal = Decimal('627.509')
                    table_data = []
                    rel_energies = []
                    for i, e in enumerate(hist_energies):
                        rel_e = (e - e_react) * eh_to_kcal
                        table_data.append([i, str(e), f"{rel_e:.2f}"])
                        rel_energies.append(float(rel_e))
                    self.data_panel.show_table(headers, table_data)
                    self.plot_widget.plot_energy(rel_energies, title=f"NEB Path Energy (Iter {iter_idx})", xlabel="Image", ylabel="Relative Energy to Reactant (kcal/mol)")

            elif "history_root" in data:
                # Plot the cumulative history graph
                self.data_panel.plot_btn.show()
                final_path = job.history_structures_list[-1] if job.history_structures_list else []
                final_energies = job.history_energies_list[-1] if job.history_energies_list else []
                if final_path:
                    max_idx = final_energies.index(max(final_energies)) if final_energies else 0
                    self.viewer_3d.load_structure(final_path[max_idx])
                    self.data_panel.show_structure(final_path[max_idx])
                
                if final_energies:
                    headers = ["Image", "Energy (Eh)", "Rel. Energy (kcal/mol)"]
                    from decimal import Decimal
                    e_react = final_energies[0]
                    eh_to_kcal = Decimal('627.509')
                    table_data = []
                    for i, e in enumerate(final_energies):
                        rel_e = (e - e_react) * eh_to_kcal
                        table_data.append([i, str(e), f"{rel_e:.2f}"])
                    self.data_panel.show_table(headers, table_data)

                # Plot history
                self.plot_widget.plot_neb_history(job.history_energies_list)
            elif "point" in data and hasattr(job, 'structure_list'):
                pt = data["point"]
                self.viewer_3d.load_structure(job.structure_list[pt])
                self.data_panel.show_structure(job.structure_list[pt])
                if job.JOB_TYPE == 'scan' and hasattr(job, 'energy_list') and len(job.energy_list) > 0:
                    headers = ["Point"]
                    for i in range(job.dim):
                        idx_str = ",".join(map(str, job.scan_atom_indices_list[i]))
                        p_name = f"{job.scan_type_list[i].capitalize()} ({idx_str})"
                        headers.append(p_name)
                    headers.extend(["Energy (Eh)", "Rel. Energy (kcal/mol)"])
                    from decimal import Decimal
                    e0 = job.energy_list[0]
                    eh_to_kcal = Decimal('627.509')
                    table_data = []
                    for i in range(len(job.energy_list)):
                        row = [i+1]
                        if i < len(job.parameters_list):
                            params = job.parameters_list[i]
                            for p in params:
                                row.append(str(p))
                        else:
                            for _ in range(job.dim):
                                row.append("")
                        e = job.energy_list[i]
                        rel_e = (e - e0) * eh_to_kcal
                        row.append(str(e))
                        row.append(f"{rel_e:.2f}")
                        table_data.append(row)
                    self.data_panel.show_table(headers, table_data)
                    rel_energies = [float((e - e0) * eh_to_kcal) for e in job.energy_list]
                    if getattr(job, 'dim', 0) == 1:
                        self.data_panel.plot_btn.show()
                        if len(job.parameters_list) == len(job.energy_list):
                            x_vals = [float(p[0]) for p in job.parameters_list]
                        else:
                            x_vals = list(range(1, len(job.energy_list) + 1))
                        self.plot_widget.plot_energy(rel_energies, x_vals=x_vals, title="Scan Path Energy", xlabel=headers[1], ylabel="Relative Energy (kcal/mol)")
                    elif getattr(job, 'dim', 0) == 2:
                        self.data_panel.plot_btn.show()
                        if len(job.parameters_list) == len(job.energy_list):
                            x_vals = [float(p[0]) for p in job.parameters_list]
                            y_vals = [float(p[1]) for p in job.parameters_list]
                            self.plot_widget.plot_2d_scan(x_vals, y_vals, rel_energies, title="2D Scan Energy Surface", xlabel=headers[1], ylabel=headers[2], zlabel="Relative Energy (kcal/mol)")
                
                elif job.JOB_TYPE == 'irc' and hasattr(job, 'energy_list') and len(job.energy_list) > 0:
                    self.data_panel.plot_btn.show()
                    headers = ["Point", "Energy (Eh)", "Rel. Energy (kcal/mol)"]
                    from decimal import Decimal
                    e_ts = max(job.energy_list)
                    eh_to_kcal = Decimal('627.509')
                    table_data = []
                    for i, e in enumerate(job.energy_list):
                        rel_e = (e - e_ts) * eh_to_kcal
                        table_data.append([i+1, str(e), f"{rel_e:.2f}"])
                    self.data_panel.show_table(headers, table_data)
                    rel_energies = [float((e - e_ts) * eh_to_kcal) for e in job.energy_list]
                    self.plot_widget.plot_energy(rel_energies, title="IRC Path Energy", xlabel="Point", ylabel="Relative Energy to TS (kcal/mol)")
                
        self.data_panel.update_tabs_visibility()

    def on_table_selection_changed(self):
        if not self.data_panel.current_freq_job:
            return
        selected_items = self.data_panel.table_widget.selectedItems()
        if not selected_items:
            return
        # Row index gives the mode
        row = selected_items[0].row()
        job = self.data_panel.current_freq_job
        if isinstance(job, ORCAFreq) and row < len(job.freq_matrix_list):
            self.viewer_3d.animate_mode(job, row)
