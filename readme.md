# Yearn Vesting Escrow

A modified version of [Curve Vesting Escrow](https://github.com/curvefi/curve-dao-contracts) contracts with added functionality:

- An escrow can have a `start_date` in the past.
- The first unlock can be delayed using `cliff_length`.
- An ability to `claim` partial amounts or use a different beneficiary account.
- An ability to `open_claim` and let anyone to claim for beneficiary recipient.
- An ability to terminate an escrow and choose beneficiary for the unvested tokens using `revoke`. The recipient is still entitled to the vested portion.
- An ability to use ERC20 non-compliant `token`, e.g. USDT.
- Factory admin controls removed, anyone can deploy escrows, funds are pulled instead of pushed.
- Factory emits an event which allows finding all the escrows deployed from it.

## Contracts

- [`VestingEscrowFactory`](contracts/VestingEscrowFactory.vy): Factory to deploy many simplified vesting contracts
- [`VestingEscrowSimple`](contracts/VestingEscrowSimple.vy): Simplified vesting contract that holds tokens for a single beneficiary

## Usage

```python
$ brownie console --network mainnet
funder = accounts.load(name)
factory = VestingEscrowFactory.at('0x98d3872b4025ABE58C4667216047Fe549378d90f', owner=funder)
factory.deploy_vesting_contract(token, recipient, amount, vesting_duration, vesting_start, cliff_length, open_claim, support_vyper, owner)
```

## Ethereum mainnet deployment

### v0.3.0

- `VestingEscrowFactory`:
- `VestingEscrowSimple`:

### v0.2.0

- `VestingEscrowFactory`: [0x98d3872b4025ABE58C4667216047Fe549378d90f](https://etherscan.io/address/0x98d3872b4025ABE58C4667216047Fe549378d90f#code)
- `VestingEscrowSimple`: [0xaB080A16007DC2E34b99F269a0217B4e96f88813](https://etherscan.io/address/0xaB080A16007DC2E34b99F269a0217B4e96f88813#code)

### v0.1.0

⚠️ This version has an [unpatched bug](https://github.com/banteg/yearn-vesting-escrow/security/advisories/GHSA-vpxq-238p-8q3m), do not call `renounce_ownership` on it.

- `VestingEscrowFactory`: [0xF124534bfa6Ac7b89483B401B4115Ec0d27cad6A](https://etherscan.io/address/0xF124534bfa6Ac7b89483B401B4115Ec0d27cad6A#code)
- `VestingEscrowSimple`: [0x9c351CabC5d9e1393678d221F84E6EE3D05c016F](https://etherscan.io/address/0x9c351cabc5d9e1393678d221f84e6ee3d05c016f#code)

## Ethereum Rinkeby testnet deployment

### v0.1.0

- `VestingEscrowFactory`: [0x2836925b66345e1c118ec87bbe44fce2e5a558f6](https://rinkeby.etherscan.io/address/0x2836925b66345e1c118ec87bbe44fce2e5a558f6#code)
- `VestingEscrowSimple`: [0x8bb4edaf9269a3427ede1d1ad1885f6f9d5731f5](https://rinkeby.etherscan.io/address/0x8bb4edaf9269a3427ede1d1ad1885f6f9d5731f5#code)

## Ethereum Ropsten testnet deployment

### v0.1.0

- `VestingEscrowFactory`: [0x8bb4edaf9269a3427ede1d1ad1885f6f9d5731f5](https://ropsten.etherscan.io/address/0x8bb4edaf9269a3427ede1d1ad1885f6f9d5731f5#code)
- `VestingEscrowSimple`: [0xd887a875f4bc3b2aa5928e46607b7a06facfe3d0](https://ropsten.etherscan.io/address/0xd887a875f4bc3b2aa5928e46607b7a06facfe3d0#code)
