from brownie.test import given, strategy


@given(sleep_time=strategy("uint", max_value=100000))
def test_claim_partial(
    vesting, token, accounts, chain, start_time, sleep_time, end_time, cliff_duration
):
    timestamp = start_time - chain.time() + sleep_time
    chain.sleep(timestamp)
    tx = vesting.claim({"from": accounts[1]})
    if timestamp - start_time > cliff_duration:
        expected_amount = (
            10 ** 20 * (tx.timestamp - start_time) // (end_time - start_time)
        )
    else:
        expected_amount = 0

    assert token.balanceOf(accounts[1]) == expected_amount
