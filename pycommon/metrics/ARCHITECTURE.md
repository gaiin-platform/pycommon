# Usage Tracker Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Lambda Invocation                        │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    @validated Decorator                          │
│                      (authz.py)                                  │
└─────────────────────────────────────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
    ┌────────┐         ┌────────────┐         ┌──────────┐
    │ Parse  │────────▶│ Get Claims │────────▶│ Validate │
    │ Token  │         │ (Auth)     │         │ Data     │
    └────────┘         └────────────┘         └──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ ⭐ START TRACKING   │◀──── Entry Point
                    │ (usage_tracker)     │
                    └─────────────────────┘
                               │
                               │ Creates tracking_context:
                               │ - start_time
                               │ - user
                               │ - operation
                               │ - endpoint
                               │ - request_id
                               │ - memory_limit
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Execute Handler     │
                    │ f(event, context,   │
                    │   user, name, data) │
                    └─────────────────────┘
                               │
                    ┌──────────┴─────────┐
                    │                    │
                    ▼                    ▼
              ┌──────────┐         ┌──────────┐
              │ Success  │         │  Error   │
              │ (200-399)│         │ (400+)   │
              └──────────┘         └──────────┘
                    │                    │
                    └──────────┬─────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ ⭐ END TRACKING     │◀──── Exit Point
                    │ (usage_tracker)     │
                    └─────────────────────┘
                               │
                               │ Creates LambdaExecutionMetrics:
                               │ - duration_ms
                               │ - status_code
                               │ - success (boolean)
                               │ - error_type
                               │ - estimated_cost_usd
                               │
                               ▼
                    ┌─────────────────────┐
                    │ ⭐ RECORD METRICS   │◀──── Storage Point
                    │ (usage_tracker)     │      (Fire & Forget)
                    └─────────────────────┘
                               │
                               ▼
                        ┌─────────────┐
                        │  DynamoDB   │
                        │   Table     │
                        └─────────────┘
                               │
                ┌──────────────┼──────────────┐
                ▼              ▼              ▼
         ┌──────────┐   ┌──────────┐  ┌──────────┐
         │   Cost   │   │  Usage   │  │Analytics │
         │ Analysis │   │ Reports  │  │Dashboards│
         └──────────┘   └──────────┘  └──────────┘
```

## Component Architecture

### 1. UsageTracker Class

```python
┌────────────────────────────────────────────┐
│           UsageTracker                     │
├────────────────────────────────────────────┤
│ Attributes:                                │
│  - table_name: str                         │
│  - enabled: bool                           │
│  - dynamodb: boto3.resource                │
│  - table: DynamoDB.Table                   │
├────────────────────────────────────────────┤
│ Methods:                                   │
│  + __init__(table_name, enabled)           │
│  + start_tracking(...) → Dict              │
│  + end_tracking(...) → Metrics             │
│  + record_metrics(metrics) → None          │
└────────────────────────────────────────────┘
```

### 2. LambdaExecutionMetrics Dataclass

```python
┌────────────────────────────────────────────┐
│      LambdaExecutionMetrics                │
├────────────────────────────────────────────┤
│ Timing:                                    │
│  - start_timestamp: datetime               │
│  - end_timestamp: datetime                 │
│  - duration_ms: float                      │
├────────────────────────────────────────────┤
│ Identity:                                  │
│  - user: str                               │
│  - account: str                            │
│  - api_key_id: Optional[str]               │
├────────────────────────────────────────────┤
│ Request:                                   │
│  - operation: str                          │
│  - endpoint: str                           │
│  - api_accessed: bool                      │
├────────────────────────────────────────────┤
│ Response:                                  │
│  - status_code: int                        │
│  - success: bool                           │
│  - error_type: Optional[str]               │
├────────────────────────────────────────────┤
│ Lambda Context:                            │
│  - request_id: Optional[str]               │
│  - memory_limit_mb: Optional[int]          │
│  - purpose: Optional[str]                  │
├────────────────────────────────────────────┤
│ Methods:                                   │
│  + estimated_cost_usd() → Decimal          │
│  + to_dynamodb_item() → Dict               │
└────────────────────────────────────────────┘
```

## Data Flow Sequence

### Success Path

```
Time    Component           Action                    Data
─────────────────────────────────────────────────────────────────
t0      Lambda              Invocation starts         event, context
t1      validated           Parse token               token
t2      validated           Get claims                claims dict
t3      validated           Validate data             validated data
t4      UsageTracker        start_tracking()          tracking_context
        │                   │
        │                   └─ Captures:
        │                      • start_time = now()
        │                      • user, operation
        │                      • endpoint, context
        │
t5      Handler             Execute f(...)            business logic
        │                   │
        │                   └─ Time passes...
        │                      Duration accumulates
        │
t6      Handler             Return result             result dict
t7      UsageTracker        end_tracking()            metrics object
        │                   │
        │                   └─ Calculates:
        │                      • duration_ms
        │                      • estimated_cost_usd
        │                      • success = True
        │
t8      UsageTracker        record_metrics()          DynamoDB write
        │                   │
        │                   └─ Fire-and-forget
        │                      (async, no blocking)
        │
t9      validated           Return response           HTTP response
```

### Error Path

```
Time    Component           Action                    Data
─────────────────────────────────────────────────────────────────
t0-t4   [Same as success path]
t5      Handler             Execute f(...)            
        │                   │
        │                   ├─ Error occurs!
        │                   │
        │                   └─ Exception raised
        │
t6      validated           Catch exception           HTTPException
t7      UsageTracker        end_tracking()            metrics object
        │                   │
        │                   └─ Captures:
        │                      • error_type
        │                      • success = False
        │                      • status_code = 4xx/5xx
        │
t8      UsageTracker        record_metrics()          DynamoDB write
t9      validated           Return error              HTTP error response
```

## Cost Calculation Flow

```
┌─────────────────────────────────────────────────────────────┐
│              Cost Calculation Pipeline                      │
└─────────────────────────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
    ┌─────────┐    ┌──────────┐    ┌─────────┐
    │ Memory  │    │ Duration │    │  Price  │
    │ (MB)    │    │  (ms)    │    │ (/GB-s) │
    └─────────┘    └──────────┘    └─────────┘
         │               │               │
         │               │               │
         └───────┬───────┴───────┬───────┘
                 │               │
                 ▼               ▼
          ┌────────────┐  ┌────────────┐
          │ memory_mb  │  │ duration_ms│
          │   ÷ 1024   │  │  ÷ 1000    │
          └────────────┘  └────────────┘
                 │               │
                 └───────┬───────┘
                         │
                         ▼
                  ┌─────────────┐
                  │  GB-seconds │
                  │   = m × d   │
                  └─────────────┘
                         │
                         ×  $0.0000166667
                         │
                         ▼
                  ┌─────────────┐
                  │ Cost (USD)  │
                  └─────────────┘
```

## DynamoDB Schema Design

### Primary Access Pattern: Query by Account

```
Table: usage-metrics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Partition Key: account (HASH)
Sort Key: timestamp (RANGE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Query Pattern:
  SELECT * FROM usage_metrics
  WHERE account = 'acct-123'
    AND timestamp BETWEEN '2025-01-01' AND '2025-01-31'
    
Use Case:
  → Monthly cost rollup per account
  → Account-level billing
```

### Secondary Access Pattern: Query by User

```
GSI: UserIndex
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Partition Key: user (HASH)
Sort Key: timestamp (RANGE)
Projection: ALL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Query Pattern:
  SELECT * FROM usage_metrics.UserIndex
  WHERE user = 'user-456'
    AND timestamp BEGINS_WITH '2025-01'
    
Use Case:
  → Per-user usage analysis
  → User-level cost allocation
```

### Tertiary Access Pattern: Query by API Key

```
GSI: ApiKeyIndex
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Partition Key: api_key_id (HASH)
Sort Key: timestamp (RANGE)
Projection: ALL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Query Pattern:
  SELECT * FROM usage_metrics.ApiKeyIndex
  WHERE api_key_id = 'key-789'
    AND timestamp BEGINS_WITH '2025-01'
    
Use Case:
  → API key usage tracking
  → Third-party integration monitoring
```

## Error Handling Strategy

```
┌──────────────────────────────────────────────────────┐
│            Error Handling Philosophy                 │
│                                                      │
│  "Metrics collection must NEVER break the main flow" │
└──────────────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   Disabled  │ │  Init Error │ │ Write Error │
│   Tracking  │ │             │ │             │
└─────────────┘ └─────────────┘ └─────────────┘
        │               │               │
        ▼               ▼               ▼
  Return empty    Log & disable   Log & continue
    dict {}        tracking         (fire & forget)
        │               │               │
        └───────────────┴───────────────┘
                        │
                        ▼
           ┌────────────────────────┐
           │ Lambda Continues       │
           │ Normally              │
           └────────────────────────┘
```

### Error Scenarios

1. **Tracking Disabled**
   - Environment var `ENABLE_USAGE_TRACKING=false`
   - Missing `USAGE_METRICS_DYNAMO_TABLE`
   - **Action**: Return immediately, no-op

2. **DynamoDB Connection Error**
   - During initialization
   - **Action**: Disable tracking, log warning, continue

3. **DynamoDB Write Error**
   - During `record_metrics()`
   - **Action**: Log error, don't raise, continue

4. **Missing Lambda Context Fields**
   - `memory_limit_in_mb` not available
   - **Action**: Store as `None`, calculate cost as $0

## Singleton Pattern

```
┌─────────────────────────────────────────┐
│        get_usage_tracker()              │
│                                         │
│  Global variable: _usage_tracker        │
└─────────────────────────────────────────┘
                  │
         ┌────────┴────────┐
         ▼                 ▼
    First Call        Subsequent Calls
         │                 │
         ▼                 ▼
  Create new          Return existing
  UsageTracker()      _usage_tracker
         │                 │
         └────────┬────────┘
                  │
                  ▼
         Same instance across
         all invocations
```

Benefits:
- Single DynamoDB client instance
- Shared configuration
- Reduced initialization overhead

## Performance Profile

```
Operation          Time      Notes
─────────────────────────────────────────────────────
Initialization     ~10ms     First call only (singleton)
start_tracking()   ~1ms      Dictionary creation
Handler execution  varies    Your business logic
end_tracking()     ~1ms      Dataclass creation + math
record_metrics()   ~0ms*     Async, non-blocking

*Actual DynamoDB write is ~10-50ms but doesn't block
─────────────────────────────────────────────────────
Total Overhead:    ~2-3ms    Per request
```

## Integration Checklist

- [ ] Create DynamoDB table with schema
- [ ] Set up GSIs (UserIndex, ApiKeyIndex)
- [ ] Configure IAM permissions (PutItem)
- [ ] Set environment variable `USAGE_METRICS_DYNAMO_TABLE`
- [ ] Import `get_usage_tracker` in authz.py
- [ ] Add tracking initialization in wrapper
- [ ] Add `start_tracking()` after validation
- [ ] Add `end_tracking()` + `record_metrics()` before return
- [ ] Add error tracking in exception handlers
- [ ] Deploy to test environment
- [ ] Verify metrics in DynamoDB
- [ ] Build cost analysis queries
- [ ] Set up CloudWatch dashboards
- [ ] Configure cost alerts

## Future Enhancements

### Phase 2: Batching
```
┌────────────┐
│ Collect N  │──▶ Batch write to DynamoDB
│ metrics in │    (more efficient for high volume)
│ memory     │
└────────────┘
```

### Phase 3: Real-time Aggregation
```
DynamoDB Stream ──▶ Lambda ──▶ Aggregate metrics
                              └─▶ Store in aggregation table
```

### Phase 4: Cost Alerting
```
DynamoDB Stream ──▶ Lambda ──▶ Check thresholds
                              └─▶ SNS notification
```
