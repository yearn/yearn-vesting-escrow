# Yearn Vesting Escrow

version 0.3-dev0

## Vesting Factory

- the factory is initialized with a template contract of `Vesting Escrow`
- `deploy_vesting_escrow`
    - arguments
        - `token: address` ERC20 funding token
            - the factory must have an `allowance` of at least `amount`
        - `recipient: address` vesting recipient
            - can be a smart contract in v0.3
        - `amount: uint256` total vesting amount
        - `vesting_duration: uint256` in seconds
        - `vesting_start: uint256 = block.timestamp` in unix epoch
            - can be in the past
        - `cliff_length: uint256 = 0` in seconds
            - must not exceed vesting duration
        - `open_claim: bool = True`
            - allows anyone to claim to recipient, use this for smart contract recipients
        - `admin: address = msg.sender`
            - this party can terminate and clawback the escrow before it fully vests
            - set to `empty(address)` to disable clawback, this can also be done later with `escrow`
    - actions
        - creates a new vesting escrow using `create_minimal_proxy_to`
        - funds it by transferring tokens from `msg.sender` to the newly created `escrow`
        - initializes the `escrow`
        - emits the creation parameters in `VestingEscrowCreated` event

