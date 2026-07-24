import boa
from hypothesis import HealthCheck, given, settings, strategies as st


@settings(deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(sleep_time=st.integers(min_value=1, max_value=100000))
def test_claim_partial_copy(
    chain,
    vesting,
    recipient,
    token,
    amount,
    start_time,
    sleep_time,
    end_time,
    cliff_duration,
):
    with boa.env.anchor():
        timestamp = min(start_time + cliff_duration + sleep_time, end_time)
        chain.pending_timestamp = timestamp

        vesting.claim(recipient, 2**256 - 1, sender=recipient)
        expected_amount = amount * (timestamp - start_time) // (end_time - start_time)

        assert token.balanceOf(recipient) == expected_amount
