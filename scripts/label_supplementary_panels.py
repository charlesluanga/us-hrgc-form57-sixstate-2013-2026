"""Create FigureS1a_ / FigureS2a_ labeled panel copies for Word layout."""
from __future__ import annotations

from figure_paths import FIG_ROOT, label_supplementary_panels, sync_supplementary_aliases


def main() -> None:
    sync_supplementary_aliases(FIG_ROOT)
    counts = label_supplementary_panels(FIG_ROOT)
    print("Labeled panel copies:", counts)
    print(f"Figure S2 folder: {FIG_ROOT / 'Figure2_RF_global_structure'}")


if __name__ == "__main__":
    main()

