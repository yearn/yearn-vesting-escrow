"""Deploy the escrow implementation and factory.

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
VYPER_DONATE = "0x70CCBE10F980d80b7eBaab7D2E3A73e87D67B775"


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


def deploy_contracts(deployer, vyper_donate):
    target = boa.load(CONTRACTS / "VestingEscrowSimple.vy", sender=deployer)
    factory = boa.load(
        CONTRACTS / "VestingEscrowFactory.vy",
        target,
        vyper_donate,
        sender=deployer,
    )

    assert factory.TARGET() == target.address
    assert factory.VYPER() == vyper_donate
    assert target.version() == factory.version() == 2
    return target, factory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpc-url", default=os.environ.get("RPC_URL"))
    parser.add_argument("--private-key-env", default="DEPLOYER_PRIVATE_KEY")
    parser.add_argument("--expected-chain-id", type=int)
    parser.add_argument("--vyper-donate", default=VYPER_DONATE)
    args = parser.parse_args()

    deployer, chain_id = configure_environment(
        args.rpc_url,
        args.private_key_env,
        args.expected_chain_id,
    )
    target, factory = deploy_contracts(deployer, args.vyper_donate)

    print(
        json.dumps(
            {
                "chain_id": chain_id,
                "deployer": str(deployer),
                "vyper_donate": args.vyper_donate,
                "target": str(target.address),
                "factory": str(factory.address),
            },
            indent=2,
        )
    )
