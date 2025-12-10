# Integration Guide: Usage Tracker with `authz.py`

This guide shows exactly how to integrate the usage tracker into the `validated` decorator in `authz.py`.

## Step-by-Step Integration

### Step 1: Add Import at Top of `authz.py`

Add this import after the existing imports (around line 46):

```python
from pycommon.metrics import get_usage_tracker
```

### Step 2: Modify the `validated` Decorator Function

The `validated` decorator wrapper function needs to be modified at three key points:

#### Point A: Initialize Tracker (Line ~794)

Add after `def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:`:

```python
def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    # Initialize usage tracker
    tracker = get_usage_tracker()
    tracking_context = {}
    
    try:
```

#### Point B: Start Tracking (Line ~839)

Add after the data dictionary is set up but BEFORE calling `f()`:

```python
# Existing code (line ~839)
data["purpose"] = claims.get("purpose")
logger.debug("Data dictionary setup complete, calling main function...")

# ADD THIS - Start tracking
tracking_context = tracker.start_tracking(
    user=current_user,
    operation=op,
    endpoint=name,
    api_accessed=api_accessed,
    context=context,
)

# Existing code (line ~841)
result = f(event, context, current_user, name, data)
```

#### Point C: End Tracking and Record (Line ~843-847)

Replace the existing return statement with end tracking logic:

```python
# OLD CODE:
# result = f(event, context, current_user, name, data)
# logger.debug("Main function completed successfully")
# 
# return {
#     "statusCode": 200,
#     "body": json.dumps(result, cls=CustomPydanticJSONEncoder),
# }

# NEW CODE:
result = f(event, context, current_user, name, data)
logger.debug("Main function completed successfully")

# Create response dictionary
result_dict = {
    "statusCode": 200,
    "body": json.dumps(result, cls=CustomPydanticJSONEncoder),
}

# End tracking and record metrics
metrics = tracker.end_tracking(
    tracking_context=tracking_context,
    result=result_dict,
    claims=claims,
    error_type=None,
)
tracker.record_metrics(metrics)

return result_dict
```

#### Point D: Track Errors (Line ~848-859)

Add tracking to the exception handlers:

```python
except HTTPException as e:
    logger.error(f"HTTPException caught: {e.status_code} - {e}")
    
    result_dict = {
        "statusCode": e.status_code,
        "body": json.dumps({"error": f"Error: {e.status_code} - {e}"}),
    }
    
    # ADD THIS - Track failed request
    if tracking_context:
        metrics = tracker.end_tracking(
            tracking_context=tracking_context,
            result=result_dict,
            claims=claims if 'claims' in locals() else {"account": "unknown"},
            error_type=type(e).__name__,
        )
        tracker.record_metrics(metrics)
    
    return result_dict

except Exception as e:
    logger.error(f"Unexpected exception caught: {type(e).__name__} - {e}")
    import traceback
    logger.error(f"Traceback: {traceback.format_exc()}")
    
    # ADD THIS - Track unexpected errors
    if tracking_context:
        result_dict = {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }
        metrics = tracker.end_tracking(
            tracking_context=tracking_context,
            result=result_dict,
            claims=claims if 'claims' in locals() else {"account": "unknown"},
            error_type=type(e).__name__,
        )
        tracker.record_metrics(metrics)
    
    raise
```

## Complete Modified `validated` Function

Here's the complete modified function for reference:

```python
def validated(
    op: str,
    validate_body: bool = True,
) -> Callable:
    """Decorator to validate input data and permissions for an API operation.

    Args:
        op (str): The operation being performed.
        validate_body (bool): Whether to validate the request body.

    Returns:
        Callable: The decorated function.

    Note:
        Uses global _validate_rules and _permission_checker set
        via setup_validated()
    """

    def decorator(f: Callable) -> Callable:
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            # Initialize usage tracker
            tracker = get_usage_tracker()
            tracking_context = {}
            
            try:
                token = _parse_token(event)
                api_accessed = token[:4] == "amp-"

                claims = (
                    api_claims(event, context, token)
                    if api_accessed
                    else get_claims(token)
                )

                current_user = claims["username"]
                logger.info(f"User: {current_user}")
                if current_user is None:
                    raise HTTPUnauthorized("User not found.")

                logger.debug("Prior to call _parse_and_validate...")
                logger.debug(
                    f"Validation rules available: {_validate_rules is not None}"
                )
                logger.debug(
                    f"Permission checker available: {_permission_checker is not None}"
                )

                [name, data] = _parse_and_validate(
                    current_user,
                    event,
                    op,
                    api_accessed,
                    _validate_rules or {},
                    validate_body,
                    _permission_checker,
                )
                logger.debug(f"_parse_and_validate completed successfully. name={name}")

                logger.debug("Setting up data dictionary...")
                data["access_token"] = token
                data["account"] = claims["account"]
                data["api_key_id"] = claims.get("api_key_id")
                data["rate_limit"] = claims["rate_limit"]
                data["api_accessed"] = api_accessed
                data["allowed_access"] = claims["allowed_access"]
                data["purpose"] = claims.get("purpose")
                logger.debug("Data dictionary setup complete, calling main function...")

                # START TRACKING - after auth, before execution
                tracking_context = tracker.start_tracking(
                    user=current_user,
                    operation=op,
                    endpoint=name,
                    api_accessed=api_accessed,
                    context=context,
                )

                result = f(event, context, current_user, name, data)
                logger.debug("Main function completed successfully")

                # Create response dictionary
                result_dict = {
                    "statusCode": 200,
                    "body": json.dumps(result, cls=CustomPydanticJSONEncoder),
                }

                # END TRACKING - after execution, before return
                metrics = tracker.end_tracking(
                    tracking_context=tracking_context,
                    result=result_dict,
                    claims=claims,
                    error_type=None,
                )
                tracker.record_metrics(metrics)

                return result_dict

            except HTTPException as e:
                logger.error(f"HTTPException caught: {e.status_code} - {e}")
                
                result_dict = {
                    "statusCode": e.status_code,
                    "body": json.dumps({"error": f"Error: {e.status_code} - {e}"}),
                }
                
                # Track failed request
                if tracking_context:
                    metrics = tracker.end_tracking(
                        tracking_context=tracking_context,
                        result=result_dict,
                        claims=claims if 'claims' in locals() else {"account": "unknown"},
                        error_type=type(e).__name__,
                    )
                    tracker.record_metrics(metrics)
                
                return result_dict

            except Exception as e:
                logger.error(f"Unexpected exception caught: {type(e).__name__} - {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                
                # Track unexpected errors
                if tracking_context:
                    result_dict = {
                        "statusCode": 500,
                        "body": json.dumps({"error": "Internal server error"}),
                    }
                    metrics = tracker.end_tracking(
                        tracking_context=tracking_context,
                        result=result_dict,
                        claims=claims if 'claims' in locals() else {"account": "unknown"},
                        error_type=type(e).__name__,
                    )
                    tracker.record_metrics(metrics)
                
                raise

        return wrapper

    return decorator
```

## Testing the Integration

### 1. Unit Test

Create a test that verifies tracking is called:

```python
from unittest.mock import Mock, patch

@patch('pycommon.authz.get_usage_tracker')
def test_validated_tracks_usage(mock_get_tracker):
    # Setup mock tracker
    mock_tracker = Mock()
    mock_get_tracker.return_value = mock_tracker
    mock_tracker.start_tracking.return_value = {"start_time": datetime.now()}
    
    # Create decorated function
    @validated(op="test_op")
    def test_handler(event, context, user, name, data):
        return {"result": "success"}
    
    # Call it
    event = {
        "headers": {"Authorization": "Bearer valid_token"},
        "body": json.dumps({}),
        "path": "/test"
    }
    context = Mock()
    
    result = test_handler(event, context)
    
    # Verify tracking was called
    assert mock_tracker.start_tracking.called
    assert mock_tracker.end_tracking.called
    assert mock_tracker.record_metrics.called
```

### 2. Integration Test

Deploy to a test Lambda and verify DynamoDB entries:

```python
import boto3

def verify_metrics_recorded(account_id: str, start_time: str):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('usage-metrics-table')
    
    response = table.query(
        KeyConditionExpression=Key('account').eq(account_id) & 
                              Key('timestamp').begins_with(start_time)
    )
    
    assert len(response['Items']) > 0
    item = response['Items'][0]
    
    assert 'duration_ms' in item
    assert 'estimated_cost_usd' in item
    assert item['success'] in [True, False]
    
    print(f"✓ Metrics recorded: {item}")
```

## Environment Setup

Don't forget to set up the environment variables:

```bash
# In your Lambda environment or .env file
export USAGE_METRICS_DYNAMO_TABLE=my-usage-metrics-table
export ENABLE_USAGE_TRACKING=true  # Optional, defaults to true
```

## Performance Impact

Expected overhead per request:
- **Start tracking**: ~1ms
- **End tracking**: ~1ms  
- **Record metrics**: Async (non-blocking)
- **Total impact**: ~2-3ms per request

For a typical Lambda with 100ms execution time, this is a 2-3% overhead.

## Rollback Plan

If you need to disable tracking without code changes:

```bash
export ENABLE_USAGE_TRACKING=false
```

Or remove the import and tracking code (it's isolated to 4 locations).

## Monitoring

After deployment, monitor:

1. **Lambda Duration**: Should increase by <5ms
2. **Lambda Errors**: Should not increase
3. **DynamoDB Write Capacity**: Plan for 1 write per Lambda invocation
4. **CloudWatch Logs**: Search for "usage_tracker" to see tracking logs

Example CloudWatch Insights query:

```
fields @timestamp, @message
| filter @message like /usage_tracker/
| filter @message like /Recorded metrics/
| stats count() by bin(5m)
```

## Next Steps

1. Deploy the code changes to `authz.py`
2. Set up the DynamoDB table (see README.md for schema)
3. Configure environment variables
4. Deploy to a test environment first
5. Verify metrics are being recorded
6. Build dashboards/queries for cost analysis
7. Set up alerts for cost thresholds
