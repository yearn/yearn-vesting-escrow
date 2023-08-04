import pytest
from ape.utils import ZERO_ADDRESS


def test_claim_full(chain, vesting, receiver, token, amount, end_time):
    chain.pending_timestamp = end_time
    vesting.claim(sender=receiver)

    assert token.balanceOf(vesting) == 0
    assert token.balanceOf(receiver) == amount


def test_claim_less(chain, vesting, receiver, token, amount, end_time):
    chain.pending_timestamp = end_time
    vesting.claim(receiver, vesting.total_locked() // 10, sender=receiver)

    assert token.balanceOf(receiver) == amount / 10


def test_claim_beneficiary(chain, vesting, receiver, cold_storage, token, amount, end_time):
    chain.pending_timestamp = end_time
    vesting.claim(cold_storage, sender=receiver)

    assert token.balanceOf(cold_storage) == amount


def test_claim_before_start(chain, vesting, receiver, token, start_time):
    chain.pending_timestamp = start_time - 5
    vesting.claim(sender=receiver)

    assert token.balanceOf(receiver) == 0


def test_claim_partial(
   chain, vesting, receiver, token, start_time, end_time, cliff_duration
):
    chain.pending_timestamp = start_time + 2 * cliff_duration
    tx = vesting.claim(sender=receiver)
    expected_amount = (
        vesting.total_locked() * (tx.timestamp - start_time) // (end_time - start_time)
    )

    assert token.balanceOf(receiver) == expected_amount
    assert vesting.total_claimed() == expected_amount


def test_claim_multiple(chain, vesting, receiver, token, amount, start_time, end_time):
    chain.pending_timestamp = start_time - 1000
    balance = 0
    for _ in range(11):
        chain.pending_timestamp += (end_time - start_time) // 10
        vesting.claim(sender=receiver)
        new_balance = token.balanceOf(receiver)
        assert new_balance > balance
        balance = new_balance

    assert token.balanceOf(receiver) == amount


def test_claim_cliff(
    chain, vesting, receiver, token, start_time, end_time, cliff_duration
):
    chain.pending_timestamp = start_time + int(cliff_duration / 2)
    vesting.claim(sender=receiver)
    assert token.balanceOf(receiver) == 0
    assert vesting.total_claimed() == 0

    chain.pending_timestamp = start_time + cliff_duration

    tx = vesting.claim(sender=receiver)
    expected_amount = (
        vesting.total_locked() * (tx.timestamp - start_time) // (end_time - start_time)
    )

    assert token.balanceOf(receiver) == expected_amount
    assert vesting.total_claimed() == expected_amount
