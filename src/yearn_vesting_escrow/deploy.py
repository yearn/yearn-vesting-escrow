"""Deploy both escrow implementations and the factory.

This is development tooling, not the production rollout script. Network secrets
are read from the environment and never accepted as command-line values.
"""

import argparse
import json
import os
from pathlib import Path

import boa
from eth_account import Account


CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


def configure_environment(rpc_url, private_key_env, expected_chain_id):
    if rpc_url is None:
        deployer = boa.env.generate_address("deployer")
        boa.env.set_balance(deployer, 10**24)
        return deployer, "local"

    private_key = os.environ.get(private_key_env)
    if private_key is None:
        raise SystemExit(f"{private_key_env} must be set for network deployment")

    boa.set_network_env(rpc_url)
    account = Account.from_key(private_key)
    boa.env.add_account(account, force_eoa=True)
    chain_id = boa.env.get_chain_id()
    if expected_chain_id is not None and chain_id != expected_chain_id:
        raise SystemExit(f"expected chain ID {expected_chain_id}, connected to {chain_id}")
    return account.address, chain_id


def deploy_contracts(deployer):
    standard_target = boa.load(CONTRACTS / "VestingEscrowSimple.vy", sender=deployer)
    erc4626_target = boa.load(CONTRACTS / "VestingEscrow4626.vy", sender=deployer)
    factory = boa.load(
        CONTRACTS / "VestingEscrowFactory.vy",
        standard_target,
        erc4626_target,
        sender=deployer,
    )

    assert factory.STANDARD_TARGET() == standard_target.address
    assert factory.ERC4626_TARGET() == erc4626_target.address
    return standard_target, erc4626_target, factory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpc-url", default=os.environ.get("RPC_URL"))
    parser.add_argument("--private-key-env", default="DEPLOYER_PRIVATE_KEY")
    parser.add_argument("--expected-chain-id", type=int)
    args = parser.parse_args()

    deployer, chain_id = configure_environment(
        args.rpc_url,
        args.private_key_env,
        args.expected_chain_id,
    )
    standard_target, erc4626_target, factory = deploy_contracts(deployer)

    print(
        json.dumps(
            {
                "chain_id": chain_id,
                "deployer": str(deployer),
                "standard_target": str(standard_target.address),
                "erc4626_target": str(erc4626_target.address),
                "factory": str(factory.address),
            },
            indent=2,
        )
    )
