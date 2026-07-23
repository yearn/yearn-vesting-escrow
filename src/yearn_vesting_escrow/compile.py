"""Compile every contract with the version pinned by its source pragma."""

from pathlib import Path

import boa


CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


def pragma(path):
    for line in path.read_text().splitlines():
        if "version" in line and line.startswith("#"):
            return line.lstrip("# ")
    raise ValueError(f"No compiler version pragma in {path}")


def main():
    # Modules are compiled transitively by their importing deployable contracts.
    sources = sorted(path for path in CONTRACTS.rglob("*.vy") if "modules" not in path.parts)
    for source in sources:
        boa.load_partial(source)
        print(f"compiled {source.relative_to(CONTRACTS)} ({pragma(source)})")
    print(f"compiled {len(sources)} contracts")
