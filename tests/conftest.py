import ape
from ape.types import AddressType
import pytest

YEAR = int(365.25 * 24 * 60 * 60)


@pytest.fixture(scope="session")
def duration():
    yield 3 * YEAR


@pytest.fixture(scope="session")
def owner(accounts):
    return accounts[0]


@pytest.fixture(scope="session")
def recipient(accounts):
    yield accounts[1]


@pytest.fixture(scope="session")
def cold_storage(accounts):
    yield accounts[2]


@pytest.fixture(scope="module")
def token(project, owner):
    yield owner.deploy(project.MockToken)


@pytest.fixture(scope="module")
def another_token(project, owner):
    return owner.deploy(project.MockToken)


@pytest.fixture(scope="module")
def start_time(chain):
    yield chain.pending_timestamp + YEAR


@pytest.fixture(scope="module")
def end_time(start_time, duration):
    yield int(start_time + duration)


@pytest.fixture(scope="module")
def cliff_duration(duration):
    yield duration // 6


@pytest.fixture(scope="module")
def vesting_target(project, owner):
    yield owner.deploy(project.VestingEscrowSimple)


@pytest.fixture(scope="module")
def vyper_donation(accounts):
    # vyperlang.eth
    yield accounts[3]


@pytest.fixture(scope="module")
def vesting_factory(project, owner, vesting_target, vyper_donation):
    yield owner.deploy(project.VestingEscrowFactory, vesting_target, vyper_donation)


@pytest.fixture(scope="module")
def amount():
    yield 100 * 10**18


@pytest.fixture(scope="module")
def another_amount():
    yield 10 * 10**18


@pytest.fixture(scope="module")
def open_claim():
    yield True


@pytest.fixture(scope="module")
def support_vyper():
    yield 10


@pytest.fixture(scope="module")
def support_amount(amount, support_vyper):
    yield amount * support_vyper // 10_000


@pytest.fixture(scope="module")
def vesting(
    project,
    owner,
    recipient,
    vesting_factory,
    token,
    another_token,
    amount,
    support_amount,
    another_amount,
    start_time,
    cliff_duration,
    open_claim,
    duration,
    support_vyper,
):
    token.mint(owner, amount + support_amount, sender=owner)
    another_token.mint(owner, another_amount, sender=owner)

    token.approve(vesting_factory, amount + support_amount, sender=owner)
    receipt = vesting_factory.deploy_vesting_contract(
        token,
        recipient,
        amount,
        duration,
        start_time,
        cliff_duration,
        open_claim,
        support_vyper,
        sender=owner,
    )
    escrow = vesting_factory.VestingEscrowCreated.from_receipt(receipt)[0]
    yield project.VestingEscrowSimple.at(escrow.escrow)
