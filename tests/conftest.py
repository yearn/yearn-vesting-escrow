import boa
import pytest

from tests.helpers import Chain, at, deploy

YEAR = int(365.25 * 24 * 60 * 60)


@pytest.fixture(scope="session")
def chain():
    return Chain()


@pytest.fixture(scope="session")
def accounts():
    return [boa.env.generate_address(f"account-{index}") for index in range(10)]


@pytest.fixture(scope="session")
def duration():
    return 3 * YEAR


@pytest.fixture(scope="session")
def owner(accounts):
    return accounts[0]


@pytest.fixture(scope="session")
def recipient(accounts):
    return accounts[1]


@pytest.fixture(scope="session")
def cold_storage(accounts):
    return accounts[2]


@pytest.fixture(scope="module")
def token(owner):
    return deploy("test/MockToken", sender=owner)


@pytest.fixture(scope="module")
def another_token(owner):
    return deploy("test/MockToken", sender=owner)


@pytest.fixture(scope="module")
def start_time(chain):
    return chain.pending_timestamp + YEAR


@pytest.fixture(scope="module")
def end_time(start_time, duration):
    return start_time + duration


@pytest.fixture(scope="module")
def cliff_duration(duration):
    return duration // 6


@pytest.fixture(scope="module")
def standard_target(owner):
    return deploy("VestingEscrowSimple", sender=owner)


@pytest.fixture(scope="module")
def erc4626_target(owner):
    return deploy("VestingEscrow4626", sender=owner)


@pytest.fixture(scope="module")
def vesting_factory(owner, standard_target, erc4626_target):
    return deploy(
        "VestingEscrowFactory",
        standard_target,
        erc4626_target,
        sender=owner,
    )


@pytest.fixture(scope="module")
def asset_token(owner):
    return deploy("test/MockToken", sender=owner)


@pytest.fixture(scope="module")
def vault(owner, asset_token):
    return deploy("test/MockERC4626", asset_token, sender=owner)


@pytest.fixture(scope="module")
def amount():
    return 100 * 10**18


@pytest.fixture(scope="module")
def another_amount():
    return 10 * 10**18


@pytest.fixture(scope="module")
def open_claim():
    return True


@pytest.fixture
def vesting(
    owner,
    recipient,
    vesting_factory,
    token,
    another_token,
    amount,
    another_amount,
    start_time,
    cliff_duration,
    open_claim,
    duration,
):
    token.mint(owner, amount, sender=owner)
    another_token.mint(owner, another_amount, sender=owner)

    token.approve(vesting_factory, amount, sender=owner)
    escrow = vesting_factory.deploy_vesting_contract(
        token,
        recipient,
        amount,
        duration,
        start_time,
        cliff_duration,
        open_claim,
        owner,
        sender=owner,
    )
    return at("VestingEscrowSimple", escrow)


@pytest.fixture
def yield_vesting(
    owner,
    recipient,
    vesting_factory,
    vault,
    amount,
    duration,
    start_time,
    cliff_duration,
    open_claim,
):
    vault.mint(owner, amount, sender=owner)
    vault.approve(vesting_factory, amount, sender=owner)
    escrow = vesting_factory.deploy_erc4626_vesting(
        vault,
        recipient,
        amount,
        duration,
        start_time,
        cliff_duration,
        open_claim,
        owner,
        owner,
        sender=owner,
    )
    return at("VestingEscrow4626", escrow)
