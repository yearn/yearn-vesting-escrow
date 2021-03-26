import brownie
import pytest


@pytest.fixture(scope="module", autouse=True)
def initial_funding(token, vesting_factory, admin):
    token._mint_for_testing(10 ** 21, {"from": admin})
    token.approve(vesting_factory, 10 ** 21, {"from": admin})


def test_approve_fail(accounts, vesting_factory, token):
    with brownie.reverts("dev: funding failed"):
        vesting_factory.deploy_vesting_contract(
            token,
            accounts[2],
            10 ** 22,
            86400 * 365,
            {"from": accounts[0]},
        )


def test_target_is_set(vesting_factory, vesting_target):
    assert vesting_factory.target() == vesting_target


def test_admin_is_set(vesting_factory, admin):
    assert vesting_factory.admin() == admin


def test_balance_of(accounts, vesting_factory):
    assert vesting_factory.balanceOf(accounts[1]) == 0


def test_not_admin_fails_to_deploy(accounts, vesting_factory, alice, token):
    with brownie.reverts():
        vesting_factory.deploy_vesting_contract(
            token, accounts[1], 10 ** 18, 86400 * 365, {"from": alice}
        )


def test_deploys(accounts, vesting_factory, admin, token, chain):
    # deploy escrow 1
    tx = vesting_factory.deploy_vesting_contract(
        token, accounts[1], 10 ** 18, 86400 * 365, {"from": admin}
    )

    assert len(tx.new_contracts) == 1
    assert tx.return_value == tx.new_contracts[0]
    chain.mine(timestamp=chain.time() + 86400 * 365)

    # deploy escrow 2
    tx = vesting_factory.deploy_vesting_contract(
        token, accounts[1], 10 ** 18, 86400 * 365, {"from": admin}
    )
    assert len(tx.new_contracts) == 1
    assert tx.return_value == tx.new_contracts[0]
    chain.mine(timestamp=chain.time() + 86400 * 365)

    assert vesting_factory.balanceOf(accounts[1]) == 10 ** 18 * 2


def test_start_and_duration(
    VestingEscrowSimple, accounts, chain, vesting_factory, token
):
    start_time = chain.time() + 100

    tx = vesting_factory.deploy_vesting_contract(
        token,
        accounts[1],
        10 ** 18,
        86400 * 700,
        start_time,
        {"from": accounts[0]},
    )

    assert len(tx.new_contracts) == 1
    assert tx.return_value == tx.new_contracts[0]

    escrow = VestingEscrowSimple.at(tx.return_value)
    assert escrow.start_time() == start_time
    assert escrow.end_time() == start_time + 86400 * 700


def test_token_xfer(vesting, token):
    # exactly 10**18 tokens should be transferred
    assert token.balanceOf(vesting) == 10 ** 20


def test_token_approval(vesting, vesting_factory, token):
    # remaining approval should be zero
    assert token.allowance(vesting, vesting_factory) == 0


def test_init_vars(vesting, accounts, token, start_time, end_time):
    assert vesting.token() == token
    assert vesting.admin() == accounts[0]
    assert vesting.recipient() == accounts[1]
    assert vesting.start_time() == start_time
    assert vesting.end_time() == end_time
    assert vesting.total_locked() == 10 ** 20


def test_cannot_call_init(vesting, accounts, token, start_time, end_time):
    with brownie.reverts():
        vesting.initialize(
            accounts[0],
            token,
            accounts[1],
            10 ** 20,
            start_time,
            end_time,
            0,
            {"from": accounts[0]},
        )


def test_cannot_init_factory_target(
    vesting_target, accounts, token, start_time, end_time
):
    with brownie.reverts("dev: can only initialize once"):
        vesting_target.initialize(
            accounts[0],
            token,
            accounts[1],
            10 ** 20,
            start_time,
            end_time,
            0,
            {"from": accounts[0]},
        )
