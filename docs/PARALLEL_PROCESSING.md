# Parallel Processing in Initialization

This document describes the parallel processing implementation for the Google Drive RAG system's initialization process.

## Overview

The initialization process now supports parallel processing for email, schedule, and file embeddings creation. This significantly improves initialization speed while ensuring resource limits are respected across multiple users.

## Architecture

### Global Thread Pool Manager

The system uses a **singleton GlobalThreadPoolManager** that manages thread allocation across all users:

- **Per-user limit**: Each user can use up to `MAX_WORKERS_PER_USER` threads (default: 5)
- **Global limit**: Total threads across all users limited to `MAX_TOTAL_WORKERS` (default: 20)
- **Thread-safe**: All operations are protected by locks to prevent race conditions

### Configuration

Thread limits are configured via environment variables in `.env`:

```env
# Parallel Processing Configuration
MAX_WORKERS_PER_USER=5
MAX_TOTAL_WORKERS=20
```

### How It Works

1. **Worker Acquisition**: Before processing an item, the manager checks if a worker slot is available
2. **Global Limits**: Enforces both per-user and global thread limits
3. **Dynamic Allocation**: Workers are acquired and released dynamically as items are processed
4. **Fair Distribution**: Prevents any single user from monopolizing resources

## Implementation Details

### Thread Pool Manager (`thread_pool_manager.py`)

```python
class GlobalThreadPoolManager:
    - acquire_worker(user_id): Acquire a worker slot
    - release_worker(user_id): Release a worker slot
    - process_parallel(user_id, items, process_func): Process items in parallel
    - get_stats(): Get current worker statistics
```

### Parallel Processing Functions

#### Email Embeddings
Each email is processed in parallel to create 3 embedding types:
- `email_sum`: Full email information
- `email_context`: Full thread context
- `email_title`: Subject and sender/receiver info

#### Schedule Embeddings
Each calendar event is processed in parallel to create:
- `schedule_context`: Full schedule information

#### File Embeddings
Each file is processed in parallel:
1. Download file content
2. Process file (OCR for images, extraction for docs)
3. Create summary
4. Generate embedding with metadata

### Thread-Safe Progress Tracking

Progress updates are thread-safe using locks:

```python
progress_lock = threading.Lock()
processed_count = [0]
last_update_progress = [start_progress]

with progress_lock:
    processed_count[0] += 1
    current_progress = start_progress + int(processed_count[0] / total * progress_range)
    if current_progress - last_update_progress[0] >= 1:
        update_user_status(user_id, "processing", phase, current_progress)
        last_update_progress[0] = current_progress
```

## Benefits

### Performance Improvements

1. **Faster Initialization**: Multiple items processed simultaneously
2. **Better Resource Utilization**: CPU and network resources used efficiently
3. **Scalability**: Supports multiple users initializing concurrently

### Resource Control

1. **Prevents Overload**: Global limits prevent system resource exhaustion
2. **Fair Allocation**: Per-user limits ensure fair distribution
3. **Graceful Degradation**: If limits reached, processing waits for available slots

## Usage Examples

### Basic Usage (Automatic)

The parallel processing is automatic. No code changes needed for basic usage:

```python
# Parallel processing happens automatically
create_email_embeddings(user_id, emails, 60, 75)
create_schedule_embeddings(user_id, schedules, 75, 85)
create_file_embeddings(user_id, files, credentials, 85, 100)
```

### Monitoring Worker Stats

```python
from retrieval_service.thread_pool_manager import get_thread_pool_manager

manager = get_thread_pool_manager()
stats = manager.get_stats()
print(f"Active workers: {stats['active_workers']}/{stats['max_total_workers']}")
print(f"User workers: {stats['user_workers']}")
```

### Custom Parallel Processing

```python
from retrieval_service.thread_pool_manager import get_thread_pool_manager

def process_item(item):
    # Your processing logic
    return result

manager = get_thread_pool_manager()
results = manager.process_parallel(user_id, items, process_item, max_workers=5)
```

## Error Handling

The system includes comprehensive error handling:

1. **Item-Level Errors**: If one item fails, others continue processing
2. **Thread Errors**: Caught and logged without crashing the entire process
3. **Resource Errors**: Worker acquisition failures are handled gracefully

Example error handling in processing:

```python
def process_single_email(email):
    try:
        # Process email
        return embeddings
    except Exception as e:
        print(f"Error processing email {email_id}: {e}")
        return None  # Continues with other emails
```

## Performance Considerations

### Optimal Settings

For most deployments:
- **Small deployments** (1-5 users): `MAX_WORKERS_PER_USER=5`, `MAX_TOTAL_WORKERS=20`
- **Medium deployments** (5-20 users): `MAX_WORKERS_PER_USER=3`, `MAX_TOTAL_WORKERS=30`
- **Large deployments** (20+ users): `MAX_WORKERS_PER_USER=2`, `MAX_TOTAL_WORKERS=40`

### Bottlenecks

Common bottlenecks and solutions:

1. **API Rate Limits**: Gemini/OpenAI API calls may be rate-limited
   - Solution: Adjust worker counts to stay within API limits
   
2. **Database Connections**: Too many concurrent database operations
   - Solution: Reduce `MAX_TOTAL_WORKERS` if database issues occur
   
3. **Memory Usage**: Large files processed in parallel consume memory
   - Solution: Reduce `MAX_WORKERS_PER_USER` for file processing

## Debugging

### Enable Debug Logging

Add logging to monitor parallel processing:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Monitor Worker Allocation

```python
manager = get_thread_pool_manager()
stats = manager.get_stats()
print(f"Current stats: {stats}")
```

### Test with Single User

For testing, set conservative limits:

```env
MAX_WORKERS_PER_USER=2
MAX_TOTAL_WORKERS=5
```

## Future Enhancements

Potential improvements:

1. **Dynamic Scaling**: Adjust worker counts based on system load
2. **Priority Queues**: Prioritize certain users or item types
3. **Metrics Collection**: Track processing times and success rates
4. **Retry Logic**: Automatic retry for failed items
5. **Rate Limiting**: Built-in rate limiting for API calls

## Integration with DEBUG_MODE

Parallel processing works seamlessly with DEBUG_MODE:

```env
DEBUG_MODE=true
MAX_WORKERS_PER_USER=3
```

When DEBUG_MODE is enabled:
- Only latest 50 files are processed
- Parallel processing still applies to those 50 files
- Reduces both processing time AND API costs

## Troubleshooting

### Issue: Slow Initialization
**Solution**: Increase `MAX_WORKERS_PER_USER` if system resources allow

### Issue: Out of Memory
**Solution**: Decrease `MAX_WORKERS_PER_USER` or `MAX_TOTAL_WORKERS`

### Issue: API Rate Limit Errors
**Solution**: Decrease worker counts to reduce concurrent API calls

### Issue: Database Connection Errors
**Solution**: Reduce `MAX_TOTAL_WORKERS` to limit concurrent DB operations

## See Also

- [DEBUG_MODE.md](DEBUG_MODE.md) - Cost control during development
- [initialization_flow.md](initialization_flow.md) - Overall initialization process
