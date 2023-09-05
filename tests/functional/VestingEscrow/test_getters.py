def test_locked_unclaimed(chain, accounts, vesting, end_time):
    assert vesting.locked() == vesting.total_locked()
    assert vesting.unclaimed() == 0

    chain.pending_timestamp = end_time
    chain.mine()

    assert vesting.locked() == 0
    assert vesting.unclaimed() == vesting.total_locked()

    vesting.claim(sender=accounts[vesting.recipient()])
    assert vesting.unclaimed() == 0


def test_locked_revoke_dust(owner, vesting, token, amount, start_time, end_time):
    ts = start_time + (end_time - start_time) // 2
    vesting.revoke(ts, sender=owner)

    token.mint(owner, amount, sender=owner)
    token.transfer(vesting, amount, sender=owner)

    assert vesting.locked() == amount / 2
