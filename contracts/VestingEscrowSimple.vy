# @version 0.2.8
"""
@title Simple Vesting Escrow
@author Curve Finance, Yearn Finance
@license MIT
@notice Vests ERC20 tokens for a single address
@dev Intended to be deployed many times via `VotingEscrowFactory`
"""

from vyper.interfaces import ERC20

event Fund:
    recipient: indexed(address)
    amount: uint256

event Claim:
    recipient: indexed(address)
    claimed: uint256

event Rug:
    recipient: address
    rugged: uint256

event AdminSet:
    admin: address

event RecipientTransferInitiated:
    recipient: address

event RecipientTransferFinalized:
    recipient: address

recipient: public(address)
token: public(ERC20)
start_time: public(uint256)
end_time: public(uint256)
cliff_length: public(uint256)
total_locked: public(uint256)
total_claimed: public(uint256)
disabled_at: public(uint256)

admin: public(address)
future_admin: public(address)

pending_recipient: public(address)
recipient_transfer_started: public(uint256)
ONE_WEEK: constant(uint256) = 604_800  # 1 week (in seconds)

@external
def __init__():
    # ensure that the original contract cannot be initialized
    self.admin = msg.sender


@external
@nonreentrant('lock')
def initialize(
    admin: address,
    token: address,
    recipient: address,
    amount: uint256,
    start_time: uint256,
    end_time: uint256,
    cliff_length: uint256,
) -> bool:
    """
    @notice Initialize the contract.
    @dev This function is seperate from `__init__` because of the factory pattern
         used in `VestingEscrowFactory.deploy_vesting_contract`. It may be called
         once per deployment.
    @param admin Admin address
    @param token Address of the ERC20 token being distributed
    @param recipient Address to vest tokens for
    @param amount Amount of tokens being vested for `recipient`
    @param start_time Epoch time at which token distribution starts
    @param end_time Time until everything should be vested
    """
    assert self.admin == ZERO_ADDRESS  # dev: can only initialize once

    self.token = ERC20(token)
    self.admin = admin
    self.start_time = start_time
    self.end_time = end_time
    self.cliff_length = cliff_length

    assert self.token.transferFrom(msg.sender, self, amount)  # dev: could not fund escrow

    self.recipient = recipient
    self.disabled_at = end_time  # Set to maximum time
    self.total_locked = amount
    log Fund(recipient, amount)

    return True


@internal
@view
def _total_vested_at(time: uint256 = block.timestamp) -> uint256:
    start: uint256 = self.start_time
    end: uint256 = self.end_time
    locked: uint256 = self.total_locked
    if time < start + self.cliff_length:
        return 0
    return min(locked * (time - start) / (end - start), locked)


@internal
@view
def _unclaimed(time: uint256 = block.timestamp) -> uint256:
    return self._total_vested_at(time) - self.total_claimed


@external
@view
def unclaimed() -> uint256:
    """
    @notice Get the number of unclaimed, vested tokens for recipient
    """
    # NOTE: if `rug_pull` is activated, limit by the activation timestamp
    return self._unclaimed(min(block.timestamp, self.disabled_at))


@internal
@view
def _locked(time: uint256 = block.timestamp) -> uint256:
    return self.total_locked - self._total_vested_at(time)


@external
@view
def locked() -> uint256:
    """
    @notice Get the number of locked tokens for recipient
    """
    # NOTE: if `rug_pull` is activated, limit by the activation timestamp
    return self._locked(min(block.timestamp, self.disabled_at))


@external
def claim(amount: uint256 = MAX_UINT256, recipient: address = msg.sender):
    """
    @notice Claim tokens which have vested
    @param amount Amount of tokens to claim
    @param recipient Address to transfer claimed tokens to
    """
    assert msg.sender == self.recipient  # dev: not recipient

    claim_period_end: uint256 = min(block.timestamp, self.disabled_at)
    claimable: uint256 = min(self._unclaimed(claim_period_end), amount)
    self.total_claimed += claimable

    assert self.token.transfer(recipient, claimable)
    log Claim(recipient, claimable)


@external
def rug_pull():
    """
    @notice Disable further flow of tokens and clawback the unvested part to admin
    """
    assert msg.sender == self.admin  # dev: admin only
    # NOTE: Rugging more than once is futile

    self.disabled_at = block.timestamp
    ruggable: uint256 = self._locked()

    assert self.token.transfer(self.admin, ruggable)
    log Rug(self.recipient, ruggable)


@external
def set_admin(future_admin: address):
    """
    @notice Starts transfer of admin control to another address
    @param future_admin Address to have ownership transferred to
    """
    assert msg.sender == self.admin  # dev: admin only
    self.future_admin = future_admin


@external
def accept_admin():
    """
    @notice Completes transfer of admin control to another address
    """
    assert msg.sender == self.future_admin  # dev: admin only
    self.admin = msg.sender
    log AdminSet(msg.sender)


@external
def set_recipient(recipient: address):
    """
    @notice Start transfer of escrow benefits to another address
    @param recipient Address to have escrow benefits transferred to
    """
    assert msg.sender == self.admin  # dev: admin only
    self.pending_recipient = recipient
    self.recipient_transfer_started = block.timestamp
    log RecipientTransferInitiated(recipient)


@external
def accept_recipient():
    """
    @notice Complete transfer of escrow benefits to another address
    """
    assert block.timestamp >= self.recipient_transfer_started  + ONE_WEEK  # dev: action not ready
    assert msg.sender == self.pending_recipient  # dev: recipient only
    self.recipient = msg.sender
    log RecipientTransferFinalized(msg.sender)
