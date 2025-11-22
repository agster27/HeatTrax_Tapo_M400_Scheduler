# Implementation: Shared Event Loop for python-kasa Device Operations

## Overview
This document describes the implementation of shared event loop infrastructure to prevent python-kasa async errors in the HeatTrax Scheduler.

## Problem Statement

### Symptoms
When the Flask web server queried device status, the following errors occurred intermittently:

```
RuntimeError: Timeout context manager should be used inside a task
SmartErrorCode.INTERNAL_QUERY_ERROR: -100001
Error querying 10.0.50.74 for modules 'Time, ChildDevice, DeviceModule, Matter' after first update
```

### Root Cause
The scheduler created python-kasa device objects (`ManagedDevice` instances via `kasa.Discover.discover_single()`) on its main event loop. However, Flask request handlers created **new, ad-hoc event loops** to call async methods like `get_all_devices_status()` and `get_device_expectations()`.

Python-kasa's timeout management uses asyncio context managers that expect to run in the same event loop where the device was created. When devices were accessed from a different loop, these context managers failed with the "Timeout context manager should be used inside a task" error.

## Solution Architecture

### Core Principle
**All python-kasa device I/O must run on a single, shared asyncio event loop.**

### Implementation Components

#### 1. Scheduler Event Loop Storage (`scheduler_enhanced.py`)

**Added in `__init__`:**
```python
# Event loop reference for thread-safe async operations
# This will be set in run() and used by web server to avoid creating ad-hoc loops
# for python-kasa device operations. All kasa device I/O must run on the same loop
# to prevent "Timeout context manager should be used inside a task" errors.
self.loop = None
```

**Modified `run()` method:**
```python
async def run(self):
    """Run the main scheduler loop."""
    # Capture the running event loop for thread-safe access from web server
    # This allows web server threads to execute async kasa operations on this loop
    self.loop = asyncio.get_running_loop()
    self.logger.info(f"Scheduler event loop initialized: {self.loop}")
    
    await self.initialize()
    # ... rest of run() implementation
```

**Added helper method:**
```python
def run_coro_in_loop(self, coro):
    """
    Execute a coroutine on the scheduler's event loop from another thread.
    
    This method allows the Flask web server (running in a separate thread) to safely
    execute async python-kasa device operations on the scheduler's event loop.
    All kasa device I/O must run on the same asyncio event loop to avoid runtime errors
    such as "Timeout context manager should be used inside a task" and INTERNAL_QUERY_ERROR.
    
    Args:
        coro: Coroutine to execute on the scheduler's event loop
        
    Returns:
        Result of the coroutine execution
        
    Raises:
        RuntimeError: If the scheduler loop is not initialized
    """
    if self.loop is None:
        raise RuntimeError(
            "Scheduler event loop not initialized. "
            "Ensure the scheduler is running before calling this method."
        )
    
    # Use asyncio.run_coroutine_threadsafe to schedule the coroutine on the scheduler's loop
    # and block until it completes
    future = asyncio.run_coroutine_threadsafe(coro, self.loop)
    return future.result()
```

#### 2. Web Server Updates (`web_server.py`)

**Updated `/api/devices/status` endpoint:**
```python
# Check if scheduler has the run_coro_in_loop method (for thread-safe async execution)
if hasattr(self.scheduler, 'run_coro_in_loop'):
    # Use the scheduler's event loop to avoid python-kasa async issues
    # This prevents "Timeout context manager should be used inside a task" errors
    try:
        devices_status = self.scheduler.run_coro_in_loop(
            self.scheduler.device_manager.get_all_devices_status()
        )
    except RuntimeError as e:
        logger.error(f"Scheduler loop not available: {e}")
        return jsonify({
            'error': 'Async operations not available',
            'details': str(e)
        }), 500
else:
    # Fallback for backward compatibility (though this may cause kasa errors)
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        devices_status = loop.run_until_complete(
            self.scheduler.device_manager.get_all_devices_status()
        )
    finally:
        loop.close()
```

**Updated `_get_system_status()` method:**
```python
# Get device expectations for health monitoring
if hasattr(self.scheduler, 'get_device_expectations'):
    try:
        # Use scheduler's event loop if available to avoid python-kasa async issues
        if hasattr(self.scheduler, 'run_coro_in_loop'):
            try:
                expectations = self.scheduler.run_coro_in_loop(
                    self.scheduler.get_device_expectations()
                )
                status['device_expectations'] = expectations
            except RuntimeError as e:
                logger.warning(f"Scheduler loop not available: {e}")
                status['device_expectations'] = []
        else:
            # Fallback for backward compatibility
            # ... (similar pattern)
```

#### 3. Device Control UI Error Messaging

The error handling code was already present in the UI (lines 1289-1295 of web_server.py):

```javascript
if (device.error) {
    html += `<div style="color: #e74c3c; margin-top: 8px;"><strong>Error:</strong> ${device.error}</div>`;
    // Add helper note for kasa/tapo library errors
    if (device.error.includes('INTERNAL_QUERY_ERROR')) {
        html += `<div style="color: #e74c3c; margin-top: 4px; font-size: 12px; font-style: italic;">Note: This error is reported by the underlying python-kasa/Tapo library, not the scheduler itself.</div>`;
    }
}
```

This provides users with context when they see low-level python-kasa errors in the Device Control UI.

## Thread Safety

### How It Works

1. **Scheduler Thread**: Runs the main event loop (`self.loop`) where all device objects are created and managed
2. **Flask Threads**: Handle HTTP requests in separate threads
3. **Bridge**: `run_coro_in_loop()` uses `asyncio.run_coroutine_threadsafe()` to safely execute coroutines on the scheduler's loop from Flask threads

### Synchronization
- `asyncio.run_coroutine_threadsafe()` is thread-safe by design
- Returns a `concurrent.futures.Future` that blocks until the coroutine completes
- No manual locks or synchronization primitives needed

## Error Handling

### RuntimeError Handling
If `run_coro_in_loop()` is called before the scheduler initializes its loop:
```python
RuntimeError: Scheduler event loop not initialized. 
              Ensure the scheduler is running before calling this method.
```

The web server catches this and returns HTTP 500:
```json
{
  "error": "Async operations not available",
  "details": "Scheduler event loop not initialized..."
}
```

### Backward Compatibility
The code includes `hasattr()` checks for the new method, with fallback to the old behavior:
- If `run_coro_in_loop` exists: Use it (preferred)
- If not: Create ad-hoc event loop (old behavior, may cause kasa errors)

This ensures the code works even if the scheduler doesn't have the updated implementation.

## Testing

### Unit Tests (`test_shared_event_loop.py`)

1. **Loop Initialization Test**: Verifies `self.loop` is `None` before `run()` and set during `run()`
2. **Error Handling Test**: Verifies `RuntimeError` is raised when loop not initialized
3. **Thread-Safe Execution Test**: Simulates Flask threads calling `run_coro_in_loop()` while scheduler runs
4. **Coroutine Execution Test**: Verifies coroutines execute successfully and return correct results

### Integration Tests

Existing tests verified to still pass:
- `test_weather_state_serialization.py` - 3/3 tests passing
- `test_device_status_integration.py` - 3/3 tests passing
- `test_shared_event_loop.py` - 4/4 tests passing

### Security Scan
CodeQL scan completed with **0 alerts**.

## Performance Considerations

### Minimal Overhead
- `asyncio.run_coroutine_threadsafe()` adds minimal overhead (submits work to event loop)
- Blocking on `future.result()` is acceptable since Flask is already threaded
- No additional thread creation or event loop overhead

### Benefits Over Old Approach
- **Eliminates errors**: No more "Timeout context manager" failures
- **More efficient**: Reuses existing event loop instead of creating new ones
- **Safer**: Proper synchronization guarantees

## Migration Guide

### For New Endpoints
When adding new Flask endpoints that need async device operations:

```python
@self.app.route('/api/new-endpoint', methods=['GET'])
def new_endpoint():
    if not self.scheduler or not hasattr(self.scheduler, 'run_coro_in_loop'):
        return jsonify({'error': 'Scheduler not available'}), 503
    
    try:
        result = self.scheduler.run_coro_in_loop(
            some_async_operation()
        )
        return jsonify({'data': result})
    except RuntimeError as e:
        logger.error(f"Loop not available: {e}")
        return jsonify({'error': str(e)}), 500
```

### For Existing Endpoints
Follow the pattern in `/api/devices/status`:
1. Check for `run_coro_in_loop` method
2. Use it if available
3. Provide fallback for backward compatibility
4. Handle `RuntimeError` appropriately

## Benefits

### Reliability
✅ Eliminates "Timeout context manager" errors  
✅ Prevents INTERNAL_QUERY_ERROR in device queries  
✅ Ensures consistent device state across all operations  

### Maintainability
✅ Clear separation of concerns (scheduler owns event loop)  
✅ Well-documented with comprehensive docstrings  
✅ Backward compatible with older scheduler versions  

### Performance
✅ No overhead of creating multiple event loops  
✅ Efficient thread-safe synchronization  
✅ Proper resource management (single loop, proper cleanup)  

## Future Enhancements

### Potential Improvements
1. Add metrics for `run_coro_in_loop()` call latency
2. Implement timeout parameter for long-running operations
3. Add retry logic for transient failures
4. Consider connection pooling for device operations

### Not Recommended
- ❌ Creating multiple scheduler event loops (defeats the purpose)
- ❌ Using `asyncio.run()` in Flask handlers (creates new loops)
- ❌ Making web server async (Flask is threaded by design)

## References

- [Python asyncio documentation](https://docs.python.org/3/library/asyncio.html)
- [asyncio.run_coroutine_threadsafe](https://docs.python.org/3/library/asyncio-task.html#asyncio.run_coroutine_threadsafe)
- [python-kasa GitHub](https://github.com/python-kasa/python-kasa)
- Flask threading model documentation

## Conclusion

This implementation solves the python-kasa async errors by ensuring all device I/O runs on the scheduler's event loop. The solution is thread-safe, backward compatible, well-tested, and includes comprehensive error handling.
