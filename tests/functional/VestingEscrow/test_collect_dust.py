import brownie
import pytest
from brownie import ZERO_ADDRESS


@pytest.fixture
def token2(ERC20, accounts):
    yield ERC20.deploy("XYZ", "XYZ", 18, {"from": accounts[0]})


def test_claim_non_vested_token(vesting, token, token2, accounts, chain, end_time):
    token2._mint_for_testing(10 ** 20, {"from": accounts[0]})
    token2.transfer(vesting, 10 ** 20)

    vesting.collect_dust(token2, {"from": accounts[1]})
    assert token2.balanceOf(accounts[1]) == 10 ** 20


def test_do_not_allow_claim_of_vested_token(
    vesting, token, token2, accounts, chain, end_time
):
    with brownie.reverts():
        vesting.collect_dust(token, {"from": accounts[1]})


def test_allow_vested_token_dust_to_be_claim_at_end(
    vesting, token, accounts, chain, end_time
):
    chain.sleep(end_time - chain.time())
    chain.mine()
    vesting.collect_dust(token, {"from": accounts[1]})
    assert token.balanceOf(accounts[1]) == 10 ** 20
