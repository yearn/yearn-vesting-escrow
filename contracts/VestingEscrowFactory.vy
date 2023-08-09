# @version 0.3.9
"""
@title Vesting Escrow Factory
@author Curve Finance, Yearn Finance
@license MIT
@notice Stores and distributes ERC20 tokens by deploying `VestingEscrowSimple` contracts
"""

from vyper.interfaces import ERC20


interface VestingEscrowSimple:
    def initialize(
        owner: address,
        token: address,
        recipient: address,
        amount: uint256,
        start_time: uint256,
        end_time: uint256,
        cliff_length: uint256,
        open_claim: bool,
    ) -> bool: nonpayable



event VestingEscrowCreated:
    funder: indexed(address)
    token: indexed(address)
    recipient: indexed(address)
    escrow: address
    amount: uint256
    vesting_start: uint256
    vesting_duration: uint256
    cliff_length: uint256
    open_claim: bool


TARGET: public(immutable(address))

@external
def __init__(target: address):
    """
    @notice Contract constructor
    @dev Prior to deployment you must deploy one copy of `VestingEscrowSimple` which
         is used as a library for vesting contracts deployed by this factory
    @param target `VestingEscrowSimple` contract address
    """
    TARGET = target


@external
def deploy_vesting_contract(
    token: address,
    recipient: address,
    amount: uint256,
    vesting_duration: uint256,
    vesting_start: uint256 = block.timestamp,
    cliff_length: uint256 = 0,
    open_claim: bool = True,
    owner: address = msg.sender,
) -> address:
    """
    @notice Deploy a new vesting contract
    @param token Address of the ERC20 token being distributed
    @param recipient Address to vest tokens for
    @param amount Amount of tokens being vested for `recipient`
    @param vesting_duration Time period over which tokens are released
    @param vesting_start Epoch time when tokens begin to vest
    @param open_claim Anyone can claim for `recipient`
    """
    assert cliff_length <= vesting_duration  # dev: incorrect vesting cliff
    assert vesting_start + vesting_duration > block.timestamp  # dev: just use a transfer, dummy
    assert vesting_duration > 0  # dev: duration must be > 0
    assert recipient not in [self, empty(address), token, owner]  # dev: wrong recipient

    escrow: address = create_minimal_proxy_to(TARGET)

    VestingEscrowSimple(escrow).initialize(
        owner,
        token,
        recipient,
        amount,
        vesting_start,
        vesting_start + vesting_duration,
        cliff_length,
        open_claim,
    )
    # skip transferFrom and approve and send directly to escrow
    assert ERC20(token).transferFrom(msg.sender, escrow, amount, default_return_value=True) # dev: funding failed

    log VestingEscrowCreated(msg.sender, token, recipient, escrow, amount, vesting_start, vesting_duration, cliff_length, open_claim)
    return escrow
