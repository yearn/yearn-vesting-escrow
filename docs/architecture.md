# Architecture and security model

This document describes the unreleased 0.4.0 contracts. Historical deployments
use different code and ABIs.

## Topology

The deployment consists of three contracts:

1. One `VestingEscrowSimple` implementation.
2. One `VestingEscrow4626` implementation.
3. One `VestingEscrowFactory` configured with both implementation addresses as
   immutables.

For each escrow, the factory creates an ERC-1167 minimal proxy, transfers the
exact requested tokens or shares into it, and initializes it in the same
transaction. A failure in any step reverts the complete deployment.

The implementation contracts mark themselves initialized in their
constructors. Their code can therefore only be used through a fresh proxy. An
uninitialized proxy must never be exposed between creation and initialization;
the factory's atomic flow enforces this.

## Roles and destinations

The role model separates persistent authority from transfer destinations:

| Name | Persistent? | Rights |
| --- | --- | --- |
| `recipient` | Yes | Owns vested principal, chooses the receiver for its own claims, and enables or disables permissionless principal claims. |
| `revoker` | Until used or renounced | Stops vesting immediately and chooses where unvested principal is sent. |
| `yield_recipient` | Yes, ERC-4626 only | Receives all yield shares. It has no authority merely by being the destination. |
| `funder` | No | Pays the initial tokens or shares during factory deployment. |
| `receiver` | No | Receives one claim or revocation transfer. |
| transaction caller | No | May execute a permissionless action without acquiring routing authority. |

The factory allows the zero address as `revoker`, which creates an irrevocable
escrow from the outset. A nonzero revoker can permanently remove its own
authority with `renounce_revocation()`.

The `recipient` and `revoker` must be different. The funder, revoker, and
ERC-4626 yield recipient may otherwise be the same address if that is the
intended policy.

## Schedule

All time values are Unix timestamps or durations in seconds. Let:

- `S` be `start_time`;
- `E` be `end_time`;
- `C` be `cliff_length`;
- `P` be the total token amount or initial principal assets.

The vested amount at time `t` is:

```text
0                                      when t < S + C
P                                      when t >= E
floor(P * (t - S) / (E - S))           otherwise
```

The cliff gates an already-running linear schedule. At `S + C`, the accumulated
linear amount becomes claimable at once; the cliff does not shift the start of
the linear slope.

The factory requires:

- a nonzero amount or share amount;
- `0 < vesting_duration <= 2**64 - 1`;
- `cliff_length <= vesting_duration`;
- `vesting_start + vesting_duration > block.timestamp`.

The start may be in the past, but the end must still be in the future when the
escrow is deployed.

## Lifecycle

An escrow has three practical states:

| State | `disabled_at()` | `revoker()` | Behavior |
| --- | ---: | --- | --- |
| Active and revocable | `0` | Nonzero | Vesting continues until the scheduled end or immediate revocation. |
| Active and irrevocable | `0` | Zero | Vesting continues until the scheduled end and cannot be revoked. |
| Revoked | Revocation timestamp | Zero | Vesting is frozen at that timestamp; vested but unclaimed principal remains claimable. |

Successful revocation clears `revoker` before making external token transfers.
Revocation is not available at or after `end_time`.

`disabled_at()` deliberately uses zero as the active sentinel. Consumers must
use `end_time()` as the effective stop while `disabled_at() == 0`.

For the standard escrow, `locked()` means principal that has not yet vested. It
is not the token balance of the escrow. It becomes zero immediately after
revocation even though vested, unclaimed tokens may remain in the contract.

## Authorization

Principal claims obey these rules:

| Caller | Receiver | Permissionless claims enabled | Result |
| --- | --- | --- | --- |
| `recipient` | Any nonzero address | Either | Allowed |
| Anyone else | `recipient` | Yes | Allowed |
| Anyone else | Any other address | Either | Rejected |
| Anyone else | `recipient` | No | Rejected |

This lets automation claim for a recipient without letting the automation
redirect funds. Only the recipient can call
`set_permissionless_claims(bool)`.

ERC-4626 `claim_yield()` is callable by anyone. It always transfers to the
stored `yield_recipient`, so the caller cannot redirect value.

## Factory and discovery

The factory has no owner, upgrade mechanism, or mutable implementation target.
It has no escrow registry. Consumers discover escrows from:

- `TokenVestingEscrowCreated` for standard ERC-20 escrows;
- `ERC4626VestingEscrowCreated` for ERC-4626 escrows.

An index should treat `(chain_id, factory, transaction_hash, log_index)` as the
event identity and account for normal chain reorganizations.

## Accounting invariants

The intended invariants are:

- a standard escrow's recipient entitlement never exceeds `total_locked`;
- `total_claimed` never exceeds the vested entitlement at the effective stop;
- revocation preserves all principal vested at the revocation timestamp;
- ERC-4626 principal accounting is denominated in underlying assets;
- yield can only be routed to the fixed `yield_recipient`;
- vault loss is shared proportionally by outstanding principal;
- permissionless execution never grants permissionless routing;
- all lifecycle destinations are explicit and nonzero.

See [ERC-4626 accounting](erc4626.md) for the share allocation and rounding
rules.

## Supported assets

Deployment requires exact balance movement. Fee-on-transfer tokens and vault
shares are rejected when the factory's post-transfer balance delta differs from
the requested amount.

After deployment, supported tokens and vaults must:

- remain transferable;
- return `True` or no return value from ERC-20 `transfer` and `transferFrom`;
- avoid transfer fees, rebasing balances, blacklists, and pauses that can block
  lifecycle transfers;
- preserve the ERC-4626 conversion behavior described in
  [the accounting guide](erc4626.md).

These constraints are operational requirements, not protections the escrow can
enforce against a later token or vault upgrade.

Direct donations of the vested ERC-20 to a standard escrow are not recoverable
through the escrow and do not increase recipient entitlement. Direct donations
of vault shares to an ERC-4626 escrow participate in its principal/yield split.
Unrelated tokens sent to either escrow are unsupported and have no recovery
method.

## Intentional omissions from v0.3

Version 0.4.0 removes legacy surface that is not part of vesting correctness:

- no `version()` or on-chain release label;
- no Vyper donation transfer;
- no factory escrow array, kind mapping, or other registry;
- no generic dust recovery;
- no future-dated revocation;
- no generated default-argument overloads;
- no shared standard/ERC-4626 accounting module.

Defaults belong in deployment tools and interfaces. Version identification
belongs in verified source, deployment manifests, and factory addresses.
Creation events provide discovery without duplicating an ever-growing registry.
The two escrow implementations remain independent so standard-token accounting
does not inherit ERC-4626 complexity.

## Trust and review boundaries

The contracts are immutable after deployment. This removes administrator
upgrade risk but makes deployment review critical. A production review must
cover:

- the exact source commit, Vyper version, compiler settings, and bytecode;
- both implementation addresses wired into the factory;
- token and vault behavior, including upgradeability and privileged controls;
- every role and destination in the deployment transaction;
- schedule units and timestamps;
- source verification, event indexing, and low-value canary escrows.

Version 0.4.0 is not production-ready until an independent audit and the
deployment process described in [the deployment guide](deployment.md) are
complete.
