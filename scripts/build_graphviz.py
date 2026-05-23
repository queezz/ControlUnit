#!/usr/bin/env python3
"""Build Graphviz SVG diagrams for MkDocs documentation."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GRAPHVIZ_DIR = REPO_ROOT / "docs" / "assets" / "graphviz"

DIAGRAMS = [
    ("runtime_architecture.dot", "runtime_architecture.svg"),
]


def find_dot() -> str:
    dot = shutil.which("dot")
    if dot is None:
        sys.exit(
            "Graphviz 'dot' not found on PATH.\n"
            "Install Graphviz, then rerun:\n"
            "  macOS:   brew install graphviz\n"
            "  Ubuntu:  sudo apt install graphviz\n"
            "  Windows: choco install graphviz\n"
        )
    return dot


def build_diagram(dot_bin: str, dot_file: Path, svg_file: Path) -> None:
    result = subprocess.run(
        [dot_bin, "-Tsvg", str(dot_file), "-o", str(svg_file)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr or result.stdout, file=sys.stderr)
        sys.exit(result.returncode)
    print(f"Wrote {svg_file.relative_to(REPO_ROOT)}")


def main() -> None:
    dot_bin = find_dot()
    GRAPHVIZ_DIR.mkdir(parents=True, exist_ok=True)

    for dot_name, svg_name in DIAGRAMS:
        dot_file = GRAPHVIZ_DIR / dot_name
        svg_file = GRAPHVIZ_DIR / svg_name
        if not dot_file.is_file():
            print(f"Missing source: {dot_file}", file=sys.stderr)
            sys.exit(1)
        build_diagram(dot_bin, dot_file, svg_file)


if __name__ == "__main__":
    main()
