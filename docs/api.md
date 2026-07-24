# Contract API

The deployed 0.4.0 contracts have separate, self-contained API references:

| Contract | Ethereum mainnet | Reference |
| --- | --- | --- |
| `VestingEscrowFactory` | [`0xFbd9…0215`](https://etherscan.io/address/0xfbd94e2d6942d5b4ed0c5c9c43bded77a8f20215#code) | [Factory API](api/factory.md) |
| `VestingEscrowSimple` | [`0x4CaE…2388`](https://etherscan.io/address/0x4cae5c8d3fae0f1e7f005975cbfc0df1d4c32388#code) | [Standard ERC-20 escrow API](api/standard.md) |
| `VestingEscrow4626` | [`0x569C…665A`](https://etherscan.io/address/0x569c2e7045dcbef8b77b092d25dbbaf3a37e665a#code) | [ERC-4626 escrow API](api/erc4626.md) |

Each page documents the complete external surface, roles, authorization,
amount units, lifecycle behavior, and events for that contract. The
[ERC-4626 accounting guide](erc4626.md) separately derives the principal/yield,
gain/loss, and rounding model.

Version 0.4.0 is deployed and source-verified but has not received an
independent audit. Its release tag remains pending. Historical v0.x and
LlamaPay deployments use different ABIs.
