"""Shared matplotlib style for manuscript figures (Times New Roman on Windows)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.axes import Axes
from matplotlib.figure import Figure

SAVE_DPI = 600
FIG_SIZE = (7.2, 5.4)

# Colorblind-safe, Q1-style palette (muted, print-friendly)
PALETTE = {
    "ink": "#1a1a1a",
    "primary": "#1B3A5C",       # deep navy — primary series
    "primary_light": "#4A6FA5",
    "secondary": "#C05621",     # burnt orange — accent
    "tertiary": "#2F6F64",      # teal-green
    "neutral": "#6B7280",
    "grid": "#D1D5DB",
    "fill": "#1B3A5C",
    "equality": "#9CA3AF",
    "repeat": "#1E4D6B",
    "single": "#D4DEE8",
    "highlight": "#B45309",
}


def _resolve_times_font() -> str:
    """Pick Times New Roman when installed (typical on Windows Word setups)."""
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in ("Times New Roman", "Times", "Nimbus Roman No9 L", "DejaVu Serif"):
        if name in available:
            return name
    return "serif"


def apply_publication_rc() -> str:
    """Apply journal-style rcParams; returns the font family actually selected."""
    family = _resolve_times_font()
    mpl.rcParams.update(
        {
            "figure.dpi": 120,
            "savefig.dpi": SAVE_DPI,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.12,
            "savefig.facecolor": "white",
            "savefig.edgecolor": "white",
            "font.family": family,
            "font.serif": [family, "Times New Roman", "Times", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "font.size": 11,
            "axes.titlesize": 11,
            "axes.labelsize": 12,
            "axes.titleweight": "normal",
            "axes.linewidth": 1.15,
            "axes.edgecolor": "#222222",
            "axes.labelcolor": "#111111",
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "xtick.major.width": 1.05,
            "ytick.major.width": 1.05,
            "xtick.major.size": 5,
            "ytick.major.size": 5,
            "xtick.color": "#111111",
            "ytick.color": "#111111",
            "legend.fontsize": 10,
            "legend.frameon": True,
            "legend.edgecolor": "#333333",
            "legend.fancybox": False,
            "legend.framealpha": 1.0,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    return family


def style_axes(ax: Axes, *, grid_axis: str = "y") -> None:
    """Minimal spines + light grid (Nature/Lancet-style)."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(1.0)
    ax.spines["bottom"].set_linewidth(1.0)
    ax.spines["left"].set_color(PALETTE["ink"])
    ax.spines["bottom"].set_color(PALETTE["ink"])
    if grid_axis == "y":
        ax.yaxis.grid(True, linestyle="-", linewidth=0.55, color=PALETTE["grid"], alpha=0.9)
        ax.set_axisbelow(True)
    elif grid_axis == "both":
        ax.grid(True, linestyle="-", linewidth=0.45, color=PALETTE["grid"], alpha=0.85)
        ax.set_axisbelow(True)
    elif grid_axis == "x":
        ax.xaxis.grid(True, linestyle="-", linewidth=0.55, color=PALETTE["grid"], alpha=0.9)
        ax.set_axisbelow(True)


def new_panel(**kwargs: Any) -> tuple[Figure, Axes]:
    kw = {"figsize": FIG_SIZE, "facecolor": "white"}
    kw.update(kwargs)
    fig, ax = plt.subplots(**kw)
    return fig, ax


def save_figure(fig: Figure, path_stem: Path | str) -> None:
    path_stem = Path(path_stem)
    """Save PNG + PDF at publication resolution."""
    fig.savefig(
        f"{path_stem}.png",
        dpi=SAVE_DPI,
        facecolor="white",
        edgecolor="none",
        bbox_inches="tight",
        pad_inches=0.12,
    )
    fig.savefig(
        f"{path_stem}.pdf",
        facecolor="white",
        edgecolor="none",
        bbox_inches="tight",
        pad_inches=0.12,
    )
    plt.close(fig)

