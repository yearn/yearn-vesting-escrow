# `VestingEscrowSimple` API

`VestingEscrowSimple` vests a fixed amount of one ERC-20 token for one
recipient. This page describes its complete external surface, roles, schedule,
authorization, and events for the unreleased 0.4.0 release.

All amounts are raw units of `token`. All transfer destinations must be
nonzero.

## Roles

| Role | Authority |
| --- | --- |
| `recipient` | Owns vested principal, may route its own claims to any valid receiver, and controls permissionless claiming. |
| `revoker` | May stop vesting immediately and route unvested principal to any valid receiver, or permanently renounce that authority. |
| third-party caller | May claim only when permissionless claims are enabled and only to the stored recipient. |
| `receiver` | Receives one claim or revocation transfer and gains no persistent authority. It cannot be zero or the escrow itself. |

A zero `revoker` makes the escrow irrevocable from initialization.

## Initialization

```vyper
__init__()

initialize(
    revoker: address,
    token: address,
    recipient: address,
    amount: uint256,
    start_time: uint256,
    end_time: uint256,
    cliff_length: uint256,
    permissionless_claims: bool,
) -> bool
```

Applications should deploy through the
[`VestingEscrowFactory`](factory.md), which funds and initializes the proxy
atomically. Each proxy can initialize only once, and the implementation
contract's no-argument constructor disables its own initializer.

Initialization requires:

- `0 < amount <= 2**128 - 1`;
- a recipient distinct from zero, the proxy, token, and revoker;
- `end_time` later than both the current block and `start_time`;
- a duration no greater than `2**64 - 1`;
- `cliff_length` no greater than the duration;
- a proxy token balance of at least `amount`.

## Schedule and lifecycle state

Let `S = start_time`, `E = end_time`, `C = cliff_length`, and
`P = total_locked`. Principal vested at time `t` is:

```text
0                                      when t < S + C
P                                      when t >= E
floor(P * (t - S) / (E - S))           otherwise
```

The cliff gates the running linear schedule. At `S + C`, the accumulated
linear amount becomes claimable at once.

`disabled_at()` is zero until revocation. While it is zero, the effective
vesting stop is `end_time`. Revocation stores the current block timestamp,
freezes vesting there, and clears `revoker`. Renouncing revocation clears
`revoker` but leaves `disabled_at()` at zero and does not stop vesting.

## Configuration and accounting views

```vyper
recipient() -> address
token() -> address
start_time() -> uint256
end_time() -> uint256
cliff_length() -> uint256
total_locked() -> uint256
total_claimed() -> uint256
disabled_at() -> uint256
revoker() -> address
permissionless_claims() -> bool
claimable() -> uint256
locked() -> uint256
```

`total_locked` is the original principal, despite its historical name.
`claimable()` is vested but unclaimed principal at the effective stop.
`locked()` is principal that has not yet vested; it is not the contract's token
balance. `locked()` becomes zero immediately after revocation even when vested,
unclaimed tokens remain in the escrow.

## Claim

```vyper
claim(
    receiver: address,
    max_amount: uint256,
) -> uint256
```

Claims the smaller of currently claimable principal and `max_amount`, updates
`total_claimed`, transfers that amount to `receiver`, and returns the token
amount transferred. Passing `2**256 - 1` claims everything currently
available.

Authorization is:

| Caller | Receiver | Permissionless claims enabled | Result |
| --- | --- | --- | --- |
| `recipient` | Any address except zero or the escrow | Either | Allowed |
| Anyone else | `recipient` | Yes | Allowed |
| Anyone else | Any other address | Either | Rejected |
| Anyone else | `recipient` | No | Rejected |

Permissionless claiming grants execution, not routing. A zero-value claim
succeeds without changing accounting and emits no `Claim` event.

## Revoke

```vyper
revoke(receiver: address)
```

Only the current `revoker` may call. The function:

1. Requires a receiver other than zero or the escrow and a current timestamp
   before `end_time`.
2. Computes principal unvested at the current block timestamp.
3. Stores that timestamp in `disabled_at`.
4. Clears `revoker` before the external token transfer.
5. Transfers unvested principal to `receiver`.
6. Leaves vested, unclaimed principal for later recipient claims.
7. Emits `Revoked`.

Revocation is immediate, final, and cannot be scheduled for a future timestamp.

## Renounce revocation

```vyper
renounce_revocation()
```

Only the current `revoker` may call. It permanently clears `revoker` without
stopping vesting and emits `RevocationRenounced`. Subsequent revocation and
renunciation calls are unauthorized.

## Permissionless claiming

```vyper
set_permissionless_claims(enabled: bool)
```

Only `recipient` may call. It changes whether third parties may execute claims
to the recipient; it never permits a third party to choose another receiver.
The function emits `PermissionlessClaimsSet`.

## Events

```vyper
event Claim:
    receiver: indexed(address)
    amount: uint256

event Revoked:
    recipient: indexed(address)
    revoker: indexed(address)
    receiver: indexed(address)
    unvested_amount: uint256
    ts: uint256

event RevocationRenounced:
    revoker: indexed(address)

event PermissionlessClaimsSet:
    enabled: bool
```

`Claim.amount` and `Revoked.unvested_amount` are raw token units.

## Token behavior

The token must remain transferable and move the exact requested balance.
Pauses, blacklists, transfer fees, rebasing balances, and incompatible token
upgrades can block lifecycle operations and are unsupported.

Direct donations of the vested token do not increase `total_locked` or
recipient entitlement and cannot be recovered through this contract. Unrelated
tokens have no recovery method.
