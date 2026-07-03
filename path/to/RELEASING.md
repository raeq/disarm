# Release Process

## Binding Publishers

The binding publishers (Node and Ruby) are triggered by the `release: published` event. However, due to a race condition, the binding publishers may fail if the core crate has not yet been published to crates.io.

To mitigate this issue, a polling step has been added to the binding publishers. This step waits for the core crate to be published to crates.io before building and publishing the binding.

## Polling Step

The polling step uses the `requests` library to make HTTP requests to the crates.io sparse index. The polling interval is set to 30 seconds, and the retry logic is implemented using a `while` loop.

## Fix-Forward Approach

The fix-forward approach is used to address this issue. This approach involves updating the `publish.yml` workflow to include the polling step for the binding publishers. The `RELEASING.md` document is also updated to reflect the new polling step and its purpose.