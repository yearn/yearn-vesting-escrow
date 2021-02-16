# Yearn Vesting Escrow

A modified version of [Curve Vesting Escrow](https://github.com/curvefi/curve-dao-contracts) contracts with added functionality:
- An escrow can have a `start_date` in the past.
- The first unlock can be delayed using `cliff_length`.
- An ability to `claim` partial amounts or use a different beneficiary account.
- An ability to terminate an escrow and clawback all the unvested tokens using `rug_pull`. The recipient is still entitled to the vested portion.
- Factory admin controls removed, anyone can deploy escrows, funds are pulled instead of pushed.
- Factory emits an event which allows finding all the escrows deployed from it.

## Contracts

* [`VestingEscrowFactory`](contracts/VestingEscrowFactory.vy): Factory to deploy many simplified vesting contracts
* [`VestingEscrowSimple`](contracts/VestingEscrowSimple.vy): Simplified vesting contract that holds tokens for a single beneficiary
