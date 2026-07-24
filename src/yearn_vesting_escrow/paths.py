"""Resolve contract sources from an installed wheel or a source checkout."""

from importlib.resources import files
from pathlib import Path


def contracts_path():
    packaged = files("yearn_vesting_escrow").joinpath("contracts")
    if packaged.is_dir():
        return Path(str(packaged))

    checkout = Path(__file__).resolve().parents[2] / "contracts"
    if checkout.is_dir():
        return checkout

    raise FileNotFoundError("yearn-vesting-escrow contract sources are missing")
