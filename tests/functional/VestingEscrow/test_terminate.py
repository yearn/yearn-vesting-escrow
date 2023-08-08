import ape
from ape.utils import ZERO_ADDRESS


def test_terminate_admin_only(vesting, receiver):
    with ape.reverts(): # "dev: admin only"):
        vesting.terminate(sender=receiver)


def test_disabled_at_is_initially_end_time(vesting):
    assert vesting.disabled_at() == vesting.end_time()


def test_terminate(vesting, ychad):
    tx = vesting.terminate(sender=ychad)

    assert vesting.disabled_at() == tx.timestamp


def test_terminate_after_end_time(
    chain, vesting, ychad, receiver, token, amount, end_time
):
    balance_ychad = token.balanceOf(ychad)
    chain.pending_timestamp = end_time

    vesting.terminate(sender=ychad)
    vesting.claim(sender=receiver)

    assert token.balanceOf(receiver) == amount
    assert token.balanceOf(ychad) == balance_ychad


def test_terminate_before_start_time(chain, vesting, ychad, receiver, token, end_time):
    balance_ychad = token.balanceOf(ychad)
    vesting.terminate(sender=ychad)
    chain.pending_timestamp = end_time
    vesting.claim(sender=receiver)

    assert token.balanceOf(receiver) == 0
    assert token.balanceOf(ychad) == balance_ychad + vesting.total_locked()


def test_terminate_partially_ununclaimed(
    chain, vesting, ychad, receiver, token, amount, start_time, end_time, cliff_duration
):
    balance_ychad = token.balanceOf(ychad)
    chain.pending_timestamp = start_time + 2 * cliff_duration
    tx = vesting.terminate(sender=ychad)
    chain.pending_timestamp = end_time

    assert token.balanceOf(vesting) == vesting.unclaimed()

    vesting.claim(sender=receiver)

    expected_amount = amount * (tx.timestamp - start_time) // (end_time - start_time)
    assert token.balanceOf(receiver) == expected_amount
    assert (
        token.balanceOf(ychad)
        == balance_ychad + vesting.total_locked() - expected_amount
    )


def test_terminate_for_cliff(
    chain, vesting, ychad, receiver, token, start_time, end_time, cliff_duration
):
    balance_ychad = token.balanceOf(ychad)
    chain.pending_timestamp = start_time + cliff_duration // 2
    vesting.terminate(sender=ychad)

    chain.pending_timestamp = end_time
    vesting.claim(sender=receiver)

    assert token.balanceOf(receiver) == 0
    assert token.balanceOf(ychad) == balance_ychad + vesting.total_locked()


def test_terminate_in_past(chain, vesting, ychad):
    ts = chain.pending_timestamp - 1
    with ape.reverts(): # "dev: no back to the future"):
        vesting.terminate(ts, sender=ychad)


def test_terminate_at_end_time(vesting, ychad, end_time):
    with ape.reverts(): # "dev: no back to the future"):
        vesting.terminate(end_time, sender=ychad)


def test_terminate_ts_balance(chain, vesting, ychad, receiver, token, start_time, end_time):
    ts = start_time + (end_time - start_time) // 2
    vesting.terminate(ts, sender=ychad)

    chain.pending_timestamp = ts
    vesting.claim(sender=receiver)

    assert token.balanceOf(vesting) == 0


def test_terminate_renounce_admin(vesting, ychad, start_time, end_time):
    ts = start_time + (end_time - start_time) // 2
    vesting.terminate(ts, sender=ychad)

    assert vesting.admin() == ZERO_ADDRESS


def test_terminate_after_end_time(vesting, ychad, end_time):
    ts = end_time + 1
    with ape.reverts(): # "dev: no back to the future"):
        vesting.terminate(ts, sender=ychad)


def test_terminate_beneficiary():
    pass
