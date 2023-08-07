import ape
from ape.utils import ZERO_ADDRESS


def test_rug_pull_admin_only(vesting, receiver):
    with ape.reverts("dev: admin only"):
        vesting.rug_pull(sender=receiver)


def test_disabled_at_is_initially_end_time(vesting):
    assert vesting.disabled_at() == vesting.end_time()


def test_rug_pull(vesting, ychad):
    tx = vesting.rug_pull(sender=ychad)

    assert vesting.disabled_at() == tx.timestamp


def test_rug_pull_after_end_time(
    chain, vesting, ychad, receiver, token, amount, end_time
):
    balance_ychad = token.balanceOf(ychad)
    chain.pending_timestamp = end_time

    vesting.rug_pull(sender=ychad)
    vesting.claim(sender=receiver)

    assert token.balanceOf(receiver) == amount
    assert token.balanceOf(ychad) == balance_ychad


def test_rug_pull_before_start_time(chain, vesting, ychad, receiver, token, end_time):
    balance_ychad = token.balanceOf(ychad)
    vesting.rug_pull(sender=ychad)
    chain.pending_timestamp = end_time
    vesting.claim(sender=receiver)

    assert token.balanceOf(receiver) == 0
    assert token.balanceOf(ychad) == balance_ychad + vesting.total_locked()


def test_rug_pull_partially_ununclaimed(
    chain, vesting, ychad, receiver, token, amount, start_time, end_time, cliff_duration
):
    balance_ychad = token.balanceOf(ychad)
    chain.pending_timestamp = start_time + 2 * cliff_duration
    tx = vesting.rug_pull(sender=ychad)
    chain.pending_timestamp = end_time

    assert token.balanceOf(vesting) == vesting.unclaimed()

    vesting.claim(sender=receiver)

    expected_amount = amount * (tx.timestamp - start_time) // (end_time - start_time)
    assert token.balanceOf(receiver) == expected_amount
    assert (
        token.balanceOf(ychad)
        == balance_ychad + vesting.total_locked() - expected_amount
    )


def test_rug_pull_for_cliff(
    chain, vesting, ychad, receiver, token, start_time, end_time, cliff_duration
):
    balance_ychad = token.balanceOf(ychad)
    chain.pending_timestamp = start_time + cliff_duration // 2
    vesting.rug_pull(sender=ychad)

    chain.pending_timestamp = end_time
    vesting.claim(sender=receiver)

    assert token.balanceOf(receiver) == 0
    assert token.balanceOf(ychad) == balance_ychad + vesting.total_locked()


def test_rug_pull_in_past(chain, vesting, ychad):
    ts = chain.pending_timestamp - 1
    with ape.reverts("dev: no back to the future"):
        vesting.rug_pull(ts, sender=ychad)


def test_rug_pull_ts_balance(chain, vesting, ychad, receiver, token, start_time, end_time):
    ts = start_time + (end_time - start_time) // 2
    vesting.rug_pull(ts, sender=ychad)

    chain.pending_timestamp = ts
    vesting.claim(sender=receiver)

    assert token.balanceOf(vesting) == 0


def test_rug_pull_renounce_admin(vesting, ychad, start_time, end_time):
    ts = start_time + (end_time - start_time) // 2
    vesting.rug_pull(ts, sender=ychad)

    assert vesting.admin() == ZERO_ADDRESS


def test_rug_pull_after_end_time(vesting, ychad, end_time):
    ts = end_time + 1
    with ape.reverts("dev: no back to the future"):
        vesting.rug_pull(ts, sender=ychad)
