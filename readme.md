# StakeWise Vesting Escrow

A modified version of [Yearn Vesting Escrow](https://github.com/banteg/yearn-vesting-escrow) contracts with added functionality:
- Only `admin` of `VestingEscrowFactory` can create new vesting escrows.
- `VestingEscrowFactory` keeps track of all the created escrows for the beneficiary.
- `VestingEscrowFactory` has a `balanceOf` function for retrieving the total number of unclaimed tokens of the beneficiary.
  The retrieved amount can be used for counting user's locked tokens as an additional voting power.

## Contracts

- [`VestingEscrowFactory`](contracts/VestingEscrowFactory.vy): Factory to deploy many simplified vesting contracts
- [`VestingEscrowSimple`](contracts/VestingEscrowSimple.vy): Simplified vesting contract that holds tokens for a single beneficiary

## Usage

```python
$ brownie console --network mainnet
funder = accounts.load(name)
factory = VestingEscrowFactory.at('<factory address>', owner=funder)
factory.deploy_vesting_contract(token, recipient, amount, vesting_duration, vesting_start, cliff_length)
```
