from functools import lru_cache
from pathlib import Path
import warnings

import boa


ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"


@lru_cache
def contract_deployer(name):
    """Compile a contract once and reuse its deployer throughout the test run."""
    return boa.load_partial(CONTRACTS / f"{name}.vy")


def deploy(name, *args, sender):
    return contract_deployer(name).deploy(*args, sender=sender)


def at(name, address):
    # Minimal proxies deliberately have different runtime bytecode from their
    # implementations, so suppress Boa's bytecode-cast warning.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return contract_deployer(name).at(address)


def events(contract, event_name, *, include_child_logs=True):
    """Decode one event type from the contract's most recent computation."""
    return [
        log
        for log in contract.get_logs(include_child_logs=include_child_logs)
        if type(log).__name__ == event_name
    ]


class Chain:
    """Small absolute-timestamp adapter for the existing vesting test vectors."""

    @property
    def pending_timestamp(self):
        return boa.env.evm.patch.timestamp

    @pending_timestamp.setter
    def pending_timestamp(self, timestamp):
        delta = timestamp - self.pending_timestamp
        if delta < 0:
            raise ValueError("Titanoboa cannot travel backwards in time")
        if delta:
            boa.env.time_travel(seconds=delta)

    def mine(self):
        boa.env.time_travel(blocks=1)
