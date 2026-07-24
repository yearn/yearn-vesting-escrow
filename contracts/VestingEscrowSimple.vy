#pragma version 0.4.3
#pragma evm-version prague

"""
@title Simple Vesting Escrow
@author Curve Finance, Yearn Finance
@license MIT
@notice Vests one ERC-20 token for one recipient
"""

from ethereum.ercs import IERC20
from modules import vesting_math


event Claim:
    receiver: indexed(address)
    amount: uint256


event Revoked:
    recipient: indexed(address)
    revoker: indexed(address)
    receiver: indexed(address)
    unvested_amount: uint256
    ts: uint256


event RevocationRenounced:
    revoker: indexed(address)


event PermissionlessClaimsSet:
    enabled: bool


MAX_AMOUNT: constant(uint256) = 2**128 - 1
MAX_DURATION: constant(uint256) = 2**64 - 1

recipient: public(address)
token: public(IERC20)
start_time: public(uint256)
end_time: public(uint256)
cliff_length: public(uint256)
total_locked: public(uint256)
total_claimed: public(uint256)
# Zero until revocation; active escrows use end_time as their effective stop.
disabled_at: public(uint256)
claims_closed: bool
revoker: public(address)


@deploy
def __init__():
    # Prevent initialization of the implementation itself.
    self.recipient = self


@external
def initialize(
    revoker: address,
    token: IERC20,
    recipient: address,
    amount: uint256,
    start_time: uint256,
    end_time: uint256,
    cliff_length: uint256,
    permissionless_claims: bool,
) -> bool:
    """Initialize one funded minimal proxy."""
    assert self.recipient == empty(address)  # dev: can only initialize once

    assert amount > 0  # dev: amount must be > 0
    assert amount <= MAX_AMOUNT  # dev: amount too large
    assert recipient not in [empty(address), self, token.address, revoker]  # dev: invalid recipient
    assert end_time > block.timestamp and end_time > start_time  # dev: invalid vesting period
    duration: uint256 = end_time - start_time
    assert duration <= MAX_DURATION  # dev: duration too long
    assert cliff_length <= duration  # dev: invalid cliff
    assert staticcall token.balanceOf(self) >= amount  # dev: escrow not funded

    self.revoker = revoker
    self.token = token
    self.recipient = recipient
    self.start_time = start_time
    self.end_time = end_time
    self.cliff_length = cliff_length
    self.total_locked = amount
    self.claims_closed = not permissionless_claims

    return True


@internal
@view
def _vesting_end() -> uint256:
    disabled_at: uint256 = self.disabled_at
    if disabled_at == 0:
        return self.end_time
    return disabled_at


@internal
@view
def _total_vested_at(time: uint256) -> uint256:
    return vesting_math.vested_at(
        self.total_locked,
        self.start_time,
        self.end_time,
        self.cliff_length,
        time,
    )


@internal
@view
def _unclaimed(time: uint256) -> uint256:
    return self._total_vested_at(time) - self.total_claimed


@external
@view
def claimable() -> uint256:
    return self._unclaimed(min(block.timestamp, self._vesting_end()))


@external
@view
def locked() -> uint256:
    vesting_end: uint256 = self._vesting_end()
    time: uint256 = min(block.timestamp, vesting_end)
    return self._total_vested_at(vesting_end) - self._total_vested_at(time)


@external
@view
def permissionless_claims() -> bool:
    return not self.claims_closed


@external
@nonreentrant
def claim(
    receiver: address,
    max_amount: uint256,
) -> uint256:
    recipient: address = self.recipient
    assert receiver != empty(address)  # dev: invalid receiver
    assert msg.sender == recipient or not self.claims_closed and receiver == recipient  # dev: not authorized

    claim_period_end: uint256 = min(block.timestamp, self._vesting_end())
    claimable: uint256 = min(self._unclaimed(claim_period_end), max_amount)
    self.total_claimed += claimable

    if claimable > 0:
        assert extcall self.token.transfer(receiver, claimable, default_return_value=True)
        log Claim(receiver=receiver, amount=claimable)
    return claimable


@external
@nonreentrant
def revoke(receiver: address):
    revoker: address = self.revoker
    assert msg.sender == revoker  # dev: not revoker
    assert receiver != empty(address)  # dev: invalid receiver
    assert block.timestamp < self.end_time  # dev: vesting complete

    unvested_amount: uint256 = self.total_locked - self._total_vested_at(block.timestamp)
    self.disabled_at = block.timestamp
    self.revoker = empty(address)

    if unvested_amount > 0:
        assert extcall self.token.transfer(receiver, unvested_amount, default_return_value=True)
    log Revoked(
        recipient=self.recipient,
        revoker=revoker,
        receiver=receiver,
        unvested_amount=unvested_amount,
        ts=block.timestamp,
    )


@external
def renounce_revocation():
    revoker: address = self.revoker
    assert msg.sender == revoker  # dev: not revoker
    self.revoker = empty(address)
    log RevocationRenounced(revoker=revoker)


@external
def set_permissionless_claims(enabled: bool):
    assert msg.sender == self.recipient  # dev: not recipient
    self.claims_closed = not enabled
    log PermissionlessClaimsSet(enabled=enabled)
