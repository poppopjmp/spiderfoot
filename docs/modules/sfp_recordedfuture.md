# Recorded Future Module Documentation

## Overview

The `sfp_recordedfuture` module integrates Recorded Future's Vulnerability Database API with SpiderFoot. This module allows you to query vulnerability data from Recorded Future and process the results to notify listeners of relevant events, such as `VULNERABILITY_DISCLOSURE`.

## Configuration Options

The `sfp_recordedfuture` module provides the following configuration options:

- `api_key`: Recorded Future API key.
- `verify`: Verify host names resolve.

## Usage

To use the `sfp_recordedfuture` module, follow these steps:

1. Obtain an API key from Recorded Future by visiting their website, registering for an account, and generating an API key.
2. Configure the `sfp_recordedfuture` module with the obtained API key and other desired options.
3. Run a SpiderFoot scan with the `sfp_recordedfuture` module enabled.

## Example

Here is an example of how to configure and use the `sfp_recordedfuture` module:

```python
# Configuration options
options = {
    'api_key': 'your_recorded_future_api_key',
    'verify': True
}

# Create a SpiderFoot instance
sf = SpiderFoot(options)

# Create and configure the sfp_recordedfuture module
module = sfp_recordedfuture()
module.setup(sf, options)

# Define a target and an event
target_value = 'example.com'
target_type = 'DOMAIN_NAME'
target = SpiderFootTarget(target_value, target_type)
sf.target = target

event_type = 'DOMAIN_NAME'
event_data = 'example.com'
event_module = 'test_module'
source_event = SpiderFootEvent(event_type, event_data, event_module, None)

# Handle the event with the sfp_recordedfuture module
module.handleEvent(source_event)
```

## References

- [Recorded Future API Documentation](https://support.recordedfuture.com/hc/en-us/articles/360035531473-API-Documentation)
- [Recorded Future Website](https://www.recordedfuture.com/)
