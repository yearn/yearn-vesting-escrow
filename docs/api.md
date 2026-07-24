# Contract API

This is the complete external surface of the unreleased 0.4.0 contracts. All
amounts are raw token units unless stated otherwise. All addresses supplied as
transfer destinations must be nonzero.

## `VestingEscrowFactory`

### Constructor and getters

```vyper
__init__(standard_target: address, erc4626_target: address)
STANDARD_TARGET() -> address
ERC4626_TARGET() -> address
```

Both targets must be distinct deployed contracts. They are immutable after
factory deployment.

### Standard escrow deployment

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

The caller is the funder and must approve the factory for at least `amount`
tokens. The factory transfers exactly `amount` tokens directly into the new
proxy before initializing it.

| Parameter | Meaning |
| --- | --- |
| `token` | ERC-20 token held and vested by the escrow. |
| `recipient` | Owner of vested principal. Must differ from zero, the factory, token, and revoker. |
| `amount` | Total principal in raw token units. Maximum `2**128 - 1`. |
| `vesting_duration` | Schedule length in seconds. Maximum `2**64 - 1`. |
| `vesting_start` | Unix timestamp at which linear vesting starts. |
| `cliff_length` | Seconds after `vesting_start` before accumulated vesting becomes claimable. |
| `permissionless_claims` | Whether third parties may trigger claims to `recipient`. |
| `revoker` | Revocation authority, or zero for an irrevocable escrow. |

### ERC-4626 escrow deployment

```vyper
deploy_erc4626_vesting(
    vault: address,
    recipient: address,
    funded_shares: uint256,
    vesting_duration: uint256,
    vesting_start: uint256,
    cliff_length: uint256,
    permissionless_claims: bool,
    revoker: address,
    yield_recipient: address,
) -> address
```

The caller must approve the factory for at least `funded_shares` vault shares.
`principal_assets` is fixed during initialization from
`vault.convertToAssets(funded_shares)`.

| Parameter | Meaning |
| --- | --- |
| `vault` | ERC-4626 share token held by the escrow. |
| `recipient` | Owner of vested principal. |
| `funded_shares` | Exact number of vault shares transferred into the new escrow. |
| `vesting_duration` | Schedule length in seconds. |
| `vesting_start` | Unix timestamp at which linear principal vesting starts. |
| `cliff_length` | Seconds after `vesting_start` before accumulated principal becomes claimable. |
| `permissionless_claims` | Whether third parties may trigger principal claims to `recipient`. |
| `revoker` | Revocation authority, or zero for an irrevocable escrow. |
| `yield_recipient` | Fixed destination for yield shares. |

### Creation events

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

Creation events contain the complete immutable deployment configuration and are
the canonical escrow index.

## `VestingEscrowSimple`

### Configuration and accounting views

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
`claimable` is vested but unclaimed principal. `locked` is principal not yet
vested; it is not the contract's token balance. `disabled_at` is zero before
revocation.

### Claim

```vyper
claim(receiver: address, max_amount: uint256) -> uint256
```

Claims at most the smaller of currently claimable principal and `max_amount`.
The return value and `Claim.amount` are token units.

The recipient may choose any nonzero receiver. A third party may call only when
permissionless claims are enabled, and then `receiver` must equal `recipient`.
Passing `2**256 - 1` claims the full currently available amount.

No `Claim` event is emitted when the computed amount is zero.

### Revoke and renounce

```vyper
revoke(receiver: address)
renounce_revocation()
```

Only the current revoker can call either function. `revoke` immediately freezes
vesting, clears the revoker, and transfers unvested principal to `receiver`.
Vested but unclaimed principal stays in the escrow for the recipient.

`renounce_revocation` clears the revoker without stopping vesting. Both changes
are permanent.

### Permissionless claiming

```vyper
set_permissionless_claims(enabled: bool)
```

Only the recipient can call this function. It changes execution permission, not
the recipient or permitted routing.

### Events

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

## `VestingEscrow4626`

### Configuration and accounting views

```vyper
recipient() -> address
vault() -> address
start_time() -> uint256
end_time() -> uint256
cliff_length() -> uint256
principal_assets() -> uint256
claimed_principal_assets() -> uint256
disabled_at() -> uint256
revoker() -> address
yield_recipient() -> address
permissionless_claims() -> bool

claimable_principal_assets() -> uint256
preview_principal_claim(max_principal_assets: uint256)
    -> (principal_assets: uint256, shares: uint256)
claimable_yield_shares() -> uint256
```

`principal_assets` is the initialization-time asset value of the funded shares.
It does not rebase with vault performance. `claimed_principal_assets` tracks
schedule entitlement consumed, while the escrow transfers vault shares.

`preview_principal_claim` returns both units explicitly. Its second value is the
expected share transfer under the vault's current conversion rate. A vault
state change between simulation and execution may change it.

If a very small partial claim previews positive principal assets but zero
shares, do not submit it. `claim_principal` consumes the previewed asset
entitlement even when share rounding produces no transfer. Wait for more
principal to vest or request a larger partial amount.

### Principal claim

```vyper
claim_principal(
    receiver: address,
    max_principal_assets: uint256,
) -> uint256
```

`max_principal_assets` and the event's `principal_assets` field are underlying
asset units. The return value is the number of vault shares transferred.

Authorization and permissionless routing are identical to the standard
escrow. Passing `2**256 - 1` claims all currently claimable principal.

No `PrincipalClaim` event is emitted if the share transfer is zero. This does
not by itself prove that `claimed_principal_assets` was unchanged; inspect both
values returned by `preview_principal_claim` before execution.

### Yield claim

```vyper
claim_yield() -> uint256
```

Callable by anyone after initialization. Transfers all currently claimable
yield shares to the fixed `yield_recipient` and returns the number of shares
transferred. It emits no event when the amount is zero.

### Revoke, renounce, and permissionless claiming

```vyper
revoke(receiver: address)
renounce_revocation()
set_permissionless_claims(enabled: bool)
```

`revoke` immediately sends the unvested principal share allocation to
`receiver`, sends current yield shares to `yield_recipient`, and preserves the
vested principal share allocation for later recipient claims.

`renounce_revocation` and `set_permissionless_claims` have the same authority
rules as the standard escrow.

### Events

```vyper
event PrincipalClaim:
    receiver: indexed(address)
    principal_assets: uint256
    shares: uint256

event YieldClaim:
    recipient: indexed(address)
    shares: uint256

event Revoked:
    recipient: indexed(address)
    revoker: indexed(address)
    receiver: indexed(address)
    unvested_principal_assets: uint256
    shares: uint256
    ts: uint256

event RevocationRenounced:
    revoker: indexed(address)

event PermissionlessClaimsSet:
    enabled: bool
```

The ERC-4626 `Revoked.shares` field is the actual share transfer to the
revocation receiver. `unvested_principal_assets` is the corresponding schedule
entitlement in asset units; under vault loss, the current asset value of those
shares may be lower.

## Initializer surface

Both implementations expose `initialize(...) -> bool` because ERC-1167 proxies
do not execute implementation constructors in proxy storage. Application
integrators should deploy through the factory, not call initializers directly.
Each proxy can initialize only once, and each implementation contract disables
its own initializer in its constructor.
