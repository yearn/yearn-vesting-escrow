import ape
from ape.utils import ZERO_ADDRESS


def test_revoke_owner_only(vesting, recipient):
    with ape.reverts():  # "dev: owner only"):
        vesting.revoke(sender=recipient)


def test_disabled_at_is_initially_end_time(vesting):
    assert vesting.disabled_at() == vesting.end_time()


def test_revoke(vesting, owner):
    tx = vesting.revoke(sender=owner)
    assert vesting.disabled_at() == tx.timestamp


def test_revoke_before_start_time(chain, vesting, owner, recipient, token, end_time):
    balance_owner = token.balanceOf(owner)
    vesting.revoke(sender=owner)
    chain.pending_timestamp = end_time
    vesting.claim(sender=recipient)

    assert token.balanceOf(recipient) == 0
    assert token.balanceOf(owner) == balance_owner + vesting.total_locked()


def test_revoke_partially_ununclaimed(
    chain,
    vesting,
    owner,
    recipient,
    token,
    amount,
    start_time,
    end_time,
    cliff_duration,
):
    balance_owner = token.balanceOf(owner)
    chain.pending_timestamp = start_time + 2 * cliff_duration
    tx = vesting.revoke(sender=owner)
    chain.pending_timestamp = end_time

    assert token.balanceOf(vesting) == vesting.unclaimed()

    vesting.claim(sender=recipient)

    expected_amount = amount * (tx.timestamp - start_time) // (end_time - start_time)
    assert token.balanceOf(recipient) == expected_amount
    assert token.balanceOf(owner) == balance_owner + vesting.total_locked() - expected_amount


def test_revoke_for_cliff(
    chain,
    vesting,
    owner,
    recipient,
    token,
    start_time,
    end_time,
    cliff_duration,
):
    balance_owner = token.balanceOf(owner)
    chain.pending_timestamp = start_time + cliff_duration // 2
    vesting.revoke(sender=owner)

    chain.pending_timestamp = end_time
    vesting.claim(sender=recipient)

    assert token.balanceOf(recipient) == 0
    assert token.balanceOf(owner) == balance_owner + vesting.total_locked()


def test_revoke_in_past(chain, vesting, owner):
    ts = chain.pending_timestamp - 1
    with ape.reverts():  # "dev: no back to the future"):
        vesting.revoke(ts, sender=owner)


def test_revoke_at_end_time(vesting, owner, end_time):
    with ape.reverts():  # "dev: no back to the future"):
        vesting.revoke(end_time, sender=owner)


def test_revoke_ts_balance(chain, vesting, owner, recipient, token, start_time, end_time):
    ts = start_time + (end_time - start_time) // 2
    vesting.revoke(ts, sender=owner)

    chain.pending_timestamp = ts
    vesting.claim(sender=recipient)

    assert token.balanceOf(vesting) == 0


def test_revoke_renounce_owner(vesting, owner, start_time, end_time):
    ts = start_time + (end_time - start_time) // 2
    vesting.revoke(ts, sender=owner)

    assert vesting.owner() == ZERO_ADDRESS


def test_revoke_after_end_time(vesting, owner, end_time):
    ts = end_time + 1
    with ape.reverts():  # "dev: no back to the future"):
        vesting.revoke(ts, sender=owner)


def test_revoke_beneficiary():
    pass
