# Yearn Vesting Escrow

Vesting escrows for standard ERC-20 tokens and optional ERC-4626 vault-share
principal accounting.

The unreleased version 2 contracts preserve the version 1 lifecycle while
adding an opt-in `yield_to_owner` mode:

- funding and payouts remain in the supplied ERC-20 token;
- in yield mode that token is an ERC-4626 wrapper share;
- the recipient receives vested principal shares;
- `claim_yield()` sends the original owner only shares representing value above
  remaining principal;
- revocation returns unvested principal shares and any available yield;
- vault losses are borne proportionally by outstanding principal without
  blocking claims;
- `claim_yield()` is permissionless, but always pays the fixed original owner.

Supported tokens must remain transferable and move the exact requested token
or share amount. Pauses, blacklists, transfer fees, and incompatible token or
vault upgrades are outside the accounting model and must be excluded during
deployment review.

Yield mode targets reviewed Yearn-style vaults with conventional share
precision. Each lifecycle transition can differ by less than one raw share due
to ERC-4626 floor rounding; the contract deliberately accepts that negligible
bound instead of maintaining cross-call rounding checkpoints. Coarse-share
vaults are outside the supported deployment policy.

`VestingEscrowSimple.vy` is the sole implementation for both modes.
`VestingEscrowFactory.vy` funds and initializes minimal proxies of that target.

## Development

The contracts use Vyper 0.4.3 and Titanoboa on Python 3.11:

```sh
./setup-python.sh
.venv/bin/python scripts/compile.py
.venv/bin/pytest tests/functional/ --gas-profile
.venv/bin/pytest tests/integration/
```

Run the pinned real-vault smoke test with an archive-capable Ethereum RPC:

```sh
MAINNET_RPC=https://... .venv/bin/python scripts/fork_smoke.py
```

The smoke test defaults to sUSDS at Ethereum block `25,587,000`. Set
`MAINNET_BLOCK`, `ERC4626_VAULT`, `ERC4626_HOLDER`, and `ERC4626_AMOUNT` to use
another standards-compliant vault and matching pinned state.

After changing `requirements.in`, regenerate the lock file with:

```sh
./update-lock.sh
```

## Development deployment

Deploy locally without a key:

```sh
.venv/bin/python scripts/deploy.py
```

For a development network, secrets are read only from the environment:

```sh
RPC_URL=https://... DEPLOYER_PRIVATE_KEY=... \
  .venv/bin/python scripts/deploy.py --expected-chain-id 11155111
```

Production deployment requires an independent audit, a reviewed deployment
manifest, source verification, and low-value standard-token and ERC-4626
canaries.

## Deployed version 1

The audited version 1 contracts remain immutable and unaffected:

- Factory: [`0x200C92Dd85730872Ab6A1e7d5E40A067066257cF`](https://etherscan.io/address/0x200c92dd85730872ab6a1e7d5e40a067066257cf#code)
- Implementation: [`0x9692F652A3048eb7F5074e12B907F20d33F37a01`](https://etherscan.io/address/0x9692f652a3048eb7f5074e12b907f20d33f37a01#code)
- Audit: [MixBytes, 2023-10-13](https://github.com/yearn/yearn-security/tree/master/audits/20231013_Mixbytes_yearn_vesting_escrow)

Version 2 has not yet been deployed or audited.
