#pragma version 0.4.3
#pragma evm-version prague

"""
@title Vesting arithmetic
@notice Stateless helpers shared by token and ERC-4626 vesting escrows
"""


@internal
@pure
def vested_at(
    total: uint256,
    start_time: uint256,
    end_time: uint256,
    cliff_length: uint256,
    time: uint256,
) -> uint256:
    if time < start_time + cliff_length:
        return 0
    if time >= end_time:
        return total
    return total * (time - start_time) // (end_time - start_time)


@internal
@pure
def payout_shares(
    principal_shares: uint256,
    principal_before: uint256,
    principal_after: uint256,
) -> uint256:
    """Pay shares while rounding the remaining reserve up."""
    if principal_after == 0:
        return principal_shares

    whole: uint256 = principal_shares // principal_before
    remainder: uint256 = principal_shares % principal_before
    scaled_remainder: uint256 = remainder * principal_after
    reserve: uint256 = whole * principal_after + scaled_remainder // principal_before
    if scaled_remainder % principal_before > 0:
        reserve += 1
    return principal_shares - reserve
