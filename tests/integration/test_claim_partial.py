from brownie.test import given, strategy


@given(sleep_time=strategy("uint", max_value=100000))
def test_claim_partial(
    vesting, token, accounts, chain, start_time, sleep_time, end_time
):
    chain.sleep(start_time - chain.time() + sleep_time)
    tx = vesting.claim({"from": accounts[1]})
    expected_amount = 10 ** 20 * (tx.timestamp - start_time) // (end_time - start_time)

    assert token.balanceOf(accounts[1]) == expected_amount
