# Development and deployment

Version 0.4.0 is unreleased, unaudited, and has no production deployment. This
guide documents the repository tooling and the review gates required before a
future rollout.

## Prerequisites

- Python 3.11
- [`uv`](https://docs.astral.sh/uv/)
- an archive-capable Ethereum RPC for the pinned real-vault smoke test

Install the exact locked environment:

```sh
uv sync --locked
```

The package exposes three entry points:

| Command | Purpose |
| --- | --- |
| `vesting-escrow-compile` | Compile every Vyper contract and report bytecode sizes. |
| `vesting-escrow-deploy` | Deploy both implementations and their factory locally or to a development network. |
| `vesting-escrow-fork-smoke` | Exercise the ERC-4626 lifecycle against a real vault on a pinned mainnet fork. |

## Compile and test

```sh
uv run --locked vesting-escrow-compile
uv run --locked pytest
uv run --locked pytest tests/functional/ --gas-profile
uv run --locked pytest tests/integration/
```

The tests cover the exact external ABI, factory funding, authorization,
revocation, adversarial transfer callbacks, ERC-4626 gain/loss accounting,
rounding, and a differential accounting model.

After changing dependencies in `pyproject.toml`, regenerate the lock:

```sh
uv lock
```

Commit `pyproject.toml` and `uv.lock` together.

## Local deployment

Deploy into Titanoboa's local environment without a key:

```sh
uv run --locked vesting-escrow-deploy
```

The command deploys in this order:

1. `VestingEscrowSimple`
2. `VestingEscrow4626`
3. `VestingEscrowFactory(standard_target, erc4626_target)`

It checks both immutable target getters and prints a JSON result:

```json
{
  "chain_id": "local",
  "deployer": "0x...",
  "standard_target": "0x...",
  "erc4626_target": "0x...",
  "factory": "0x..."
}
```

## Development network deployment

Secrets are read only from the environment:

```sh
RPC_URL=https://... DEPLOYER_PRIVATE_KEY=... \
  uv run --locked vesting-escrow-deploy --expected-chain-id 11155111
```

`--expected-chain-id` is strongly recommended. The command exits before
deployment when the connected chain ID differs.

This entry point is development tooling, not the production rollout script. It
does not create a reviewed manifest, verify source, transfer governance
ownership, or run canaries.

## Pinned ERC-4626 fork smoke

Run the default sUSDS scenario:

```sh
MAINNET_RPC=https://... uv run --locked vesting-escrow-fork-smoke
```

The defaults are:

| Variable | Default |
| --- | --- |
| `MAINNET_BLOCK` | `25587000` |
| `ERC4626_VAULT` | sUSDS at `0xa3931d71877C0E7a3148CB7Eb4463524FEc27fbD` |
| `ERC4626_HOLDER` | Account funded with shares at the pinned block |
| `ERC4626_AMOUNT` | `10**18` raw shares |

Override all vault-specific values together when testing another vault:

```sh
MAINNET_RPC=https://... \
MAINNET_BLOCK=... \
ERC4626_VAULT=0x... \
ERC4626_HOLDER=0x... \
ERC4626_AMOUNT=... \
  uv run --locked vesting-escrow-fork-smoke
```

The block must be numeric and pinned. The smoke test deploys the 0.4.0
contracts, creates an escrow, claims principal and yield, revokes, claims the
remaining vested principal, and checks that the escrow is empty.

## Production manifest

A production deployment should begin from an immutable reviewed manifest
containing at least:

```text
release
source repository
source commit
Vyper version and EVM target
chain ID
deployer
standard implementation address and bytecode hashes
ERC-4626 implementation address and bytecode hashes
factory address and bytecode hashes
factory constructor arguments
deployment transaction hashes
verification URLs
supported token policy
approved ERC-4626 vaults and review evidence
canary escrow transactions and observed results
independent audit reference
```

Record both creation and runtime bytecode hashes. Recompile from the clean
source commit and compare before announcing addresses.

## Production checklist

### Source and build

- Pin a clean release commit and tag.
- Run the locked full suite and integration smoke tests.
- Reproduce compiler output in an independent environment.
- Confirm Vyper 0.4.3 and the Prague EVM target are intended for every target
  chain.
- Review runtime and creation bytecode size.
- Complete an independent audit of the final commit.

### Contract deployment

- Deploy the standard implementation.
- Deploy the ERC-4626 implementation.
- Confirm both implementation initializers are disabled.
- Deploy the factory with the two exact implementation addresses.
- Read back `STANDARD_TARGET()` and `ERC4626_TARGET()`.
- Confirm the targets are distinct and match the manifest.
- Verify all three contracts on the chain explorer.

### Asset policy

- Test exact `transferFrom` balance deltas for each supported token or share.
- Exclude fee-on-transfer, rebasing, paused, blacklisted, or otherwise
  incompatible assets.
- Review every supported ERC-4626 vault against
  [the vault requirements](erc4626.md#vault-requirements).
- Document vault upgrade and emergency-control risks.

### Canary escrows

- Create low-value standard and ERC-4626 escrows.
- Decode and compare every creation event field.
- Exercise partial and full principal claims.
- Exercise recipient-selected and permissionless claim routes.
- Claim ERC-4626 yield.
- Exercise revocation and post-revocation recipient claims.
- Exercise irrevocable creation or renunciation.
- Confirm indexers discover both escrow types from events.

### Release

- Publish the manifest, verified addresses, ABI artifacts, audit, and canary
  evidence.
- Update the [production deployment history](../readme.md#production-deployments).
- Add the factory addresses and ABIs to supported managers and indexers.
- Monitor initial escrows before recommending broad use.

The factory and implementations are immutable. A failed configuration cannot
be upgraded in place; remediation requires a new deployment and explicit
migration by integrators.
