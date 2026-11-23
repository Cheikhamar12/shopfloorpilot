"""Génère un jeu de données industrielles déterministe pour ShopFloorPilot.

Tables produites : usines, machines, fournisseurs, ordres de fabrication (OF),
arrêts machine, vérité terrain des arrêts « Autre », commandes fournisseurs.

Rappel TRS (taux de rendement synthétique) :
    TRS = disponibilité x performance x qualité
        = (temps de marche / temps planifié)
          x (pièces totales x cycle théorique / temps de marche)
          x (pièces bonnes / pièces totales)
        = (pièces bonnes x cycle théorique) / temps planifié

Invariants garantis (vérifiés par tests/test_datagen.py) :
- temps de marche = temps planifié - somme des arrêts de l'OF ;
- pièces bonnes <= pièces totales <= capacité théorique ;
- même graine => mêmes fichiers, octet pour octet.
"""

from __future__ import annotations

import csv
import random
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from shopfloorpilot.datagen import config as cfg

# ---------------------------------------------------------------------------
# Modèle de données. Des dataclasses figées (frozen) : une ligne générée ne doit
# plus jamais être modifiée, ce qui évite des incohérences entre tables.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Machine:
    machine_id: str  # clé naturelle, ex. "PLT-LYS-PRESSE-03"
    plant_id: str
    kind: str
    ideal_cycle_s: float  # temps de cycle théorique (s/pièce), base du calcul de performance


@dataclass(frozen=True)
class ProductionOrder:
    """Un ordre de fabrication (OF) = une machine, une journée, un poste de 8 h."""

    of_id: str
    plant_id: str
    machine_id: str
    product: str
    prod_date: date
    planned_time_min: int  # temps d'ouverture planifié
    downtime_min: int  # somme des arrêts de l'OF (redondant, mais pratique pour contrôler)
    run_time_min: int  # temps de marche = planifié - arrêts
    ideal_cycle_s: float
    total_count: int  # pièces produites
    good_count: int  # pièces conformes


@dataclass(frozen=True)
class Downtime:
    """Un arrêt machine tel que saisi par l'opérateur (catégorie parfois « Autre »)."""

    event_id: str
    of_id: str  # rattachement à l'OF : permet de recalculer la disponibilité
    machine_id: str
    start_ts: datetime
    duration_min: int
    cause_code: str
    cause_category: str  # catégorie SAISIE, éventuellement « Autre »
    operator_comment: str  # texte libre : l'entrée du classifieur de la semaine 9


@dataclass(frozen=True)
class DowntimeLabel:
    """Vraie catégorie des arrêts saisis « Autre » (vérité terrain, semaine 9).

    Stockée dans une table séparée pour ne pas « fuiter » la réponse dans les
    données que verra le modèle.
    """

    event_id: str
    true_category: str


@dataclass(frozen=True)
class PurchaseOrder:
    po_id: str
    supplier_id: str
    plant_id: str
    part: str
    quantity: int
    order_date: date
    promised_date: date
    delivered_date: date | None  # None tant que la commande n'est pas livrée
    status: str  # "livree" | "en_cours"


@dataclass
class Dataset:
    """Conteneur de toutes les tables générées, en mémoire."""

    plants: list[cfg.Plant] = field(default_factory=list)
    machines: list[Machine] = field(default_factory=list)
    suppliers: list[cfg.Supplier] = field(default_factory=list)
    production_orders: list[ProductionOrder] = field(default_factory=list)
    downtimes: list[Downtime] = field(default_factory=list)
    downtime_labels: list[DowntimeLabel] = field(default_factory=list)
    purchase_orders: list[PurchaseOrder] = field(default_factory=list)

    def tables(self) -> dict[str, list[Any]]:
        """Associe un nom de table (= nom du fichier CSV) à ses lignes."""
        return {
            "plants": self.plants,
            "machines": self.machines,
            "suppliers": self.suppliers,
            "production_orders": self.production_orders,
            "downtimes": self.downtimes,
            "downtime_labels": self.downtime_labels,
            "purchase_orders": self.purchase_orders,
        }


# ---------------------------------------------------------------------------
# Référentiels
# ---------------------------------------------------------------------------


def _working_days(start: date, end: date) -> list[date]:
    """Jours ouvrés (lundi-vendredi) entre deux dates incluses. Pas de jours fériés."""
    days, d = [], start
    while d <= end:
        if d.weekday() < 5:  # 0 = lundi ... 4 = vendredi
            days.append(d)
        d += timedelta(days=1)
    return days


def _build_machines() -> list[Machine]:
    """Crée le parc machine : même composition dans chaque usine (7 machines par site)."""
    machines = []
    for plant in cfg.PLANTS:
        for mtype in cfg.MACHINE_TYPES:
            for i in range(1, cfg.MACHINES_PER_TYPE[mtype.kind] + 1):
                machine_id = f"{plant.plant_id}-{mtype.kind.upper()}-{i:02d}"
                machines.append(
                    Machine(machine_id, plant.plant_id, mtype.kind, mtype.ideal_cycle_s)
                )
    return machines


# ---------------------------------------------------------------------------
# Production et arrêts
# ---------------------------------------------------------------------------


def _material_shortage_boost(plant_id: str, day: date) -> float:
    """Multiplicateur de probabilité de « Manque matière ».

    x4 à Lyon en mars : c'est la conséquence, côté atelier, des retards
    d'Aciers du Rhône injectés dans les commandes fournisseurs.
    """
    if plant_id == cfg.SCENARIO_PLANT and day.month == cfg.SCENARIO_MONTH:
        return 4.0
    return 1.0


def _pick_category(rng: random.Random, plant_id: str, machine_id: str, day: date) -> str:
    """Tire la VRAIE catégorie d'un arrêt, selon les poids du référentiel.

    Les poids sont modifiés pendant le scénario de Lyon (manques matière,
    et pannes mécaniques x3 sur la presse 3).
    """
    names = list(cfg.DOWNTIME_CATEGORIES)
    weights = [cfg.DOWNTIME_CATEGORIES[n][1] for n in names]
    weights[names.index("Manque matière")] *= _material_shortage_boost(plant_id, day)
    if machine_id == cfg.SCENARIO_MACHINE and day.month == cfg.SCENARIO_MONTH:
        weights[names.index("Panne mécanique")] *= 3.0
    return rng.choices(names, weights=weights, k=1)[0]


def _generate_production(
    rng: random.Random, machines: list[Machine]
) -> tuple[list[ProductionOrder], list[Downtime], list[DowntimeLabel]]:
    """Génère les OF, leurs arrêts et la vérité terrain des arrêts « Autre ».

    Pour chaque machine et chaque jour ouvré :
    1. on tire un nombre d'arrêts, puis leur catégorie, leur durée et leur commentaire ;
    2. ~15 % des arrêts sont « mal saisis » en « Autre » (vraie catégorie conservée à part) ;
    3. on en déduit le temps de marche, puis les pièces produites et bonnes.
    Les arrêts sont générés AVANT les quantités : c'est ce qui garantit
    l'équilibre temps planifié = temps de marche + arrêts.
    """
    kinds = {m.kind: m for m in cfg.MACHINE_TYPES}
    orders: list[ProductionOrder] = []
    downtimes: list[Downtime] = []
    labels: list[DowntimeLabel] = []
    of_seq = ev_seq = 0  # compteurs => identifiants stables d'une exécution à l'autre

    for day in _working_days(cfg.START_DATE, cfg.END_DATE):
        for machine in machines:
            of_seq += 1
            of_id = f"OF-{of_seq:07d}"
            planned = cfg.SHIFT_MINUTES
            scenario = machine.plant_id == cfg.SCENARIO_PLANT and day.month == cfg.SCENARIO_MONTH
            # La plupart des postes ont 0 à 2 arrêts ; plus pendant le scénario de Lyon.
            n_events = rng.choices([0, 1, 2, 3, 4], weights=[25, 35, 22, 12, 6], k=1)[0]
            if scenario:
                n_events += rng.choice([0, 1, 1, 2])

            # Les arrêts s'enchaînent dans la journée à partir de 6 h + quelques minutes.
            cursor = datetime.combine(day, time(6, 0)) + timedelta(minutes=rng.randint(10, 60))
            budget = int(planned * 0.6)  # l'arrêt cumulé ne dépasse jamais 60 % du poste
            total_down = 0
            for _ in range(n_events):
                category = _pick_category(rng, machine.plant_id, machine.machine_id, day)
                codes, _, mean_min, comments = cfg.DOWNTIME_CATEGORIES[category]
                # Loi exponentielle : beaucoup d'arrêts courts, quelques arrêts longs
                # (proche de la réalité). Plancher de 5 min, plafond = budget restant.
                duration = max(5, round(rng.expovariate(1 / mean_min)))
                duration = min(duration, budget - total_down)
                if duration < 5:
                    break  # budget épuisé : plus d'arrêt ce jour-là
                ev_seq += 1
                event_id = f"EV-{ev_seq:07d}"
                code = rng.choice(codes)
                comment = rng.choice(comments)
                if machine.machine_id == cfg.SCENARIO_MACHINE and category == "Panne mécanique":
                    code = "E-214"  # le code panne du cas d'usage « technicien »
                # Mauvaise saisie : l'opérateur choisit « Autre » et écrit un commentaire vague.
                # La vraie catégorie va dans downtime_labels, pas dans downtimes.
                if rng.random() < cfg.OTHER_RATE:
                    labels.append(DowntimeLabel(event_id, category))
                    shown_category, code = cfg.OTHER_CATEGORY, cfg.OTHER_CODE
                    comment = rng.choice(cfg.OTHER_COMMENTS[category])
                else:
                    shown_category = category
                downtimes.append(
                    Downtime(
                        event_id,
                        of_id,
                        machine.machine_id,
                        cursor,
                        duration,
                        code,
                        shown_category,
                        comment,
                    )
                )
                total_down += duration
                cursor += timedelta(minutes=duration + rng.randint(15, 90))

            # Décomposition du TRS : disponibilité (ci-dessus), puis performance et qualité.
            run_time = planned - total_down
            performance = rng.uniform(0.82, 0.97)  # micro-arrêts, cadence réduite
            quality = rng.uniform(0.95, 0.995)  # part de pièces conformes
            if scenario:
                quality -= 0.02  # matière de remplacement => plus de rebuts
            capacity = int(run_time * 60 / machine.ideal_cycle_s)  # pièces max en marche
            total = int(capacity * performance)
            good = int(total * quality)
            product = rng.choice(kinds[machine.kind].products)
            orders.append(
                ProductionOrder(
                    of_id,
                    machine.plant_id,
                    machine.machine_id,
                    product,
                    day,
                    planned,
                    total_down,
                    run_time,
                    machine.ideal_cycle_s,
                    total,
                    good,
                )
            )
    return orders, downtimes, labels


# ---------------------------------------------------------------------------
# Supply chain
# ---------------------------------------------------------------------------


def _generate_purchase_orders(rng: random.Random) -> list[PurchaseOrder]:
    """Génère les commandes fournisseurs, avec retards et commandes encore ouvertes.

    - Chaque fournisseur livre à l'heure avec la probabilité `reliability`.
    - Scénario : Aciers du Rhône tombe à 25 % de fiabilité vers Lyon entre
      mi-février et fin mars (cause des manques matière de mars).
    - Une commande dont la livraison tomberait après la fin de la période est
      « en_cours » : ce sont celles que l'agent supply chain devra scorer.
    """
    pos: list[PurchaseOrder] = []
    seq = 0
    for day in _working_days(cfg.START_DATE, cfg.END_DATE):
        if day.weekday() not in (0, 3):  # commandes passées le lundi et le jeudi
            continue
        for plant in cfg.PLANTS:
            for supplier in cfg.SUPPLIERS:
                if rng.random() > 0.5:  # chaque fournisseur n'est pas sollicité à chaque fois
                    continue
                seq += 1
                lead = rng.randint(7, 21)  # délai promis, en jours
                promised = day + timedelta(days=lead)
                reliability = supplier.reliability
                win_start, win_end = cfg.SCENARIO_LATE_WINDOW
                if (
                    supplier.supplier_id == cfg.SCENARIO_SUPPLIER
                    and plant.plant_id == cfg.SCENARIO_PLANT
                    and win_start <= promised <= win_end
                ):
                    reliability = 0.25
                delay = 0 if rng.random() < reliability else rng.randint(1, 15)
                if rng.random() < 0.1:
                    delay = -rng.randint(1, 3)  # livraison en avance
                delivered: date | None = promised + timedelta(days=delay)
                status = "livree"
                if delivered is not None and delivered > cfg.END_DATE:
                    delivered, status = None, "en_cours"  # pas encore livrée à la date d'extraction
                pos.append(
                    PurchaseOrder(
                        f"PO-{seq:06d}",
                        supplier.supplier_id,
                        plant.plant_id,
                        supplier.part,
                        rng.randrange(100, 5000, 50),
                        day,
                        promised,
                        delivered,
                        status,
                    )
                )
    return pos


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------


def generate(seed: int = 42) -> Dataset:
    """Construit le jeu de données complet, en mémoire.

    Déterministe : un seul `random.Random(seed)` est partagé et les tables sont
    générées dans un ordre fixe. Ne jamais utiliser le module `random` global
    ni l'heure courante ici, sinon la reproductibilité est perdue.
    """
    rng = random.Random(seed)
    machines = _build_machines()
    orders, downtimes, labels = _generate_production(rng, machines)
    return Dataset(
        plants=list(cfg.PLANTS),
        machines=machines,
        suppliers=list(cfg.SUPPLIERS),
        production_orders=orders,
        downtimes=downtimes,
        downtime_labels=labels,
        purchase_orders=_generate_purchase_orders(rng),
    )


def _serialize(value: Any) -> str:
    """Convertit une valeur Python en texte CSV : ISO 8601 pour les dates, vide pour None."""
    if value is None:
        return ""
    if isinstance(value, datetime | date):
        return value.isoformat()
    return str(value)


def write_csv(dataset: Dataset, out_dir: Path) -> dict[str, int]:
    """Écrit une table par fichier CSV (UTF-8) et retourne le nombre de lignes par table.

    Les fichiers sont réécrits à chaque appel (écrasement complet) : relancer la
    génération ne crée jamais de doublons.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for name, rows in dataset.tables().items():
        records = [asdict(r) for r in rows]
        path = out_dir / f"{name}.csv"
        # newline="" : obligatoire avec le module csv pour éviter des lignes vides sous Windows.
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(records[0]))
            writer.writeheader()
            for rec in records:
                writer.writerow({k: _serialize(v) for k, v in rec.items()})
        counts[name] = len(records)
    return counts
