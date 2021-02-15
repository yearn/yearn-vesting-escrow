import pytest
from brownie import ZERO_ADDRESS


def test_claim_full(vesting, token, accounts, chain, end_time):
    chain.sleep(end_time - chain.time())
    vesting.claim({"from": accounts[1]})

    assert token.balanceOf(accounts[1]) == 10 ** 20


def test_claim_less(vesting, token, accounts, chain, end_time):
    chain.sleep(end_time - chain.time())
    vesting.claim(vesting.total_locked() / 10, {"from": accounts[1]})

    assert token.balanceOf(accounts[1]) == 10 ** 19


def test_claim_beneficiary(vesting, token, accounts, chain, end_time):
    chain.sleep(end_time - chain.time())
    vesting.claim(2 ** 256 - 1, accounts[2], {"from": accounts[1]})

    assert token.balanceOf(accounts[2]) == 10 ** 20


def test_claim_before_start(vesting, token, accounts, chain, start_time):
    chain.sleep(start_time - chain.time() - 5)
    vesting.claim({"from": accounts[1]})

    assert token.balanceOf(accounts[1]) == 0


def test_claim_partial(vesting, token, accounts, chain, start_time, end_time):
    chain.sleep(vesting.start_time() - chain.time() + 31337)
    tx = vesting.claim({"from": accounts[1]})
    expected_amount = vesting.total_locked() * (tx.timestamp - start_time) // (end_time - start_time)

    assert token.balanceOf(accounts[1]) == expected_amount
    assert vesting.total_claimed() == expected_amount


def test_claim_multiple(vesting, token, accounts, chain, start_time, end_time):
    chain.sleep(start_time - chain.time() - 1000)
    balance = 0
    for i in range(11):
        chain.sleep((end_time - start_time) // 10)
        vesting.claim({"from": accounts[1]})
        new_balance = token.balanceOf(accounts[1])
        assert new_balance > balance
        balance = new_balance

    assert token.balanceOf(accounts[1]) == 10 ** 20
