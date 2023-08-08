# Yearn Vesting Escrow

version 0.3-dev0

## Vesting Factory

- the factory is initialized with a template contract of `Vesting Escrow`
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
        - `admin: address = msg.sender`
            - this party can terminate and clawback the escrow before it fully vests
            - set to `empty(address)` to disable clawback, this can also be done later with `escrow`
    - constraints
        - `token`, `amount`
            - `token` that doesn't return True on transfer is supported via `default_return_value=True`
            - implicitly checked by `token` transfer
                - the funder must have a `token` balance of at least `amount`
                - the factory must have a `token` allowance of at least `amount`
        - `vesting_start`
            - can be in the past
        - `cliff_duration`
            - must not exceed vesting duration
    - actions
        - create a new vesting escrow using `create_minimal_proxy_to`
        - fund it by transferring tokens from `msg.sender` to the newly created `escrow`
        - `initialize` the `escrow`
        - log the creation parameters in `VestingEscrowCreated` event


## Vesting Escrow

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
        - admin
    - constraints
        - must not be initialized
        - must be called from the factory
            - TODO: needs to know the factory? tango with deploy.
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
            - TODO: should we disallow claiming to [empty(address), self, token]
        - if beneficiary is the recipient and `open_claim` is True, allow anyone to claim
        - the `amount` is limited by the maximum amount claimable
    - actions
        - `total_claimed` is updated
        - transfer tokens to beneficiary, use `default_return_value=True`
        - log `Claim` with beneficiary and claimed amount
    - returns
        - amount claimed
- `terminate`
    - arguments
        - `time: uint256 = block.timestamp` optionally terminate at a date and clawback lower amount
        - TODO: should we add a `recipient` here too? what could be the use case?
    - constraints
        - can only be called by `admin`
        - time must be now or in the future
        - time must not exceed vesting end time
    - actions
        - `disabled_at` is set to `time`
        - admin is set to `empty(address)`
        - the amount of tokens is determined as tokens still locked at `time`
        - tokens are transferred to `admin`
        - log `VestingTerminated(self.recipient, self.admin, rugged, time)`
- `set_admin`
- `collect_dust`
- `unclaimed`
- `locked`
