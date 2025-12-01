"""
Visualisation Interactive pour Distillation Multicomposants
=============================================================
Graphiques interactifs et statiques pour bilans matière, compositions et température.

Auteur: Prof. BAKHER Zine Elabidine
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrow, Rectangle

# Import Plotly si disponible
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

class DistillationVisualizer:
    """
    Visualisation des résultats de distillation :
    bilans, profils et schéma de colonne
    """

    def _init_(self, compound_names):
        """Initialisation : noms des composés et couleurs"""
        self.compound_names = compound_names
        self.n_comp = len(compound_names)
        self.colors = plt.cm.Set3(np.linspace(0, 1, self.n_comp))
        if PLOTLY_AVAILABLE:
            self.plotly_colors = px.colors.qualitative.Set3[:self.n_comp]
    
    def plot_material_balance(self, F, D, B, z_F, x_D, x_B, save_path='bilan_matiere.png'):
        """Graphiques barres : débits et compositions"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        fig.suptitle('Bilans Matieres', fontsize=14, fontweight='bold')

        # Débits
        streams = ['Alimentation', 'Distillat', 'Residu']
        flows = [F, D, B]
        colors_streams = ['blue', 'green', 'red']
        bars = ax1.bar(streams, flows, color=colors_streams, alpha=0.7, edgecolor='black', linewidth=2)
        for bar, flow in zip(bars, flows):
            ax1.text(bar.get_x() + bar.get_width()/2., bar.get_height(), f'{flow:.1f}\nkmol/h',
                     ha='center', va='bottom', fontweight='bold', fontsize=10)
        ax1.set_ylabel('Debit (kmol/h)')
        ax1.set_title('Débits')
        ax1.grid(True, alpha=0.3, axis='y')
        ax1.set_ylim([0, max(flows) * 1.2])

        # Compositions
        x = np.arange(self.n_comp)
        width = 0.25
        ax2.bar(x - width, z_F, width, label='Alimentation', color='blue', alpha=0.7, edgecolor='black')
        ax2.bar(x, x_D, width, label='Distillat', color='green', alpha=0.7, edgecolor='black')
        ax2.bar(x + width, x_B, width, label='Residu', color='red', alpha=0.7, edgecolor='black')
        ax2.set_xticks(x)
        ax2.set_xticklabels(self.compound_names, rotation=15, ha='right')
        ax2.set_ylabel('Fraction molaire')
        ax2.set_title('Compositions')
        ax2.legend()
        ax2.grid(True, alpha=0.3, axis='y')
        ax2.set_ylim([0, 1.0])

        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"[OK] Graphique sauvegardé : {save_path}")
        plt.close()

    def plot_shortcut_results(self, results, save_path='shortcut_results.png'):
        """Visualisation simplifiée : Fenske, Underwood, Gilliland, Kirkbride"""
        fig = plt.figure(figsize=(16, 10))
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
        fig.suptitle('Résultats simplifiés', fontsize=16, fontweight='bold')

        ax1 = fig.add_subplot(gs[:, 0])
        self._draw_column_schematic(ax1, results)  # Schéma colonne

        # Fenske
        ax2 = fig.add_subplot(gs[0, 1])
        ax2.text(0.5, 0.6, f"N_min = {results['N_min']:.2f}", ha='center', va='center', fontsize=20, fontweight='bold', transform=ax2.transAxes)
        ax2.axis('off')

        # Underwood
        ax3 = fig.add_subplot(gs[0, 2])
        ax3.text(0.5, 0.6, f"R_min = {results['R_min']:.3f}", ha='center', va='center', fontsize=20, fontweight='bold', transform=ax3.transAxes)
        ax3.axis('off')

        # Gilliland
        ax4 = fig.add_subplot(gs[1, 1])
        ax4.plot([results['R_min'], results['R']], [results['N_min'], results['N_theoretical']], 'b-')
        ax4.set_xlabel('R')
        ax4.set_ylabel('N')
        ax4.grid(True, alpha=0.3)

        # Kirkbride
        ax5 = fig.add_subplot(gs[1, 2])
        ax5.barh(range(1, results['N_real']+1), [1]*results['N_real'])
        ax5.set_title('Plateau alimentation')
        ax5.invert_yaxis()

        # Tableau résumé
        ax6 = fig.add_subplot(gs[2, 1:])
        ax6.axis('off')
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"[OK] Graphique sauvegardé : {save_path}")
        plt.close()

    def _draw_column_schematic(self, ax, results):
        """Schéma simple de la colonne avec condenseur, rebouilleur et flux"""
        ax.set_xlim([0, 1])
        ax.set_ylim([0, 1])
        ax.axis('off')
        col = FancyBboxPatch((0.375, 0.15), 0.25, 0.65, boxstyle="round,pad=0.01", edgecolor='black', facecolor='lightblue', linewidth=2.5)
        ax.add_patch(col)

    def plot_composition_profiles_matplotlib(self, stages, x_profiles, y_profiles, feed_stage, save_path='composition_profiles.png'):
        """Profils de composition statiques (liquide et vapeur)"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 8))
        for i in range(self.n_comp):
            ax1.plot(x_profiles[:, i], stages, 'o-', label=self.compound_names[i], color=self.colors[i])
            ax2.plot(y_profiles[:, i], stages, 's-', label=self.compound_names[i], color=self.colors[i])
        ax1.axhline(feed_stage, color='blue', linestyle='--')
        ax2.axhline(feed_stage, color='blue', linestyle='--')
        ax1.invert_yaxis(); ax2.invert_yaxis()
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()

    def plot_temperature_profile(self, stages, temperatures, feed_stage, save_path='temperature_profile.png'):
        """Profil de température avec plateau alimentation"""
        fig, ax = plt.subplots(figsize=(8, 10))
        ax.plot(temperatures-273.15, stages, 'o-', color='orangered')
        ax.axhline(feed_stage, color='blue', linestyle='--')
        ax.invert_yaxis()
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()

def print_design_summary(shortcut_results, compound_names):
    """Affiche un résumé texte du dimensionnement"""
    print("\nRESUME DE LA COLONNE".center(80))
    print(f"Débit Alim: {shortcut_results['D']+shortcut_results['B']:.2f} kmol/h")
    print(f"Débit Distillat: {shortcut_results['D']:.2f} kmol/h")
    print(f"Débit Résidu: {shortcut_results['B']:.2f} kmol/h")
    print("Compositions Distillat / Résidu")
    for i, name in enumerate(compound_names):
        print(f"{name}: D {shortcut_results['x_D'][i]*100:.2f}%, B {shortcut_results['x_B'][i]*100:.2f}%")
    print(f"N_min: {shortcut_results['N_min']:.2f}, R_min: {shortcut_results['R_min']:.3f}, N_théo: {shortcut_results['N_theoretical']:.2f}")
