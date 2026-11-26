"""Point d'entrée : `uv run shopfloorpilot-datagen --out data --seed 42`."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from shopfloorpilot.datagen.generator import generate, write_csv


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Génère les données fictives ShopFloorPilot.")
    parser.add_argument("--out", type=Path, default=Path("data"), help="dossier de sortie")
    parser.add_argument("--seed", type=int, default=42, help="graine aléatoire")
    parser.add_argument(
        "--months", type=int, default=6, help="durée de la période en mois, de 1 à 12"
    )
    args = parser.parse_args(argv)

    try:
        dataset = generate(args.seed, args.months)
    except ValueError as exc:
        parser.error(str(exc))  # message clair + code de sortie 2, au lieu d'une trace Python
    counts = write_csv(dataset, args.out)
    for table, n in counts.items():
        print(f"{table:<20} {n:>8} lignes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
