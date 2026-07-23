# Yearn Vesting Escrow

Vesting escrows for standard ERC-20 tokens and ERC-4626 vault shares.

The unreleased version 2 has two dedicated implementations behind one factory:

- `VestingEscrowSimple.vy` vests a fixed amount of an ordinary ERC-20 token;
- `VestingEscrow4626.vy` vests principal denominated in the vault's underlying
  asset while holding and paying ERC-4626 shares;
- `VestingEscrowFactory.vy` deploys minimal proxies from separate immutable
  standard-token and ERC-4626 targets.

The factory exposes `deploy_vesting_contract()` for standard tokens and
`deploy_erc4626_vesting()` for vault shares. Both implementations share only
stateless vesting arithmetic through `modules/vesting_math.vy`; their storage,
external APIs, and accounting remain separate.

The ERC-4626 escrow records principal in underlying-asset units at
initialization. Its API makes units explicit:

- `claimable_principal_assets()` and `vested_principal_assets()` report assets;
- `claimable_shares()` and `locked_shares()` report vault shares;
- `claim_principal()` pays vested principal in shares;
- `claim_yield()` sends shares worth more than the remaining principal to a
  fixed `yield_recipient`, which is independent from the revocation owner;
- revocation returns unvested principal shares and sends available yield to the
  fixed yield recipient;
- vault losses are borne proportionally by outstanding principal without
  blocking claims.

Supported tokens must remain transferable and move the exact requested token
or share amount. Pauses, blacklists, transfer fees, and incompatible token or
vault upgrades are outside the accounting model and must be excluded during
deployment review.

ERC-4626 escrows target reviewed Yearn-style vaults with conventional share
precision. Each lifecycle transition can differ by less than one raw share due
to ERC-4626 floor rounding; the contract deliberately accepts that negligible
bound instead of maintaining cross-call rounding checkpoints. Coarse-share
vaults are outside the supported deployment policy.

## Development

The contracts use Vyper 0.4.3 and Titanoboa on Python 3.11:

```sh
uv sync --locked
uv run --locked vesting-escrow-compile
uv run --locked pytest tests/functional/ --gas-profile
uv run --locked pytest tests/integration/
```

Run the pinned real-vault smoke test with an archive-capable Ethereum RPC:

```sh
MAINNET_RPC=https://... uv run --locked vesting-escrow-fork-smoke
```

The smoke test defaults to sUSDS at Ethereum block `25,587,000`. Set
`MAINNET_BLOCK`, `ERC4626_VAULT`, `ERC4626_HOLDER`, and `ERC4626_AMOUNT` to use
another standards-compliant vault and matching pinned state.

After changing dependencies in `pyproject.toml`, regenerate the lock file with:

```sh
uv lock
```

## Development deployment

Deploy locally without a key:

```sh
uv run --locked vesting-escrow-deploy
```

For a development network, secrets are read only from the environment:

```sh
RPC_URL=https://... DEPLOYER_PRIVATE_KEY=... \
  uv run --locked vesting-escrow-deploy --expected-chain-id 11155111
```

Production deployment requires an independent audit, a reviewed deployment
manifest, source verification, and low-value standard-token and ERC-4626
canaries.

## Escrow manager

Wavey's [Vesting Escrow app](https://vest.wavey.info/) provides an interface to
find and manage escrows deployed by the current Yearn factory and the LlamaPay
v2 factory. The app and its Ethereum event indexer are
[open source](https://github.com/wavey0x/vesting-escrow-app).

## Production deployments

The `version() == 2` contracts on `master` have not yet been deployed or
audited. This contract version is separate from the historical v0.x release
tags below. Existing factories and escrows remain immutable and unaffected.

### [v0.3.0](https://github.com/yearn/yearn-vesting-escrow/tree/v0.3.0)

This is the current Yearn factory.

- Factory: [`0x200C92Dd85730872Ab6A1e7d5E40A067066257cF`](https://etherscan.io/address/0x200c92dd85730872ab6a1e7d5e40a067066257cf#code)
- Implementation: [`0x9692F652A3048eb7F5074e12B907F20d33F37a01`](https://etherscan.io/address/0x9692f652a3048eb7f5074e12b907f20d33f37a01#code)
- Audit: [MixBytes, 2023-10-13](https://github.com/yearn/yearn-security/tree/master/audits/20231013_Mixbytes_yearn_vesting_escrow)

### [LlamaPay v2](https://github.com/LlamaPay/yearn-vesting-escrow) (derived from v0.3.0)

LlamaPay forked this repository at
[v0.3.0 (`d14eed1`)](https://github.com/yearn/yearn-vesting-escrow/commit/d14eed16f5b131bc35c58df2b8b4a03427928ef1)
and retained its consumer interface. Its v2 adds an escrow registry, makes the
Vyper donation opt-in by default, and hardens revoke and dust handling.

- Factory: [`0xcf61782465Ff973638143d6492B51A85986aB347`](https://etherscan.io/address/0xcf61782465ff973638143d6492b51a85986ab347#code)
- Implementation: [`0x9dd5cF263327e2D6a608da8c30368Eb27514bAD2`](https://etherscan.io/address/0x9dd5cf263327e2d6a608da8c30368eb27514bad2#code)

### [v0.2.0](https://github.com/yearn/yearn-vesting-escrow/tree/v0.2.0)

- Factory: [`0x98d3872b4025ABE58C4667216047Fe549378d90f`](https://etherscan.io/address/0x98d3872b4025abe58c4667216047fe549378d90f#code)
- Implementation: [`0xaB080A16007DC2E34b99F269a0217B4e96f88813`](https://etherscan.io/address/0xab080a16007dc2e34b99f269a0217b4e96f88813#code)

### [v0.1.0](https://github.com/yearn/yearn-vesting-escrow/tree/v0.1.0)

> [!WARNING]
> This version has an
> [unpatched bug](https://github.com/banteg/yearn-vesting-escrow/security/advisories/GHSA-vpxq-238p-8q3m).
> Do not call `renounce_ownership`.

- Factory: [`0xF124534bfa6Ac7b89483B401B4115Ec0d27cad6A`](https://etherscan.io/address/0xf124534bfa6ac7b89483b401b4115ec0d27cad6a#code)
- Implementation: [`0x9c351CabC5d9e1393678d221F84E6EE3D05c016F`](https://etherscan.io/address/0x9c351cabc5d9e1393678d221f84e6ee3d05c016f#code)
