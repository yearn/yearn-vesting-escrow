def test_claim_non_vested_token(vesting, owner, recipient, another_token, another_amount):
    another_token.transfer(vesting, another_amount, sender=owner)

    vesting.collect_dust(another_token, sender=recipient)
    assert another_token.balanceOf(recipient) == another_amount


def test_collect_dust_zero_vested_token(vesting, recipient, token):
    receipt = vesting.collect_dust(token, sender=recipient)

    transfers = token.Transfer.from_receipt(receipt)

    assert len(transfers) == 1
    assert transfers[0] == token.Transfer(vesting, recipient, 0)


def test_collect_dust_some_vested_token(chain, vesting, owner, recipient, token, amount, start_time, end_time):
    token.mint(owner, amount, sender=owner)

    token.transfer(vesting, amount, sender=owner)
    chain.pending_timestamp += (end_time - start_time) // 2
    vesting.collect_dust(token, sender=recipient)
    assert token.balanceOf(recipient) == amount


def test_collect_dust_some_vested_token_and_claimed(
    chain, vesting, owner, recipient, token, amount, start_time, end_time
):
    token.mint(owner, amount, sender=owner)

    token.transfer(vesting, amount, sender=owner)
    chain.pending_timestamp += (end_time - start_time) // 2
    receipt = vesting.claim(sender=recipient)
    claimed_amount = receipt.return_value

    receipt = vesting.collect_dust(token, sender=recipient)

    transfers = token.Transfer.from_receipt(receipt)
    assert len(transfers) == 1
    assert transfers[0] == token.Transfer(vesting, recipient, amount)

    assert token.balanceOf(recipient) == amount + claimed_amount


def test_collect_dust_beneficiary(vesting, owner, recipient, cold_storage, another_token, another_amount):
    another_token.transfer(vesting, another_amount, sender=owner)

    vesting.collect_dust(another_token, cold_storage, sender=recipient)
    assert another_token.balanceOf(cold_storage) == another_amount


def test_collect_dust_recepient_beneficiary(vesting, owner, recipient, another_token, another_amount):
    another_token.transfer(vesting, another_amount, sender=owner)

    vesting.collect_dust(another_token, recipient, sender=owner)
    assert another_token.balanceOf(recipient) == another_amount
