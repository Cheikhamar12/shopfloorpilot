"""Référentiel fictif : usines, machines, causes d'arrêt, fournisseurs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Plant:
    plant_id: str
    name: str
    city: str


@dataclass(frozen=True)
class MachineType:
    kind: str
    ideal_cycle_s: float  # temps de cycle théorique, en secondes par pièce
    products: tuple[str, ...]


@dataclass(frozen=True)
class Supplier:
    supplier_id: str
    name: str
    part: str
    reliability: float  # probabilité de livrer à l'heure en régime normal


PLANTS: tuple[Plant, ...] = (
    Plant("PLT-LYS", "Usine de Lyon", "Lyon"),
    Plant("PLT-VAL", "Usine de Valenciennes", "Valenciennes"),
    Plant("PLT-TLS", "Usine de Toulouse", "Toulouse"),
)

MACHINE_TYPES: tuple[MachineType, ...] = (
    MachineType("Presse", 12.0, ("Support moteur", "Renfort de portière")),
    MachineType("Injection", 30.0, ("Planche de bord", "Garniture de porte")),
    MachineType("Soudage", 20.0, ("Traverse", "Berceau")),
    MachineType("Assemblage", 45.0, ("Siège avant", "Module de porte")),
)
MACHINES_PER_TYPE = {"Presse": 3, "Injection": 2, "Soudage": 1, "Assemblage": 1}

# Catégorie -> (codes, part relative, durée moyenne en minutes, commentaires opérateur)
DOWNTIME_CATEGORIES: dict[str, tuple[tuple[str, ...], float, float, tuple[str, ...]]] = {
    "Panne mécanique": (
        ("E-214", "E-118", "E-302"),
        0.22,
        55.0,
        (
            "vérin bloqué, remplacement joint",
            "bruit anormal roulement, arrêt pour contrôle",
            "fuite hydraulique sur le vérin principal",
        ),
    ),
    "Panne électrique": (
        ("E-501", "E-517"),
        0.12,
        40.0,
        ("capteur de présence HS", "disjoncteur armoire déclenché", "défaut variateur"),
    ),
    "Changement de série": (
        ("C-100",),
        0.20,
        35.0,
        ("changement d'outil", "changement de moule", "passage à la référence suivante"),
    ),
    "Manque matière": (
        ("M-010",),
        0.14,
        45.0,
        ("plus de bobines acier", "attente palettes fournisseur", "rupture granulés"),
    ),
    "Qualité / réglage": (
        ("Q-020", "Q-021"),
        0.14,
        25.0,
        ("pièces hors tolérance, re-réglage", "bavures, ajustement pression", "contrôle 1re pièce"),
    ),
    "Maintenance préventive": (
        ("P-001",),
        0.10,
        60.0,
        ("graissage planifié", "changement filtres", "vérification annuelle"),
    ),
    "Manque personnel": (
        ("H-001",),
        0.08,
        30.0,
        ("opérateur absent, poste non remplacé", "réunion sécurité", "formation équipe"),
    ),
}
OTHER_CATEGORY = "Autre"
OTHER_CODE = "X-999"
# Probabilité qu'un opérateur saisisse « Autre » au lieu de la vraie cause
# (le cas d'usage du classifieur de la semaine 9).
OTHER_RATE = 0.15
# Commentaires plus vagues, typiques d'une saisie « Autre »
OTHER_COMMENTS: dict[str, tuple[str, ...]] = {
    "Panne mécanique": ("ça coince encore sur la presse", "machine qui force, on a arrêté"),
    "Panne électrique": ("plus de jus sur la ligne", "écran éteint d'un coup"),
    "Changement de série": ("on a changé de pièce", "outillage à monter"),
    "Manque matière": ("rien à mettre dans la machine", "camion pas arrivé"),
    "Qualité / réglage": ("pièces pas bonnes", "le chef qualité a bloqué"),
    "Maintenance préventive": ("la maintenance est passée", "entretien prévu"),
    "Manque personnel": ("personne au poste", "équipe incomplète"),
}

SUPPLIERS: tuple[Supplier, ...] = (
    Supplier("SUP-001", "Aciers du Rhône", "Bobine acier", 0.85),
    Supplier("SUP-002", "Polymères Nord", "Granulés PP", 0.78),
    Supplier("SUP-003", "Visserie Occitane", "Visserie", 0.92),
    Supplier("SUP-004", "Textiles Auto Est", "Tissu siège", 0.72),
    Supplier("SUP-005", "Électro Composants", "Faisceau électrique", 0.82),
    Supplier("SUP-006", "Mousses Industrielles", "Mousse PU", 0.75),
)

START_DATE = date(2026, 1, 1)
END_DATE = date(2026, 6, 30)
SHIFT_MINUTES = 480  # 1 équipe de 8 h par machine et par jour ouvré

# Scénario injecté : « Pourquoi le TRS de Lyon a baissé en mars ? »
# Aciers du Rhône livre Lyon en retard (mi-février -> mars), ce qui provoque des
# manques matière en mars ; la presse 3 de Lyon cumule en plus des pannes E-214.
SCENARIO_PLANT = "PLT-LYS"
SCENARIO_SUPPLIER = "SUP-001"
SCENARIO_LATE_WINDOW = (date(2026, 2, 15), date(2026, 3, 31))
SCENARIO_MONTH = 3
SCENARIO_MACHINE = "PLT-LYS-PRESSE-03"
