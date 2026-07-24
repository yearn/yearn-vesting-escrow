# `VestingEscrowFactory` API

`VestingEscrowFactory` deploys funded ERC-1167 minimal proxies for standard
ERC-20 vesting and ERC-4626 principal vesting. This page describes the complete
factory surface for the deployed 0.4.0 contracts.

The Ethereum mainnet factory is
[`0xFbd94e2D6942D5b4Ed0C5C9C43bded77a8f20215`](https://etherscan.io/address/0xfbd94e2d6942d5b4ed0c5c9c43bded77a8f20215#code).
Its immutable targets and deployment provenance are recorded in the
[0.4.0 manifest](../../deployments/ethereum/0.4.0.json).

The factory has no owner, mutable configuration, upgrade mechanism, or escrow
registry. Creation events are the canonical escrow index.

## Roles and units

The transaction caller is the `funder`. The factory transfers tokens or shares
from that address but gives it no implicit rights in the deployed escrow.
`recipient`, `revoker`, and ERC-4626 `yield_recipient` are always explicit
arguments.

Standard `amount` values are raw ERC-20 token units. ERC-4626
`principal_assets` values are underlying asset units, while
`max_funded_shares`, funding previews, and actual funding are vault-share
units. All time values are seconds.

## Constructor and getters

```vyper
__init__(
    standard_target: address,
    erc4626_target: address,
)

STANDARD_TARGET() -> address
ERC4626_TARGET() -> address
```

Both targets must be distinct deployed contracts. They are stored as
immutables and cannot change after deployment.

## Standard escrow deployment

```vyper
deploy_vesting_contract(
    token: address,
    recipient: address,
    amount: uint256,
    vesting_duration: uint256,
    vesting_start: uint256,
    cliff_length: uint256,
    permissionless_claims: bool,
    revoker: address,
) -> address
```

The caller must approve the factory for at least `amount` tokens. The factory:

1. Validates the configuration.
2. Creates a minimal proxy to `STANDARD_TARGET`.
3. Transfers exactly `amount` from the caller to the proxy.
4. Requires the proxy balance to increase by exactly `amount`.
5. Initializes the proxy.
6. Emits `TokenVestingEscrowCreated`.

The returned address is the new escrow.

| Parameter | Meaning |
| --- | --- |
| `token` | ERC-20 token held and vested by the escrow. |
| `recipient` | Owner of vested principal. Must differ from zero, the factory, new proxy, token, and revoker. |
| `amount` | Total principal in raw token units. Maximum `2**128 - 1`. |
| `vesting_duration` | Schedule length in seconds. Maximum `2**64 - 1`. |
| `vesting_start` | Unix timestamp at which linear vesting starts. May be in the past if the end remains in the future. |
| `cliff_length` | Seconds after `vesting_start` before accumulated vesting becomes claimable. Cannot exceed the duration. |
| `permissionless_claims` | Whether third parties may trigger claims to `recipient`. |
| `revoker` | Revocation authority, or zero for an irrevocable escrow. It cannot be the new proxy. |

See the [standard escrow API](standard.md) for the deployed contract's
lifecycle and authorization rules.

## ERC-4626 funding preview

```vyper
preview_erc4626_funding(
    vault: address,
    principal_assets: uint256,
) -> uint256
```

Returns the current shares required to fully back the requested principal. The
factory starts with:

```text
funded_shares = vault.convertToShares(principal_assets)
```

It rejects a zero result. If converting those shares back to assets would
underfund principal, it adds one raw share and verifies that the result covers
the requested assets.

The preview is not a guarantee. The vault conversion rate can change before
execution, so deployment also requires an explicit share limit.

## ERC-4626 escrow deployment

```vyper
deploy_erc4626_vesting(
    vault: address,
    recipient: address,
    principal_assets: uint256,
    max_funded_shares: uint256,
    vesting_duration: uint256,
    vesting_start: uint256,
    cliff_length: uint256,
    permissionless_claims: bool,
    revoker: address,
    yield_recipient: address,
) -> address
```

The caller chooses an exact asset-denominated principal and approves the
factory for `max_funded_shares` vault shares. The factory:

1. Validates the configuration.
2. Recomputes the rounded-up funding quote.
3. Reverts if the quote exceeds `max_funded_shares`.
4. Creates a minimal proxy to `ERC4626_TARGET`.
5. Transfers only the quoted shares from the caller.
6. Requires the proxy balance to increase by exactly the quote.
7. Initializes the proxy with the exact requested `principal_assets`.
8. Emits `ERC4626VestingEscrowCreated`.

Unused share allowance is not consumed. The returned address is the new
escrow.

| Parameter | Meaning |
| --- | --- |
| `vault` | ERC-4626 share token held by the escrow. |
| `recipient` | Owner of vested principal. Must differ from zero, the factory, new proxy, vault, and revoker. |
| `principal_assets` | Exact vesting principal in underlying asset units. Maximum `2**128 - 1`. |
| `max_funded_shares` | Maximum vault shares the factory may transfer from the funder. |
| `vesting_duration` | Schedule length in seconds. Maximum `2**64 - 1`. |
| `vesting_start` | Unix timestamp at which linear principal vesting starts. |
| `cliff_length` | Seconds after `vesting_start` before accumulated principal becomes claimable. |
| `permissionless_claims` | Whether third parties may trigger principal claims to `recipient`. |
| `revoker` | Revocation authority, or zero for an irrevocable escrow. It cannot be the new proxy. |
| `yield_recipient` | Fixed destination for yield shares. Must differ from zero, the proxy, vault, and underlying asset. |

See the [ERC-4626 escrow API](erc4626.md) for the deployed contract's
lifecycle and the [accounting guide](../erc4626.md) for its share allocation
model.

## Creation events

```vyper
event TokenVestingEscrowCreated:
    escrow: indexed(address)
    token: indexed(address)
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
    vault: indexed(address)
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
```

The first three fields of each event are indexed. `funded_shares` is the actual
ERC-4626 execution cost, not the caller's maximum. The events contain the
complete persistent deployment configuration.

## Reverts and asset requirements

Both deployment paths require:

- a nonzero amount or principal;
- a nonzero duration no greater than `2**64 - 1`;
- a cliff no greater than the duration;
- an end timestamp later than the deployment block;
- a recipient distinct from the token or vault and the revoker.

ERC-4626 principal cannot exceed `2**128 - 1`, and its funding conversion must
produce nonzero shares that cover the requested principal.

Funding reverts unless the new proxy receives exactly the transferred token or
share amount. Fee-on-transfer and rebasing assets are outside the supported
model. Any failure during creation, funding, or initialization reverts the
complete transaction.
