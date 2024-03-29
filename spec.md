# Yearn Vesting Escrow

version 0.3-dev0

## Vesting Factory

- `__init__`
    - arguments
        - `template: address` vesting escrow template
        - `vyper_donate: address` vyper safe for donations (vyperlang.eth on mainnet)
    - actions
        - save both as immutables
- `deploy_vesting_escrow`
    - arguments
        - `token: address` ERC20 funding token
        - `recipient: address` vesting recipient
            - can be a smart contract in v0.3
        - `amount: uint256` total vesting amount
        - `vesting_duration: uint256` in seconds
        - `vesting_start: uint256 = block.timestamp` in unix epoch
        - `cliff_duration: uint256 = 0` in seconds
        - `open_claim: bool = True`
            - allows anyone to claim to recipient, use this for smart contract recipients
        - `owner: address = msg.sender`
            - this party can terminate and clawback the escrow before it fully vests
            - set to `empty(address)` to disable clawback, this can also be done later with `escrow`
        - `support_vyper: uint256 = 100` in bps
    - constraints
        - `token`, `amount`
            - `token` that doesn't return True on transfer is supported via `default_return_value=True`
            - implicitly checked by `token` transfer
                - the funder must have a `token` balance of at least `amount`
                - the factory must have a `token` allowance of at least `amount`
        - `vesting_start + vesting_duration`
            - end time must be in the future
            - a regular transfer would suit better if it's in the past
        - `recipient`
            - must not be zero address
        - `owner`
            - can be zero address
        - `cliff_duration`
            - must not exceed vesting duration
        - `support_vyper`
            - check we are on mainnet in case someone deploys the contract on other networks
            - or ask vyper team to make a new multisig using create2 so they can resurrect it on any network
    - actions
        - create a new vesting escrow using `create_minimal_proxy_to`
        - fund it by transferring tokens from `msg.sender` to the newly created `escrow`
        - `initialize` the `escrow`
        - log the creation parameters in `VestingEscrowCreated` event
        - if `support_vyper > 0`, transfer additional tokens from `msg.sender` to `vyperlang.eth`


## Vesting Escrow

- global considerations
    - return an appropriate value or True from methods to make contract calls cheaper
    - use `default_return_value=True` for token transfers

- `__init__`
    - actions
        - template contract must be made defunct by storing `initialized` as True
- `initialize`
    - arguments
        - token
        - recipient
        - amount
        - start_time
        - end_time
        - cliff_duration
        - open_claim
        - owner
    - constraints
        - must not be initialized
        - must be funded
            - implicitly checked by only allowing creation from factory
    - actions
        - save the creation parameters to storage
        - store `initialized` as True
    - returns
        - True to make the call from a contract cheaper
- `claim`
    - arguments
        - `beneficiary: address = msg.sender` where to send funds to
        - `amount: uint256 = max_value(uint256)` optionally claim a fixed amount
    - constraints
        - recipient can claim to any beneficiary
        - allow anyone to call claim on behalf of receipient if `open_claim` is True
        - the `amount` is limited by the maximum amount claimable
    - actions
        - `total_claimed` is updated
        - transfer tokens to beneficiary, use `default_return_value=True`
        - log `Claim` with beneficiary and claimed amount
    - returns
        - amount claimed
- `revoke` (previously `rug_pull`)
    - arguments
        - `time: uint256 = block.timestamp` optionally terminate at a date and clawback lower amount
        - `beneficiary: address` where to send the clawed back amount
            - one use case could be to reward the recipient early, another is to transfer to treasury and not have owner handle to funds
    - constraints
        - can only be called by `owner`
        - time must be now or in the future
        - time must not exceed vesting end time
        - claw back only the non-vested amount, so the time of the last claim doesn't matter
    - actions
        - `disabled_at` is set to `time`
        - owner is set to `empty(address)`
        - the amount of tokens is determined as tokens still locked at `time`
        - tokens are transferred to `owner`
        - log `Revoked(owner, beneficiary, amount, time)`
        - log `Disowned(owner)`
- `disown` (previously `set_owner`)
    - arguments
        - none
    - constraints
        - can only be called by `owner`
    - actions
        - set owner to `empty(address)`
        - log `Disowned(owner)`
- `collect_dust`
    - arguments
        - `token: address` dust token to claim
        - `beneficiary: address = msg.sender` where to send tokens to
    - constraints
        - recipient can claim to any beneficiary
        - if beneficiary is the recipient and `open_claim` is True, allow anyone to claim
        - if the token is the vested token itself, the amount is determined as token balance of the contract minus the still locked portion of the vesting
        - for all other tokens, the full balance is sent
    - actions
        - send tokens to the beneficiary
