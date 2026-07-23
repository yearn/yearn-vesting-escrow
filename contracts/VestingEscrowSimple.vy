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
    recipient: indexed(address)
    claimed: uint256


event Revoked:
    recipient: address
    owner: address
    rugged: uint256
    ts: uint256


event Disowned:
    owner: address


event SetOpenClaim:
    state: bool


MAX_AMOUNT: constant(uint256) = 2**128 - 1
MAX_DURATION: constant(uint256) = 2**64 - 1

recipient: public(address)
token: public(IERC20)
start_time: public(uint256)
end_time: public(uint256)
cliff_length: public(uint256)
total_locked: public(uint256)
total_claimed: public(uint256)
disabled_at: public(uint256)
open_claim: public(bool)
initialized: public(bool)
owner: public(address)


@deploy
def __init__():
    # Prevent initialization of the implementation itself.
    self.initialized = True


@external
@pure
def version() -> uint256:
    return 2


@external
def initialize(
    owner: address,
    token: IERC20,
    recipient: address,
    amount: uint256,
    start_time: uint256,
    end_time: uint256,
    cliff_length: uint256,
    open_claim: bool,
) -> bool:
    """Initialize one funded minimal proxy."""
    assert not self.initialized  # dev: can only initialize once
    self.initialized = True

    assert amount > 0  # dev: amount must be > 0
    assert amount <= MAX_AMOUNT  # dev: amount too large
    assert recipient not in [empty(address), self, token.address, owner]  # dev: invalid recipient
    assert end_time > block.timestamp and end_time > start_time  # dev: invalid vesting period
    duration: uint256 = end_time - start_time
    assert duration <= MAX_DURATION  # dev: duration too long
    assert cliff_length <= duration  # dev: invalid cliff
    assert staticcall token.balanceOf(self) >= amount  # dev: escrow not funded

    self.owner = owner
    self.token = token
    self.recipient = recipient
    self.start_time = start_time
    self.end_time = end_time
    self.cliff_length = cliff_length
    self.total_locked = amount
    self.disabled_at = end_time
    self.open_claim = open_claim

    return True


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
def unclaimed() -> uint256:
    return self._unclaimed(min(block.timestamp, self.disabled_at))


@external
@view
def locked() -> uint256:
    time: uint256 = min(block.timestamp, self.disabled_at)
    return self._total_vested_at(self.disabled_at) - self._total_vested_at(time)


@external
@nonreentrant
def claim(
    beneficiary: address = msg.sender,
    amount: uint256 = max_value(uint256),
) -> uint256:
    recipient: address = self.recipient
    assert msg.sender == recipient or self.open_claim and beneficiary == recipient  # dev: not authorized

    claim_period_end: uint256 = min(block.timestamp, self.disabled_at)
    claimable: uint256 = min(self._unclaimed(claim_period_end), amount)
    self.total_claimed += claimable

    if claimable > 0:
        assert extcall self.token.transfer(beneficiary, claimable, default_return_value=True)
    log Claim(recipient=beneficiary, claimed=claimable)
    return claimable


@external
@nonreentrant
def revoke(
    ts: uint256 = block.timestamp,
    beneficiary: address = msg.sender,
):
    owner: address = self.owner
    assert msg.sender == owner  # dev: not owner
    assert ts >= block.timestamp and ts < self.end_time  # dev: no back to the future

    ruggable: uint256 = self._total_vested_at(self.disabled_at) - self._total_vested_at(ts)
    self.disabled_at = ts
    self.owner = empty(address)

    if ruggable > 0:
        assert extcall self.token.transfer(beneficiary, ruggable, default_return_value=True)
    log Disowned(owner=owner)
    log Revoked(recipient=self.recipient, owner=owner, rugged=ruggable, ts=ts)


@external
def disown():
    owner: address = self.owner
    assert msg.sender == owner  # dev: not owner
    self.owner = empty(address)
    log Disowned(owner=owner)


@external
def set_open_claim(open_claim: bool):
    assert msg.sender == self.recipient  # dev: not recipient
    self.open_claim = open_claim
    log SetOpenClaim(state=open_claim)


@external
@nonreentrant
def collect_dust(
    token: IERC20,
    beneficiary: address = msg.sender,
):
    recipient: address = self.recipient
    assert msg.sender == recipient or self.open_claim and beneficiary == recipient  # dev: not authorized

    amount: uint256 = staticcall token.balanceOf(self)
    if token.address == self.token.address:
        required: uint256 = self._total_vested_at(self.disabled_at) - self.total_claimed
        assert amount >= required  # dev: insolvent
        amount -= required

    if amount > 0:
        assert extcall token.transfer(beneficiary, amount, default_return_value=True)
    required_balance: uint256 = self._total_vested_at(self.disabled_at) - self.total_claimed
    assert staticcall self.token.balanceOf(self) >= required_balance
