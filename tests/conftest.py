import pytest

WEEK = 7 * 24 * 60 * 60  # seconds
YEAR = 365.25 * 24 * 60 * 60  # seconds


@pytest.fixture(autouse=True)
def isolation_setup(fn_isolation):
    pass


@pytest.fixture(scope="session")
def admin(accounts):
    yield accounts[0]


@pytest.fixture(scope="session")
def alice(accounts):
    yield accounts[1]


@pytest.fixture(scope="session")
def bob(accounts):
    yield accounts[2]


@pytest.fixture(scope="session")
def charlie(accounts):
    yield accounts[3]


@pytest.fixture(scope="session")
def receiver(accounts):
    yield accounts.at("0x0000000000000000000000000000000000031337", True)


@pytest.fixture(scope="module")
def token(ERC20, accounts):
    yield ERC20.deploy("StakeWise", "SWISE", 18, {"from": accounts[0]})


@pytest.fixture(scope="module")
def start_time(chain):
    yield chain.time() + 1000 + 86400 * 365


@pytest.fixture(scope="module")
def end_time(start_time):
    yield int(start_time + 3 * YEAR)


@pytest.fixture(scope="module")
def vesting_target(VestingEscrowSimple, accounts):
    yield VestingEscrowSimple.deploy({"from": accounts[0]})


@pytest.fixture(scope="module")
def vesting_factory(VestingEscrowFactory, accounts, vesting_target, admin):
    yield VestingEscrowFactory.deploy(
        vesting_target,
        admin,
        {"from": accounts[0]}
    )


@pytest.fixture(scope="module")
def vesting(VestingEscrowSimple, accounts, vesting_factory, token, start_time):
    token._mint_for_testing(10 ** 20, {"from": accounts[0]})
    token.approve(vesting_factory, 10 ** 20, {"from": accounts[0]})
    tx = vesting_factory.deploy_vesting_contract(
        token,
        accounts[1],
        10 ** 20,
        3 * YEAR,  # duration
        start_time,
        0,  # cliff
        {"from": accounts[0]},
    )
    yield VestingEscrowSimple.at(tx.new_contracts[0])
