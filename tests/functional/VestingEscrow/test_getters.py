def test_locked_unclaimed(chain, vesting_factory, vesting, end_time):
    assert vesting.locked() == vesting.total_locked()
    assert vesting.unclaimed() == 0
    chain.sleep(end_time - chain.time())
    chain.mine()
    assert vesting_factory.balanceOf(vesting.recipient()) == vesting.total_locked()
    assert vesting.locked() == 0
    assert vesting.unclaimed() == vesting.total_locked()
    vesting.claim({"from": vesting.recipient()})
    assert vesting.unclaimed() == 0
