"""Exercise vault-share vesting against a real ERC-4626 on a pinned fork."""

import os
from pathlib import Path
import warnings

import boa


CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
SUSDS = "0xa3931d71877C0E7a3148CB7Eb4463524FEc27fbD"
SUSDS_HOLDER = "0xfB4f83C3923EAB7B6254Cd2399C206109970f95E"
DEFAULT_BLOCK = 25_587_000
DAY = 24 * 60 * 60
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

ERC4626_INTERFACE = """
@view
def asset() -> address: ...
@view
def balanceOf(account: address) -> uint256: ...
@view
def convertToAssets(shares: uint256) -> uint256: ...
@nonpayable
def approve(spender: address, amount: uint256) -> bool: ...
"""


def main():
    rpc_url = os.environ.get("MAINNET_RPC")
    if rpc_url is None:
        raise SystemExit("MAINNET_RPC must be set")

    block_identifier = os.environ.get("MAINNET_BLOCK", str(DEFAULT_BLOCK))
    if not block_identifier.isdigit():
        raise SystemExit("MAINNET_BLOCK must be a pinned numeric block")
    block_identifier = int(block_identifier)
    boa.fork(rpc_url, block_identifier=block_identifier)
    assert boa.env.evm.patch.chain_id == 1

    warnings.filterwarnings(
        "ignore",
        message="casted bytecode does not match compiled bytecode*",
        category=UserWarning,
    )

    vault_address = os.environ.get("ERC4626_VAULT", SUSDS)
    holder = os.environ.get("ERC4626_HOLDER", SUSDS_HOLDER)
    amount = int(os.environ.get("ERC4626_AMOUNT", 10**18))

    deployer = boa.env.generate_address("fork-deployer")
    recipient = boa.env.generate_address("fork-recipient")
    vault = boa.loads_vyi(ERC4626_INTERFACE, name="ERC4626").at(vault_address)
    assert vault.asset() != ZERO_ADDRESS
    assert vault.balanceOf(holder) >= amount
    assert vault.convertToAssets(amount) > amount

    standard_target = boa.load(CONTRACTS / "VestingEscrowSimple.vy", sender=deployer)
    erc4626_target = boa.load(CONTRACTS / "VestingEscrow4626.vy", sender=deployer)
    factory = boa.load(
        CONTRACTS / "VestingEscrowFactory.vy",
        standard_target,
        erc4626_target,
        sender=deployer,
    )

    start_time = boa.env.evm.patch.timestamp + 60
    duration = 60 * DAY
    vault.approve(factory, amount, sender=holder)
    escrow_address = factory.deploy_erc4626_vesting(
        vault,
        recipient,
        amount,
        duration,
        start_time,
        0,
        True,
        holder,
        holder,
        sender=holder,
    )
    escrow = boa.load_partial(CONTRACTS / "VestingEscrow4626.vy").at(escrow_address)

    boa.env.time_travel(seconds=30 * DAY)
    holder_balance = vault.balanceOf(holder)
    claimed = escrow.claim_principal(sender=recipient)
    assert claimed > 0
    assert vault.balanceOf(recipient) == claimed
    assert vault.balanceOf(holder) == holder_balance
    assert (
        vault.convertToAssets(vault.balanceOf(escrow))
        >= escrow.principal_assets() - escrow.claimed_principal_assets()
    )

    yield_shares = escrow.claim_yield(sender=recipient)
    assert yield_shares > 0
    assert vault.balanceOf(holder) == holder_balance + yield_shares

    escrow.revoke(sender=holder)
    escrow.claim_principal(sender=recipient)
    assert vault.balanceOf(escrow) == 0
    print(f"sUSDS fork lifecycle passed at Ethereum block {block_identifier}")
