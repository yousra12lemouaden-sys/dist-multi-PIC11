"""
==============================================================
Distillation de Mélanges Multicomposants
Modélisation simplifiée et rigoureuse d’une colonne de distillation
==============================================================

Auteur  : Prof. BAKHER Zine Elabidine
Cours   : Modélisation et Simulation des Procédés - PIC
Université : UH1

Ce script regroupe :
  - Le calcul thermodynamique de base (K, Psat, enthalpies)
  - Le dimensionnement simplifié d’une colonne (Fenske, Underwood, Gilliland)
  - L’estimation de la composition du distillat / résidu

Les commentaires ci-dessous ont été reformulés pour plus de clarté.
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import fsolve, brentq, minimize
from scipy.linalg import solve_banded
from thermo.chemical import Chemical
from thermo import ChemicalConstantsPackage, PRMIX, CEOSLiquid, CEOSGas
import warnings
warnings.filterwarnings('ignore')

# ===============================================================
#  Modules optionnels pour graphiques interactifs (Plotly)
# ===============================================================
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    print("⚠ Plotly non installé : pip install plotly")
    print("  → Les visualisations interactives seront désactivées.")
class Compound:
    """
    Représente un composé chimique avec ses propriétés thermodynamiques.

    Les propriétés sont automatiquement récupérées depuis la base de
    données du module 'thermo' (Tc, Pc, Tb, Oméga, enthalpies, etc.)
    """

    def __init__(self, name):
        """Charge les données du composé à partir de la base thermo."""
        try:
            self.chem = Chemical(name)
            self.name = name

            # Extraction des propriétés principales
            self.Tc = self.chem.Tc       # Température critique
            self.Pc = self.chem.Pc       # Pression critique
            self.omega = self.chem.omega # Facteur acentrique
            self.Tb = self.chem.Tb       # Température d'ébullition normale
            self.MW = self.chem.MW       # Masse molaire
            self.Hfus = self.chem.Hfusm if self.chem.Hfusm else 0

        except Exception as e:
            raise ValueError(f"⚠ Impossible de charger le composé '{name}': {e}")

    def vapor_pressure(self, T):
        """Retourne la pression de vapeur saturante à la température T."""
        self.chem.T = T
        return self.chem.Psat if self.chem.Psat else 1e-10

    def K_value(self, T, P):
        """Coefficient d’équilibre vapeur-liquide : K = Psat(T) / P."""
        return self.vapor_pressure(T) / P

    def enthalpy_liquid(self, T, T_ref=298.15):
        """Enthalpie du liquide (approximation Cpl * ΔT)."""
        self.chem.T = T
        try:
            return self.chem.Cplm * (T - T_ref)
        except:
            # Valeur par défaut si les données manquent
            return 4.18 * self.MW * (T - T_ref)

    def enthalpy_vapor(self, T, T_ref=298.15):
        """Enthalpie de la vapeur = enthalpie liquide + chaleur latente."""
        self.chem.T = T
        Hvap = self.chem.Hvap if self.chem.Hvap else 40000
        return self.enthalpy_liquid(T, T_ref) + Hvap

    def __repr__(self):
        """Affichage lisible pour le débogage."""
        return f"Compound('{self.name}', Tb={self.Tb-273.15:.1f}°C, MW={self.MW:.2f})"


# ===============================================================
#  Classe ThermodynamicPackage
# ===============================================================
class ThermodynamicPackage:
    """
    Gère le paquet thermodynamique pour les calculs de distillation.
    Utilise les propriétés des composés pour calculer les équilibres vapeur-liquide.
    """

    def __init__(self, compounds, model='ideal'):
        """
        Initialise le paquet thermodynamique.
        
        Parameters:
        -----------
        compounds : dict
            Dictionnaire {nom: Compound}
        model : str
            Modèle thermodynamique ('ideal' ou 'raoult')
        """
        self.compounds = compounds
        self.model = model
        self.nc = len(compounds)

    def bubble_point(self, T, x, P_target=101325):
        """
        Calcule le point de bulle (température à laquelle le liquide commence à bouillir).
        
        Parameters:
        -----------
        T : float
            Température initiale (K)
        x : ndarray
            Fractions molaires en phase liquide
        P_target : float
            Pression cible (Pa)
        
        Returns:
        --------
        T_bubble : float
            Température de bulle (K)
        P_sat : float
            Pression de saturation (Pa)
        """
        def bubble_eq(T):
            K_values = np.array([self.compounds[name].K_value(T, P_target) 
                               for name in self.compounds])
            return np.sum(x * K_values) - 1.0
        
        try:
            T_bubble = brentq(bubble_eq, 250, 500)
            K_values = np.array([self.compounds[name].K_value(T_bubble, P_target) 
                               for name in self.compounds])
            P_sat = np.sum(x * np.array([self.compounds[name].vapor_pressure(T_bubble) 
                                        for name in self.compounds]))
            return T_bubble, P_sat
        except:
            return T, P_target

    def dew_point(self, T, y, P_target=101325):
        """
        Calcule le point de rosée (température à laquelle la vapeur commence à condenser).
        """
        def dew_eq(T):
            K_values = np.array([self.compounds[name].K_value(T, P_target) 
                               for name in self.compounds])
            return np.sum(y / K_values) - 1.0
        
        try:
            T_dew = brentq(dew_eq, 250, 500)
            return T_dew, P_target
        except:
            return T, P_target

    def flash_calculation(self, z, T, P):
        """
        Effectue un calcul de flash (VLE) pour trouver x, y et V/F.
        """
        # Initialisation
        K_values = np.array([self.compounds[name].K_value(T, P) for name in self.compounds])
        
        # Équation de Rachford-Rice
        def rachford_rice(V_F):
            return np.sum(z * (K_values - 1) / (1 + V_F * (K_values - 1)))
        
        try:
            if np.min(K_values) >= 1:
                V_F = 0  # Liquide
            elif np.max(K_values) <= 1:
                V_F = 1  # Vapeur
            else:
                V_F = brentq(rachford_rice, 0, 1)
        except:
            V_F = 0.5
        
        # Calcul des compositions
        x = z / (1 + V_F * (K_values - 1))
        x = x / np.sum(x)
        y = K_values * x
        y = y / np.sum(y)
        
        return x, y, V_F


# ===============================================================
#  Classe ShortcutDistillation
# ===============================================================
class ShortcutDistillation:
    """
    Modèle raccourci de distillation (Fenske-Underwood-Gilliland).
    Permet un dimensionnement rapide d'une colonne de distillation.
    """

    def __init__(self, thermo_package, reflux_ratio=None):
        """
        Initialise le modèle raccourci.
        
        Parameters:
        -----------
        thermo_package : ThermodynamicPackage
            Paquet thermodynamique
        reflux_ratio : float
            Ratio de reflux (L/D) - si None, calculé à partir de reflux minimum
        """
        self.thermo = thermo_package
        self.reflux_ratio = reflux_ratio
        self.compounds_dict = thermo_package.compounds

    def fenske_equation(self, x_d, x_b, T_d, T_b, P):
        """
        Calcule le nombre minimum de plateaux (Fenske).
        """
        # Calcul des K values aux conditions de distillat et résidu
        K_d = np.array([self.compounds_dict[name].K_value(T_d, P) for name in self.compounds_dict])
        K_b = np.array([self.compounds_dict[name].K_value(T_b, P) for name in self.compounds_dict])
        
        # Alpha relatifs
        alpha_avg = (K_d[0] / K_d[-1]) ** 0.5  # Approximation
        
        # Nombre minimum de plateaux
        x_d_key = np.max(x_d)
        x_b_key = np.min(x_b[x_b > 0])
        
        if x_d_key > 0 and x_b_key > 0:
            N_min = np.log((x_d_key / (1 - x_d_key)) * ((1 - x_b_key) / x_b_key)) / np.log(alpha_avg)
        else:
            N_min = 5
        
        return max(N_min, 1)

    def underwood_equation(self, composition, separation_factor=1.5):
        """
        Calcule le reflux minimum (Underwood).
        """
        # Approximation simplifiée du reflux minimum
        R_min = separation_factor / (separation_factor - 1)
        return R_min

    def gilliland_correlation(self, N_min, R_min, R):
        """
        Corrélation de Gilliland pour calculer le nombre réel de plateaux.
        """
        if R <= R_min:
            return N_min
        
        # Corrélation empirique
        X = (R - R_min) / (R + 1)
        Y = 1 - np.exp((1 - 54.4 * X) / (11 + 117.2 * X))
        N = N_min + Y / (1 - Y) * (N_min - 1)
        
        return max(N, N_min)

    def size_column(self, F, z, x_d, x_b, P=101325):
        """
        Dimensionne la colonne complète.
        """
        # Estimation des températures
        T_d, _ = self.thermo.bubble_point(350, x_d, P)
        T_b, _ = self.thermo.bubble_point(380, x_b, P)
        
        # Nombre minimum de plateaux
        N_min = self.fenske_equation(x_d, x_b, T_d, T_b, P)
        
        # Reflux minimum
        R_min = self.underwood_equation(z)
        
        # Reflux opératoire
        if self.reflux_ratio is None:
            self.reflux_ratio = 1.2 * R_min
        
        # Nombre réel de plateaux
        N = self.gilliland_correlation(N_min, R_min, self.reflux_ratio)
        
        return {
            'N_min': N_min,
            'R_min': R_min,
            'N': N,
            'T_d': T_d,
            'T_b': T_b
        }
