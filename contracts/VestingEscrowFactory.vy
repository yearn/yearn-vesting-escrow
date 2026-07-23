#pragma version 0.4.3
#pragma evm-version prague

"""
@title Vesting Escrow Factory
@author Curve Finance, Yearn Finance
@license MIT
@notice Deploys immutable minimal-proxy vesting escrows
"""

from ethereum.ercs import IERC20


interface VestingEscrowSimple:
    def initialize(
        owner: address,
        token: IERC20,
        recipient: address,
        amount: uint256,
        start_time: uint256,
        end_time: uint256,
        cliff_length: uint256,
        open_claim: bool,
        yield_to_owner: bool,
    ) -> bool: nonpayable
    def asset() -> address: view
    def total_principal() -> uint256: view


event VestingEscrowCreated:
    funder: indexed(address)
    token: indexed(IERC20)
    recipient: indexed(address)
    escrow: address
    amount: uint256
    vesting_start: uint256
    vesting_duration: uint256
    cliff_length: uint256
    open_claim: bool


event VestingEscrowConfigured:
    escrow: indexed(address)
    owner: indexed(address)
    asset: indexed(address)
    yield_to_owner: bool
    principal: uint256


BPS: constant(uint256) = 10_000
MAX_AMOUNT: constant(uint256) = 2**128 - 1
MAX_DURATION: constant(uint256) = 2**64 - 1

TARGET: public(immutable(address))
VYPER: public(immutable(address))
escrows_length: public(uint256)
escrows: public(address[1000000000000])


@deploy
def __init__(target: address, vyper_donate: address):
    assert target != empty(address)  # dev: invalid target
    TARGET = target
    VYPER = vyper_donate


@external
@pure
def version() -> uint256:
    return 2


@external
@nonreentrant
def deploy_vesting_contract(
    token: IERC20,
    recipient: address,
    amount: uint256,
    vesting_duration: uint256,
    vesting_start: uint256 = block.timestamp,
    cliff_length: uint256 = 0,
    open_claim: bool = True,
    support_vyper: uint256 = 0,
    owner: address = msg.sender,
    yield_to_owner: bool = False,
) -> address:
    """Deploy, fund, and initialize one vesting escrow."""
    assert support_vyper <= BPS  # dev: donation exceeds 100%
    assert amount > 0  # dev: amount must be > 0
    assert amount <= MAX_AMOUNT  # dev: amount too large
    assert not yield_to_owner or owner != empty(address)  # dev: invalid yield recipient
    assert vesting_duration > 0  # dev: invalid vesting period
    assert vesting_duration <= MAX_DURATION  # dev: duration too long
    assert cliff_length <= vesting_duration  # dev: invalid cliff
    assert vesting_start + vesting_duration > block.timestamp  # dev: invalid vesting period
    assert recipient not in [empty(address), self, token.address, owner]  # dev: invalid recipient

    escrow: address = create_minimal_proxy_to(TARGET)
    assert extcall token.transferFrom(msg.sender, escrow, amount, default_return_value=True)  # dev: funding failed
    assert staticcall token.balanceOf(escrow) >= amount  # dev: escrow not funded

    assert extcall VestingEscrowSimple(escrow).initialize(
        owner,
        token,
        recipient,
        amount,
        vesting_start,
        vesting_start + vesting_duration,
        cliff_length,
        open_claim,
        yield_to_owner,
    )
    asset: address = staticcall VestingEscrowSimple(escrow).asset()
    principal: uint256 = staticcall VestingEscrowSimple(escrow).total_principal()

    if support_vyper > 0:
        assert VYPER != empty(address)  # dev: invalid donation recipient
        donation: uint256 = amount * support_vyper // BPS
        if donation > 0:
            assert extcall token.transferFrom(
                msg.sender,
                VYPER,
                donation,
                default_return_value=True,
            )  # dev: donation failed

    index: uint256 = self.escrows_length
    self.escrows[index] = escrow
    self.escrows_length = index + 1

    log VestingEscrowCreated(
        funder=msg.sender,
        token=token,
        recipient=recipient,
        escrow=escrow,
        amount=amount,
        vesting_start=vesting_start,
        vesting_duration=vesting_duration,
        cliff_length=cliff_length,
        open_claim=open_claim,
    )
    log VestingEscrowConfigured(
        escrow=escrow,
        owner=owner,
        asset=asset,
        yield_to_owner=yield_to_owner,
        principal=principal,
    )
    return escrow
