import brownie


def test_rug_pull_admin_only(vesting, accounts):
    with brownie.reverts("dev: admin only"):
        vesting.rug_pull({"from": accounts[1]})


def test_disabled_at_is_initially_end_time(vesting, accounts):
    assert vesting.disabled_at() == vesting.end_time()


def test_rug_pull(vesting, accounts):
    tx = vesting.rug_pull({"from": accounts[0]})

    assert vesting.disabled_at() == tx.timestamp


def test_rug_pull_after_end_time(vesting, token, accounts, chain, end_time):
    chain.sleep(end_time - chain.time())
    vesting.rug_pull({"from": accounts[0]})
    vesting.claim({"from": accounts[1]})

    assert token.balanceOf(accounts[1]) == 10 ** 20
    assert token.balanceOf(accounts[0]) == 0


def test_rug_pull_before_start_time(vesting, token, accounts, chain, end_time):
    vesting.rug_pull({"from": accounts[0]})
    chain.sleep(end_time - chain.time())
    vesting.claim({"from": accounts[1]})

    assert token.balanceOf(accounts[1]) == 0
    assert token.balanceOf(accounts[0]) == vesting.total_locked()


def test_rug_pull_partially_ununclaimed(
    vesting, token, accounts, chain, start_time, end_time, cliff_duration
):
    chain.sleep(start_time - chain.time() + 2 * cliff_duration)
    tx = vesting.rug_pull({"from": accounts[0]})
    chain.sleep(end_time - chain.time())
    vesting.claim({"from": accounts[1]})

    expected_amount = 10 ** 20 * (tx.timestamp - start_time) // (end_time - start_time)
    assert token.balanceOf(accounts[1]) == expected_amount
    assert token.balanceOf(accounts[0]) == vesting.total_locked() - expected_amount


def test_rug_pull_for_cliff(
    vesting, token, accounts, chain, start_time, end_time, cliff_duration
):
    chain.sleep(start_time - chain.time() + int(cliff_duration / 2))
    tx = vesting.rug_pull({"from": accounts[0]})
    chain.sleep(end_time - chain.time())
    vesting.claim({"from": accounts[1]})

    assert token.balanceOf(accounts[1]) == 0
    assert token.balanceOf(accounts[0]) == vesting.total_locked()

    chain.sleep(start_time - chain.time() + cliff_duration)
    vesting.claim({"from": accounts[1]})
    assert token.balanceOf(accounts[1]) == 0
