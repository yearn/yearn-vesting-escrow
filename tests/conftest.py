import ape
from ape_tokens import tokens
from ape.types import AddressType
import pytest

WEEK = 7 * 24 * 60 * 60  # seconds
YEAR = int(365.25 * 24 * 60 * 60)  # seconds


@pytest.fixture(scope="session")
def ychad(accounts):
    return accounts[ape.convert("ychad.eth", AddressType)]


@pytest.fixture(scope="session")
def ytrades(accounts):
    return accounts[ape.convert("ytrades.ychad.eth", AddressType)]


@pytest.fixture(scope="session")
def receiver(accounts):
    yield accounts["0x0000000000000000000000000000000000031337"]


@pytest.fixture(scope="session")
def cold_storage(accounts):
    yield accounts["0x000000000000000000000000000000000000C001"]


@pytest.fixture(scope="module")
def token():
    return tokens["YFI"]


@pytest.fixture(scope="module")
def another_token():
    return tokens["DAI"]


@pytest.fixture(scope="module")
def start_time(chain):
    yield chain.pending_timestamp + 1000 + 86400 * 365


@pytest.fixture(scope="module")
def end_time(start_time):
    yield int(start_time + 3 * YEAR)


@pytest.fixture(scope="module")
def cliff_duration():
    yield int(YEAR / 6)


@pytest.fixture(scope="module")
def vesting_target(project, ychad):
    yield ychad.deploy(project.VestingEscrowSimple)


@pytest.fixture(scope="module")
def vesting_factory(project, ychad, vesting_target):
    yield ychad.deploy(project.VestingEscrowFactory, vesting_target)


@pytest.fixture(scope="module")
def amount():
    yield ape.convert("100 YFI", int)


@pytest.fixture(scope="module")
def another_amount():
    yield ape.convert("10 DAI", int)


@pytest.fixture(scope="module")
def vesting(project, ychad, receiver, vesting_factory, token, amount, start_time, cliff_duration):
    token.approve(vesting_factory, amount, sender=ychad)
    receipt = vesting_factory.deploy_vesting_contract(
        token,
        receiver,
        amount,
        3 * YEAR,  # duration
        start_time,
        cliff_duration,
        sender=ychad,
    )
    escrow = vesting_factory.VestingEscrowCreated.from_receipt(receipt)[0]
    yield project.VestingEscrowSimple.at(escrow.escrow)
