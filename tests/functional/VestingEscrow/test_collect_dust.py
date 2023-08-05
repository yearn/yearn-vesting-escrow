import ape


def test_claim_non_vested_token(
    vesting, ychad, receiver, another_token, another_amount
):
    another_token.transfer(vesting, another_amount, sender=ychad)

    vesting.collect_dust(another_token, sender=receiver)
    assert another_token.balanceOf(receiver) == another_amount


def test_do_not_allow_claim_of_vested_token(vesting, receiver, token):
    with ape.reverts(dev_message="dev: can't collect"):
        vesting.collect_dust(token, sender=receiver)


def test_allow_vested_token_dust_to_be_claim_at_end(
    chain, vesting, ychad, receiver, token, amount, end_time
):
    token.transfer(vesting, amount, sender=ychad)
    chain.pending_timestamp = end_time + 1
    vesting.collect_dust(token, sender=receiver)
    assert token.balanceOf(receiver) == 2 * amount
