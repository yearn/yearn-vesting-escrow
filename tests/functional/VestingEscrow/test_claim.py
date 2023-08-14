import ape


def test_claim_full(chain, vesting, recipient, token, amount, end_time):
    chain.pending_timestamp = end_time
    vesting.claim(sender=recipient)

    assert token.balanceOf(vesting) == 0
    assert token.balanceOf(recipient) == amount


def test_claim_less(chain, vesting, recipient, token, amount, end_time):
    chain.pending_timestamp = end_time
    vesting.claim(recipient, vesting.total_locked() // 10, sender=recipient)

    assert token.balanceOf(recipient) == amount / 10


def test_claim_beneficiary(chain, vesting, recipient, cold_storage, token, amount, end_time):
    chain.pending_timestamp = end_time
    vesting.claim(cold_storage, sender=recipient)

    assert token.balanceOf(cold_storage) == amount


def test_claim_recepient_beneficiary(chain, vesting, owner, recipient, token, amount, end_time):
    chain.pending_timestamp = end_time
    vesting.claim(recipient, sender=owner)

    assert token.balanceOf(recipient) == amount


def test_claim_not_open(chain, vesting, owner, recipient, end_time):
    vesting.set_open_claim(False, sender=recipient)
    chain.pending_timestamp = end_time
    with ape.reverts():  # dev_message="dev: not authorized"):
        vesting.claim(recipient, sender=owner)


def test_claim_before_start(chain, vesting, recipient, token, start_time):
    chain.pending_timestamp = start_time - 5
    vesting.claim(sender=recipient)

    assert token.balanceOf(recipient) == 0


def test_claim_partial(chain, vesting, recipient, token, start_time, end_time, cliff_duration):
    chain.pending_timestamp = start_time + 2 * cliff_duration
    tx = vesting.claim(sender=recipient)
    expected_amount = vesting.total_locked() * (tx.timestamp - start_time) // (end_time - start_time)

    assert token.balanceOf(recipient) == expected_amount
    assert vesting.total_claimed() == expected_amount


def test_claim_multiple(
    chain,
    vesting,
    recipient,
    token,
    amount,
    start_time,
    end_time,
    cliff_duration,
):
    chain.pending_timestamp = start_time + cliff_duration
    balance = 0
    for _ in range(10):
        chain.pending_timestamp += (end_time - start_time - cliff_duration) // 10
        vesting.claim(sender=recipient)
        new_balance = token.balanceOf(recipient)
        assert new_balance > balance
        balance = new_balance

    assert token.balanceOf(recipient) == amount


def test_claim_cliff(chain, vesting, recipient, token, start_time, end_time, cliff_duration):
    chain.pending_timestamp = start_time + int(cliff_duration / 2)
    vesting.claim(sender=recipient)
    assert token.balanceOf(recipient) == 0
    assert vesting.total_claimed() == 0

    chain.pending_timestamp = start_time + cliff_duration

    tx = vesting.claim(sender=recipient)
    expected_amount = vesting.total_locked() * (tx.timestamp - start_time) // (end_time - start_time)

    assert token.balanceOf(recipient) == expected_amount
    assert vesting.total_claimed() == expected_amount
