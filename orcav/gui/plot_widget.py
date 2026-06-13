import matplotlib
matplotlib.use('QtAgg')
from PySide6.QtWidgets import QWidget, QVBoxLayout, QCheckBox
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

class PlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.toolbar_layout = QVBoxLayout()
        self.figure = Figure()
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        
        self.show_threshold_cb = QCheckBox("Show Thresholds (OPT only)")
        self.show_threshold_cb.setChecked(False)
        self.show_threshold_cb.toggled.connect(self.replot_current)

        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.show_threshold_cb)
        self.layout.addWidget(self.canvas)
        
        self.current_plot_type = None
        self.current_data = None

    def clear_plot(self):
        self.figure.clear()
        self.canvas.draw()
        self.current_plot_type = None
        self.current_data = None

    def replot_current(self):
        if self.current_plot_type == "energy":
            self.plot_energy(**self.current_data)
        elif self.current_plot_type == "opt":
            self.plot_opt_convergence(**self.current_data)
        elif self.current_plot_type == "2d_scan":
            self.plot_2d_scan(**self.current_data)
        elif self.current_plot_type == "neb_history":
            self.plot_neb_history(**self.current_data)

    def plot_energy(self, energies, x_vals=None, title="Energy Profile", xlabel="Step", ylabel="Energy (Eh)"):
        self.current_plot_type = "energy"
        self.current_data = {"energies": energies, "x_vals": x_vals, "title": title, "xlabel": xlabel, "ylabel": ylabel}
        
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        if x_vals is not None:
            ax.plot(x_vals, energies, marker='o', color='blue')
        else:
            ax.plot(energies, marker='o', color='blue')
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        self.figure.tight_layout()
        self.canvas.draw()

    def plot_2d_scan(self, x_vals, y_vals, z_vals, title="2D Scan Surface", xlabel="X", ylabel="Y", zlabel="Energy"):
        self.current_plot_type = "2d_scan"
        self.current_data = {"x_vals": x_vals, "y_vals": y_vals, "z_vals": z_vals, 
                             "title": title, "xlabel": xlabel, "ylabel": ylabel, "zlabel": zlabel}
        self.figure.clear()
        # Ensure we have 3D axes
        ax = self.figure.add_subplot(111, projection='3d')
        
        # We might have scatter data or we can triangulate it
        # Since it's a grid typically, plot_trisurf is very robust
        ax.plot_trisurf(x_vals, y_vals, z_vals, cmap='viridis', edgecolor='none')
        
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_zlabel(zlabel)
        
        self.figure.tight_layout()
        self.canvas.draw()

    def plot_neb_history(self, history_energies_list, title="NEB Optimization History", xlabel="Normalized Path Length", ylabel="Relative Energy (kcal/mol)"):
        self.current_plot_type = "neb_history"
        self.current_data = {"history_energies_list": history_energies_list, "title": title, "xlabel": xlabel, "ylabel": ylabel}
        
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        num_iters = len(history_energies_list)
        import matplotlib.cm as cm
        import numpy as np
        colors = cm.viridis(np.linspace(0.2, 1.0, num_iters))
        
        from decimal import Decimal
        eh_to_kcal = Decimal('627.509')
        
        for i, energies in enumerate(history_energies_list):
            if len(energies) > 0:
                e_react = energies[0]
                rel_energies = [float((e - e_react) * eh_to_kcal) for e in energies]
                label = f"Iter {i}" if i == 0 or i == num_iters - 1 else None
                lw = 2.0 if i == num_iters - 1 else 1.0
                
                # Normalize x-axis to 0.0 ~ 1.0
                x_vals = np.linspace(0.0, 1.0, len(energies))
                
                ax.plot(x_vals, rel_energies, marker='.', color=colors[i], label=label, alpha=0.7 if i < num_iters - 1 else 1.0, linewidth=lw)
                
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if num_iters > 1:
            ax.legend(loc='best')
        self.figure.tight_layout()
        self.canvas.draw()

    def plot_opt_convergence(self, energy_list, 
                             rms_grad, max_grad, rms_step, max_step,
                             rms_grad_thr, max_grad_thr, rms_step_thr, max_step_thr):
        self.current_plot_type = "opt"
        self.current_data = {
            "energy_list": energy_list, "rms_grad": rms_grad, "max_grad": max_grad,
            "rms_step": rms_step, "max_step": max_step,
            "rms_grad_thr": rms_grad_thr, "max_grad_thr": max_grad_thr,
            "rms_step_thr": rms_step_thr, "max_step_thr": max_step_thr
        }
        
        self.figure.clear()
        
        # 2 subplots: Top = Energy, Bottom = Convergence Gradients
        ax1 = self.figure.add_subplot(211)
        ax2 = self.figure.add_subplot(212)
        
        # Energy
        ax1.plot(energy_list, marker='o', color='blue', label='Energy')
        ax1.set_title("Optimization Convergence")
        ax1.set_ylabel("Energy (Eh)")
        ax1.grid(True, linestyle='--', alpha=0.6)
        
        # Gradients & Steps
        # we can use log scale for gradients/steps as they span orders of magnitude
        ax2.plot(rms_grad, marker='x', label='RMS grad')
        ax2.plot(max_grad, marker='x', label='MAX grad')
        ax2.plot(rms_step, marker='+', label='RMS step')
        ax2.plot(max_step, marker='+', label='MAX step')
        
        if self.show_threshold_cb.isChecked():
            if rms_grad_thr: ax2.plot(rms_grad_thr, linestyle='--', color='tab:blue', alpha=0.5)
            if max_grad_thr: ax2.plot(max_grad_thr, linestyle='--', color='tab:orange', alpha=0.5)
            if rms_step_thr: ax2.plot(rms_step_thr, linestyle='--', color='tab:green', alpha=0.5)
            if max_step_thr: ax2.plot(max_step_thr, linestyle='--', color='tab:red', alpha=0.5)
        
        ax2.set_yscale('log')
        ax2.set_xlabel("Step")
        ax2.set_ylabel("Value (log scale)")
        ax2.legend(loc='upper right', fontsize='small')
        ax2.grid(True, linestyle='--', alpha=0.6)
        
        self.figure.tight_layout()
        self.canvas.draw()
