# Integration guide

This guide covers creation, discovery, lifecycle transactions, and migration to
the unreleased 0.4.0 ABI.

## Choose the escrow type

Use `deploy_vesting_contract` when the recipient should receive a fixed amount
of an ordinary ERC-20 token.

Use `deploy_erc4626_vesting` only when:

- the factory will be funded with ERC-4626 shares;
- vesting entitlement should be denominated in the underlying asset;
- yield must be separated from principal and sent to a fixed
  `yield_recipient`;
- the specific vault satisfies the requirements in
  [ERC-4626 accounting](erc4626.md).

Do not send vault shares through the standard path if the intended policy is to
separate yield. The standard escrow treats every funded share as recipient
principal.

## Create an escrow

### 1. Resolve policy explicitly

Before building the transaction, record:

- token or vault address;
- raw token amount or raw vault share amount;
- recipient;
- start timestamp, duration, and cliff length in seconds;
- whether permissionless principal claiming begins enabled;
- revoker, or zero for irrevocable vesting;
- ERC-4626 yield recipient, when applicable.

Display the derived end time and human-readable amounts for review. Do not
silently substitute the transaction sender for a role.

### 2. Approve the factory

The funder approves the factory, not the implementation or predicted proxy:

```text
standard: token.approve(factory, amount)
ERC-4626: vault.approve(factory, funded_shares)
```

The factory requires the new proxy's balance to increase by exactly the
requested amount. Fee-on-transfer assets revert.

### 3. Call one full factory signature

Use the exact 0.4.0 selector:

```text
deploy_vesting_contract(address,address,uint256,uint256,uint256,uint256,bool,address)

deploy_erc4626_vesting(address,address,uint256,uint256,uint256,uint256,bool,address,address)
```

There are no shorter default-argument overloads.

### 4. Read the creation event

Use the returned address and the matching creation event. Verify that every
event field equals the reviewed input. For ERC-4626, also show the emitted
`principal_assets`, which is the initialization-time asset value of the funded
shares.

The factory does not expose `escrows()` or `escrows_length()`.

## Index escrows

Index both factory event signatures from the factory's deployment block:

- `TokenVestingEscrowCreated`;
- `ERC4626VestingEscrowCreated`.

The first three fields of each event are indexed:

```text
standard: escrow, token, recipient
ERC-4626: escrow, vault, recipient
```

Store the complete non-indexed configuration with the event provenance. Handle
removed logs and replay a safety window after reorganizations. Do not infer the
contract kind from bytecode alone when the creation event is available.

Wavey's [open-source manager and
indexer](https://github.com/wavey0x/vesting-escrow-app) is a useful independent
reference for event-built discovery. Its hosted
[Vesting Escrow app](https://vest.wavey.info/) manages historical Yearn and
LlamaPay escrows. Support for 0.4.0 requires its new factory addresses and ABI.

## Read escrow state

For either escrow:

1. Read `recipient`, `revoker`, `start_time`, `end_time`, `cliff_length`,
   `disabled_at`, and `permissionless_claims`.
2. Treat `disabled_at == 0` as active, not as a stop at the Unix epoch.
3. If revoked, show the effective stop as `disabled_at`; otherwise show
   `end_time`.
4. Distinguish revocation from renunciation: both leave `revoker == 0`, but
   only revocation sets `disabled_at`.

For standard escrows, show `claimable()` and `locked()`. Do not label
`locked()` as contract balance.

For ERC-4626 escrows, always suffix displayed values with `assets` or `shares`.
Use:

```text
claimable_principal_assets()
preview_principal_claim(max_principal_assets)
claimable_yield_shares()
```

Refresh previews immediately before execution because vault conversions may
change between blocks. Do not submit a principal claim when its preview has
positive asset entitlement but zero output shares; the call would consume the
asset entitlement without making a share transfer.

## Claims

To claim everything currently available, pass `2**256 - 1` as the maximum:

```text
standard.claim(receiver, 2**256 - 1)
erc4626.claim_principal(receiver, 2**256 - 1)
```

The recipient may redirect its claim to any nonzero receiver. Automation acting
permissionlessly must use the stored recipient as receiver.

For ERC-4626:

- the maximum argument is in asset units;
- `preview_principal_claim` returns `(asset amount, share amount)`;
- `claim_principal` returns the share amount;
- the `PrincipalClaim` event records both.

`claim_yield()` needs no receiver argument. Anyone may trigger it, and shares
always go to the fixed yield recipient.

A standard claim whose computed token amount is zero succeeds without changing
accounting and emits no event. An ERC-4626 preview of `(0, 0)` behaves the same
way. A zero return value alone is not enough to make that inference for
ERC-4626 because the return unit is shares; always inspect both preview values.

## Revocation

Show the revoker both:

- the current vested entitlement that will remain for the recipient;
- the unvested token amount or share allocation sent to the chosen receiver.

Then call:

```text
escrow.revoke(receiver)
```

Revocation is immediate. There is no timestamp argument and no default
receiver. It cannot be called at or after the scheduled end.

For ERC-4626 escrows, revocation also transfers current yield to the fixed yield
recipient. Under loss, the share value sent to either principal side can be
less than its asset-denominated schedule amount.

Use `renounce_revocation()` when the policy decision is to make the active
escrow permanently irrevocable without stopping vesting.

## Transaction safety

An interface should:

- resolve the exact chain and factory address before encoding;
- fetch fresh escrow state and simulate every lifecycle transaction;
- display all destinations, raw units, and decoded human units;
- warn when a recipient is a contract whose ability to call or receive tokens
  has not been verified;
- warn when a revoker or yield recipient is zero or differs from the expected
  policy;
- wait for appropriate confirmation depth before treating creation as final;
- retain the transaction hash and log index with every indexed escrow.

An ERC-4626 interface should additionally show current share price, previewed
share output, yield shares, and any vault pause or upgrade risk available to
the integrator.

## Migrating from v0.3

Version 0.4.0 intentionally breaks the historical ABI. Do not replace an ABI
globally for existing addresses.

| v0.3 | v0.4.0 |
| --- | --- |
| `TARGET()` | `STANDARD_TARGET()` and `ERC4626_TARGET()` |
| `deploy_vesting_contract(... open_claim, support_vyper, owner)` plus overloads | One explicit standard deployment signature using `permissionless_claims` and `revoker` |
| No dedicated vault deployment | `deploy_erc4626_vesting(...)` |
| `owner()` | `revoker()` |
| `open_claim()` | `permissionless_claims()` |
| `unclaimed()` | `claimable()` for standard escrows |
| `claim(beneficiary, amount)` plus overloads | `claim(receiver, max_amount)` |
| `revoke(ts, beneficiary)` plus overloads | Immediate `revoke(receiver)` |
| `disown()` | `renounce_revocation()` |
| `set_open_claim(bool)` | `set_permissionless_claims(bool)` |
| `collect_dust(...)` | Removed |
| Factory-integrated Vyper donation | Removed |
| `VestingEscrowCreated` | Type-specific creation events |

Event field names and indexing also changed. Historical v0.1, v0.2, v0.3, and
LlamaPay escrows remain immutable and must continue to use their matching ABIs.
See the [deployment history](../readme.md#production-deployments).
