from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt
from orcav.core.result import ORCAResult
from orcav.core.base import ORCAJob

class ResultTreeModel(QStandardItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHorizontalHeaderLabels(['Job / Step'])

    def add_result(self, result: ORCAResult):
        root_item = QStandardItem(result.log_file.as_posix())
        root_item.setData(result, Qt.ItemDataRole.UserRole)
        root_item.setEditable(False)
        self.appendRow(root_item)
        
        for job in result.job_data:
            self._add_job_node(root_item, job)

    def _add_job_node(self, parent_item: QStandardItem, job: ORCAJob) -> QStandardItem:
        label = f"{job.JOB_TYPE.upper()}: {job.name}"
        if job.JOB_TYPE == 'sp' and hasattr(job, 'energy') and job.energy is not None:
            label += f" ({job.energy} Eh)"
        elif job.JOB_TYPE == 'opt' and getattr(job, 'optimized_energy', None) is not None:
            label += f" (Final: {job.optimized_energy} Eh)"
            
        job_item = QStandardItem(label)
        job_item.setData(job, Qt.ItemDataRole.UserRole)
        job_item.setEditable(False)
        parent_item.appendRow(job_item)
        
        # Add specific sub nodes depending on job type
        if job.JOB_TYPE == 'opt' and getattr(job, 'structure_list', None):
            for i, _ in enumerate(job.structure_list):
                step_label = f"Step {i+1}"
                if hasattr(job, 'energy_list') and i < len(job.energy_list):
                    step_label += f" ({job.energy_list[i]} Eh)"
                step_item = QStandardItem(step_label)
                step_item.setData({"job": job, "step": i}, Qt.ItemDataRole.UserRole)
                step_item.setEditable(False)
                job_item.appendRow(step_item)
                
                # Check if there is a frequency job for this step
                if getattr(job, 'freq_data_list', None) and i < len(job.freq_data_list):
                    freq = job.freq_data_list[i]
                    if freq is not None:
                        self._add_job_node(step_item, freq)
                
        elif job.JOB_TYPE == 'neb':
            if getattr(job, 'neb_path_structures_list', None) and len(job.neb_path_structures_list) > 0:
                final_path = job.neb_path_structures_list[0] # we saved as [structures]
                for i, _ in enumerate(final_path):
                    img_label = f"Image {i}"
                    if hasattr(job, 'neb_path_energies_list') and i < len(job.neb_path_energies_list[0]):
                        img_label += f" ({job.neb_path_energies_list[0][i]} Eh)"
                    img_item = QStandardItem(img_label)
                    img_item.setData({"job": job, "image": i}, Qt.ItemDataRole.UserRole)
                    img_item.setEditable(False)
                    job_item.appendRow(img_item)
                    
            if getattr(job, 'history_structures_list', None):
                history_root = QStandardItem("Optimization History")
                history_root.setData({"job": job, "history_root": True}, Qt.ItemDataRole.UserRole)
                history_root.setEditable(False)
                for iter_idx, iter_path in enumerate(job.history_structures_list):
                    iter_item = QStandardItem(f"Iteration {iter_idx}")
                    iter_item.setData({"job": job, "neb_iteration": iter_idx}, Qt.ItemDataRole.UserRole)
                    iter_item.setEditable(False)
                    
                    # Add images under iteration
                    iter_energies = job.history_energies_list[iter_idx] if hasattr(job, 'history_energies_list') and iter_idx < len(job.history_energies_list) else None
                    for img_idx, img_struct in enumerate(iter_path):
                        img_label = f"Image {img_idx}"
                        if iter_energies and img_idx < len(iter_energies):
                            img_label += f" ({iter_energies[img_idx]} Eh)"
                        img_item = QStandardItem(img_label)
                        img_item.setData({"job": job, "neb_iteration": iter_idx, "image": img_idx}, Qt.ItemDataRole.UserRole)
                        img_item.setEditable(False)
                        iter_item.appendRow(img_item)
                        
                    history_root.appendRow(iter_item)
                job_item.appendRow(history_root)
                    
        elif job.JOB_TYPE == 'irc' and getattr(job, 'structure_list', None):
            for i, _ in enumerate(job.structure_list):
                step_label = f"Point {i+1}" # Or i, but ORCA scan uses 1-based, irc could be 1-based or 0-based. Let's make it 1-based.
                if hasattr(job, 'energy_list') and i < len(job.energy_list):
                    step_label += f" ({job.energy_list[i]} Eh)"
                step_item = QStandardItem(step_label)
                step_item.setData({"job": job, "point": i}, Qt.ItemDataRole.UserRole)
                step_item.setEditable(False)
                job_item.appendRow(step_item)

        elif job.JOB_TYPE == 'scan' and getattr(job, 'structure_list', None):
            for i, _ in enumerate(job.structure_list):
                step_label = f"Point {i+1}"
                if hasattr(job, 'energy_list') and i < len(job.energy_list):
                    step_label += f" ({job.energy_list[i]} Eh)"
                step_item = QStandardItem(step_label)
                step_item.setData({"job": job, "point": i}, Qt.ItemDataRole.UserRole)
                step_item.setEditable(False)
                job_item.appendRow(step_item)
        
        # Recurse for sub_jobs
        for sub_job in job.sub_jobs:
            if job.JOB_TYPE == 'opt' and getattr(job, 'freq_data_list', None) and sub_job in job.freq_data_list:
                continue # Already added under step
            self._add_job_node(job_item, sub_job)
            
        return job_item
