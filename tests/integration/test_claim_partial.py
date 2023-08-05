from hypothesis import given, settings, strategies as st


@settings(deadline=None)
@given(sleep_time=st.integers(min_value=1, max_value=100000))
def test_claim_partial_copy(
    chain,
    vesting,
    receiver,
    token,
    amount,
    start_time,
    sleep_time,
    end_time,
    cliff_duration,
):
    chain.pending_timestamp += sleep_time

    tx = vesting.claim(sender=receiver)
    if tx.timestamp - start_time > cliff_duration:
        expected_amount = (
            amount * (tx.timestamp - start_time) // (end_time - start_time)
        )
    else:
        expected_amount = 0

    assert token.balanceOf(receiver) == expected_amount
