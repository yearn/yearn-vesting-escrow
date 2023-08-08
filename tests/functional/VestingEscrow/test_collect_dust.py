import ape


def test_claim_non_vested_token(
    vesting, ychad, receiver, another_token, another_amount
):
    another_token.transfer(vesting, another_amount, sender=ychad)

    vesting.collect_dust(another_token, sender=receiver)
    assert another_token.balanceOf(receiver) == another_amount


def test_collect_dust_zero_vested_token(vesting, receiver, token):
    receipt = vesting.collect_dust(token, sender=receiver)

    transfers = token.Transfer.from_receipt(receipt)

    assert len(transfers) == 1
    assert transfers[0] == token.Transfer(vesting, receiver, 0)


def test_collect_dust_some_vested_token(
    chain, vesting, ychad, receiver, token, amount, start_time, end_time
):
    token.transfer(vesting, amount, sender=ychad)
    chain.pending_timestamp += (end_time - start_time) // 2
    vesting.collect_dust(token, sender=receiver)
    assert token.balanceOf(receiver) == amount


def test_collect_dust_beneficiary(
    vesting, ychad, receiver, cold_storage, another_token, another_amount
):
    another_token.transfer(vesting, another_amount, sender=ychad)

    vesting.collect_dust(another_token, cold_storage, sender=receiver)
    assert another_token.balanceOf(cold_storage) == another_amount


def test_collect_dust_recepient_beneficiary(
    vesting, ychad, receiver, another_token, another_amount
):
    another_token.transfer(vesting, another_amount, sender=ychad)

    vesting.collect_dust(another_token, receiver, sender=ychad)
    assert another_token.balanceOf(receiver) == another_amount