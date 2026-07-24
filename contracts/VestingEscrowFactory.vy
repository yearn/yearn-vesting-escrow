#pragma version 0.4.3
#pragma evm-version prague

"""
@title Vesting Escrow Factory
@author Curve Finance, Yearn Finance
@license MIT
@notice Deploys dedicated ERC-20 and ERC-4626 minimal-proxy vesting escrows
"""

from ethereum.ercs import IERC20


interface IVestingEscrowSimple:
    def initialize(
        revoker: address,
        token: IERC20,
        recipient: address,
        amount: uint256,
        start_time: uint256,
        end_time: uint256,
        cliff_length: uint256,
        permissionless_claims: bool,
    ) -> bool: nonpayable


interface IVestingEscrow4626:
    def initialize(
        revoker: address,
        vault: address,
        recipient: address,
        funded_shares: uint256,
        start_time: uint256,
        end_time: uint256,
        cliff_length: uint256,
        permissionless_claims: bool,
        yield_recipient: address,
    ) -> bool: nonpayable
    def principal_assets() -> uint256: view


interface IERC4626:
    def asset() -> address: view


event TokenVestingEscrowCreated:
    escrow: indexed(address)
    token: indexed(IERC20)
    recipient: indexed(address)
    funder: address
    revoker: address
    amount: uint256
    vesting_start: uint256
    vesting_duration: uint256
    cliff_length: uint256
    permissionless_claims: bool


event ERC4626VestingEscrowCreated:
    escrow: indexed(address)
    vault: indexed(IERC20)
    recipient: indexed(address)
    funder: address
    revoker: address
    yield_recipient: address
    asset_token: address
    funded_shares: uint256
    principal_assets: uint256
    vesting_start: uint256
    vesting_duration: uint256
    cliff_length: uint256
    permissionless_claims: bool


MAX_DURATION: constant(uint256) = 2**64 - 1

STANDARD_TARGET: public(immutable(address))
ERC4626_TARGET: public(immutable(address))


@deploy
def __init__(
    standard_target: address,
    erc4626_target: address,
):
    assert standard_target.is_contract  # dev: invalid standard target
    assert erc4626_target.is_contract  # dev: invalid erc4626 target
    assert standard_target != erc4626_target  # dev: duplicate target

    STANDARD_TARGET = standard_target
    ERC4626_TARGET = erc4626_target


@internal
@view
def _validate(
    token: IERC20,
    recipient: address,
    amount: uint256,
    vesting_duration: uint256,
    vesting_start: uint256,
    cliff_length: uint256,
    revoker: address,
):
    assert amount > 0  # dev: amount must be > 0
    assert vesting_duration > 0  # dev: invalid vesting period
    assert vesting_duration <= MAX_DURATION  # dev: duration too long
    assert cliff_length <= vesting_duration  # dev: invalid cliff
    assert vesting_start + vesting_duration > block.timestamp  # dev: invalid vesting period
    assert recipient not in [empty(address), self, token.address, revoker]  # dev: invalid recipient


@internal
def _fund(
    token: IERC20,
    funder: address,
    escrow: address,
    amount: uint256,
):
    balance_before: uint256 = staticcall token.balanceOf(escrow)
    assert extcall token.transferFrom(funder, escrow, amount, default_return_value=True)  # dev: funding failed
    balance_after: uint256 = staticcall token.balanceOf(escrow)
    assert balance_after >= balance_before and balance_after - balance_before == amount  # dev: incorrect funding


@external
@nonreentrant
def deploy_vesting_contract(
    token: IERC20,
    recipient: address,
    amount: uint256,
    vesting_duration: uint256,
    vesting_start: uint256,
    cliff_length: uint256,
    permissionless_claims: bool,
    revoker: address,
) -> address:
    """Deploy a standard ERC-20 vesting escrow."""
    self._validate(token, recipient, amount, vesting_duration, vesting_start, cliff_length, revoker)

    escrow: address = create_minimal_proxy_to(STANDARD_TARGET)
    self._fund(token, msg.sender, escrow, amount)
    assert extcall IVestingEscrowSimple(escrow).initialize(
        revoker,
        token,
        recipient,
        amount,
        vesting_start,
        vesting_start + vesting_duration,
        cliff_length,
        permissionless_claims,
    )

    log TokenVestingEscrowCreated(
        escrow=escrow,
        token=token,
        recipient=recipient,
        funder=msg.sender,
        revoker=revoker,
        amount=amount,
        vesting_start=vesting_start,
        vesting_duration=vesting_duration,
        cliff_length=cliff_length,
        permissionless_claims=permissionless_claims,
    )
    return escrow


@external
@nonreentrant
def deploy_erc4626_vesting(
    vault: IERC20,
    recipient: address,
    funded_shares: uint256,
    vesting_duration: uint256,
    vesting_start: uint256,
    cliff_length: uint256,
    permissionless_claims: bool,
    revoker: address,
    yield_recipient: address,
) -> address:
    """Deploy an ERC-4626 principal vesting escrow."""
    self._validate(
        vault,
        recipient,
        funded_shares,
        vesting_duration,
        vesting_start,
        cliff_length,
        revoker,
    )
    assert yield_recipient != empty(address)  # dev: invalid yield recipient

    escrow: address = create_minimal_proxy_to(ERC4626_TARGET)
    self._fund(vault, msg.sender, escrow, funded_shares)
    assert extcall IVestingEscrow4626(escrow).initialize(
        revoker,
        vault.address,
        recipient,
        funded_shares,
        vesting_start,
        vesting_start + vesting_duration,
        cliff_length,
        permissionless_claims,
        yield_recipient,
    )

    log ERC4626VestingEscrowCreated(
        escrow=escrow,
        vault=vault,
        recipient=recipient,
        funder=msg.sender,
        revoker=revoker,
        yield_recipient=yield_recipient,
        asset_token=staticcall IERC4626(vault.address).asset(),
        funded_shares=funded_shares,
        principal_assets=staticcall IVestingEscrow4626(escrow).principal_assets(),
        vesting_start=vesting_start,
        vesting_duration=vesting_duration,
        cliff_length=cliff_length,
        permissionless_claims=permissionless_claims,
    )
    return escrow
