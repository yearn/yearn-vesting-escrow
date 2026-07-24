# Yearn Vesting Escrow

Vesting escrows for standard ERC-20 tokens and ERC-4626 vault shares.

> [!IMPORTANT]
> Version 0.4.0 is deployed on Ethereum mainnet from
> [frozen sources at `792c21b`](https://github.com/yearn/yearn-vesting-escrow/commit/792c21b230244943bee043505e6510d92737e01a).
> The release tag is pending post-deployment validation, and this version has
> not received an independent audit.

## Contracts

Version 0.4.0 has two dedicated escrow implementations behind one factory:

| Contract | Purpose |
| --- | --- |
| [`VestingEscrowSimple.vy`](contracts/VestingEscrowSimple.vy) | Vests a fixed amount of an ordinary ERC-20 token. |
| [`VestingEscrow4626.vy`](contracts/VestingEscrow4626.vy) | Vests principal denominated in underlying assets while holding and paying ERC-4626 shares. |
| [`VestingEscrowFactory.vy`](contracts/VestingEscrowFactory.vy) | Deploys funded minimal proxies from separate immutable implementation targets. |

The two escrows share a role model and linear schedule, but deliberately have
separate storage, APIs, and accounting. The standard escrow never needs to know
about shares or yield. The ERC-4626 escrow makes every asset/share boundary
explicit.

The factory exposes one full signature per deployment path:

```vyper
deploy_vesting_contract(
    token,
    recipient,
    amount,
    vesting_duration,
    vesting_start,
    cliff_length,
    permissionless_claims,
    revoker,
)

deploy_erc4626_vesting(
    vault,
    recipient,
    principal_assets,
    max_funded_shares,
    vesting_duration,
    vesting_start,
    cliff_length,
    permissionless_claims,
    revoker,
    yield_recipient,
)
```

ERC-4626 callers choose an exact asset-denominated principal and cap the shares
spent to fund it. `preview_erc4626_funding(vault, principal_assets)` quotes the
factory's current rounded-up share requirement.

Factory creation events are the canonical escrow index. The contracts do not
maintain a duplicate on-chain registry.

## Documentation

- [Architecture and security model](docs/architecture.md)
- [Contract API index](docs/api.md):
  [factory](docs/api/factory.md),
  [standard escrow](docs/api/standard.md), and
  [ERC-4626 escrow](docs/api/erc4626.md)
- [ERC-4626 accounting](docs/erc4626.md)
- [Integration and v0.3 migration guide](docs/integration.md)
- [Development and deployment guide](docs/deployment.md)

## Roles

| Role | Authority |
| --- | --- |
| `recipient` | Owns vested principal, may redirect its own claims, and controls permissionless claiming. |
| `revoker` | May stop vesting immediately and send unvested principal to an explicit receiver, or permanently renounce that authority. |
| `receiver` | A per-call transfer destination with no persistent authority. |
| `funder` | Supplies the initial tokens or shares and receives no implicit post-deployment rights. |
| `yield_recipient` | Fixed destination for all ERC-4626 yield shares. |

Permissionless claiming permits third-party execution, not third-party routing:
a caller other than the recipient can only send principal to the stored
recipient. ERC-4626 yield collection is permissionless because its destination
is fixed.

## Development

The contracts use Vyper 0.4.3 and Titanoboa on Python 3.11:

```sh
uv sync --locked
uv run --locked vesting-escrow-compile
uv run --locked pytest
uv run --locked pytest tests/functional/ --gas-profile
```

See the [deployment guide](docs/deployment.md) for local deployment, pinned
mainnet-fork testing, and the production checklist.

## Escrow manager

Wavey's [Vesting Escrow app](https://vest.wavey.info/) provides an interface to
find and manage escrows deployed by the historical Yearn v0.3.0 factory and the
LlamaPay v2 factory. The app and its Ethereum event indexer are
[open source](https://github.com/wavey0x/vesting-escrow-app).

The app is independent software. This contracts repository does not index or
operate deployed escrows.

## Production deployments

Every factory and escrow listed here is immutable. Integrators must select the
ABI matching each deployed version and factory address.

### [v0.4.0](https://github.com/yearn/yearn-vesting-escrow/commit/792c21b230244943bee043505e6510d92737e01a) (release tag pending)

The 0.4.0 contract sources are frozen at commit
[`792c21b`](https://github.com/yearn/yearn-vesting-escrow/commit/792c21b230244943bee043505e6510d92737e01a).
All three contracts have exact creation matches on Sourcify and are verified on
Etherscan. See the
[deployment manifest](deployments/ethereum/0.4.0.json) for transactions,
blocks, compiler settings, and bytecode hashes.

- Factory: [`0xFbd94e2D6942D5b4Ed0C5C9C43bded77a8f20215`](https://etherscan.io/address/0xfbd94e2d6942d5b4ed0c5c9c43bded77a8f20215#code)
- Standard implementation: [`0x4CaE5c8d3fAe0f1e7F005975cbFc0dF1D4C32388`](https://etherscan.io/address/0x4cae5c8d3fae0f1e7f005975cbfc0df1d4c32388#code)
- ERC-4626 implementation: [`0x569C2E7045dCbEf8B77b092D25dBBAf3A37E665A`](https://etherscan.io/address/0x569c2e7045dcbef8b77b092d25dbbaf3a37e665a#code)

### [v0.3.0](https://github.com/yearn/yearn-vesting-escrow/tree/v0.3.0)

This is the previous Yearn production factory.

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
