"""Tests du générateur : ils documentent les invariants utilisés par les semaines suivantes."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

import pytest

from shopfloorpilot.datagen import Dataset, generate
from shopfloorpilot.datagen import config as cfg
from shopfloorpilot.datagen.cli import main
from shopfloorpilot.datagen.generator import period_end, write_csv


@pytest.fixture(scope="module")
def ds() -> Dataset:
    return generate(seed=42)


def test_three_plants(ds: Dataset) -> None:
    assert {p.plant_id for p in ds.plants} == {"PLT-LYS", "PLT-VAL", "PLT-TLS"}


def test_deterministic(tmp_path: Path) -> None:
    """Même graine => fichiers identiques : base des tests d'idempotence de la semaine 2."""
    write_csv(generate(7), tmp_path / "a")
    write_csv(generate(7), tmp_path / "b")
    for f in (tmp_path / "a").iterdir():
        assert f.read_bytes() == (tmp_path / "b" / f.name).read_bytes()


def test_ids_are_unique(ds: Dataset) -> None:
    assert len({o.of_id for o in ds.production_orders}) == len(ds.production_orders)
    assert len({d.event_id for d in ds.downtimes}) == len(ds.downtimes)
    assert len({p.po_id for p in ds.purchase_orders}) == len(ds.purchase_orders)


def test_time_balance(ds: Dataset) -> None:
    """Cohérence du TRS : planifié = marche + arrêts, et bonnes <= totales <= capacité."""
    down_by_of: dict[str, int] = defaultdict(int)
    for d in ds.downtimes:
        down_by_of[d.of_id] += d.duration_min
    for o in ds.production_orders:
        assert o.downtime_min == down_by_of[o.of_id]
        assert o.run_time_min == o.planned_time_min - o.downtime_min
        assert 0 <= o.good_count <= o.total_count <= o.run_time_min * 60 / o.ideal_cycle_s


def test_other_causes_have_ground_truth(ds: Dataset) -> None:
    """Chaque arrêt « Autre » a sa vraie catégorie (jeu étiqueté de la semaine 9)."""
    others = {d.event_id for d in ds.downtimes if d.cause_category == cfg.OTHER_CATEGORY}
    labelled = {lab.event_id for lab in ds.downtime_labels}
    assert others == labelled
    assert 0.10 < len(others) / len(ds.downtimes) < 0.20


def _trs(ds: Dataset, plant_id: str, month: int) -> float:
    """TRS mensuel d'une usine = temps utile (pièces bonnes x cycle) / temps planifié."""
    rows = [
        o for o in ds.production_orders if o.plant_id == plant_id and o.prod_date.month == month
    ]
    good_time = sum(o.good_count * o.ideal_cycle_s / 60 for o in rows)
    return good_time / sum(o.planned_time_min for o in rows)


def test_lyon_trs_drops_in_march(ds: Dataset) -> None:
    """Le scénario de démo existe bien : la question de l'agent SQL a une réponse."""
    lyon_march = _trs(ds, "PLT-LYS", 3)
    assert lyon_march < _trs(ds, "PLT-LYS", 2) - 0.05
    assert lyon_march < _trs(ds, "PLT-VAL", 3) - 0.05


def test_open_purchase_orders_exist(ds: Dataset) -> None:
    statuses = {p.status for p in ds.purchase_orders}
    assert statuses == {"livree", "en_cours"}
    assert all((p.delivered_date is None) == (p.status == "en_cours") for p in ds.purchase_orders)


def test_cli_writes_csv(tmp_path: Path) -> None:
    assert main(["--out", str(tmp_path), "--seed", "1"]) == 0
    assert (tmp_path / "downtimes.csv").stat().st_size > 0


def test_period_end() -> None:
    """Fin de période correcte, y compris pour un mois de 28 jours et en fin d'année."""
    assert period_end(date(2026, 1, 1), 1) == date(2026, 1, 31)
    assert period_end(date(2026, 1, 1), 2) == date(2026, 2, 28)
    assert period_end(date(2026, 1, 1), 6) == date(2026, 6, 30)
    assert period_end(date(2026, 1, 1), 12) == date(2026, 12, 31)


def test_months_limits_the_period() -> None:
    """Avec months=1, toutes les données tombent en janvier."""
    ds = generate(seed=42, months=1)
    assert all(o.prod_date.month == 1 for o in ds.production_orders)
    assert all(p.order_date.month == 1 for p in ds.purchase_orders)
    assert 0 < len(ds.production_orders) < len(generate(seed=42).production_orders)


@pytest.mark.parametrize("months", [0, 13, -1])
def test_months_out_of_range(months: int) -> None:
    """Une valeur hors de 1..12 est refusée avec un message explicite."""
    with pytest.raises(ValueError, match="entre 1 et 12"):
        generate(seed=42, months=months)


def test_cli_rejects_bad_months(tmp_path: Path) -> None:
    """La CLI transforme l'erreur en message d'usage (code de sortie 2)."""
    with pytest.raises(SystemExit) as exc:
        main(["--out", str(tmp_path), "--months", "13"])
    assert exc.value.code == 2


def test_months_are_stable_prefixes() -> None:
    """Les données de janvier sont les mêmes qu'on génère 1 ou 2 mois (base de l'incrémental).

    Seules les commandes encore en cours au 31 janvier peuvent changer : elles ont été
    livrées entre-temps (changement d'état), tout le reste est identique.
    """
    jan, jan_feb = generate(seed=42, months=1), generate(seed=42, months=2)
    feb_orders = {o.of_id: o for o in jan_feb.production_orders}
    assert all(feb_orders[o.of_id] == o for o in jan.production_orders)

    feb_pos = {p.po_id: p for p in jan_feb.purchase_orders}
    for po in jan.purchase_orders:
        later = feb_pos[po.po_id]
        if po.status == "livree":
            assert later == po
        else:  # en cours au 31 janvier : mêmes attributs, seule la livraison peut avoir évolué
            assert (later.supplier_id, later.promised_date) == (po.supplier_id, po.promised_date)
