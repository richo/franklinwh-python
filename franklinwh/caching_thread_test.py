import pytest
from unittest.mock import MagicMock, patch
from .caching_thread import CachingThread, ThreadedFetcher, DEFAULT_POLL_EVERY
from .client import Stats, Current, Totals
import time

@pytest.fixture(autouse=True)
def no_sleep_or_join(monkeypatch):
    # Prevent actual sleeping during tests
    monkeypatch.setattr(time, "sleep", MagicMock())
    # Prevent actual thread joining during tests, as it can block
    monkeypatch.setattr(ThreadedFetcher, "join", MagicMock())

def test_caching_thread_initialization():
    thread = CachingThread()
    assert thread.thread is None
    assert thread.data is None
    assert thread.lock is not None

def test_caching_thread_start_and_get_data():
    thread = CachingThread()
    mock_fetch_func = MagicMock(return_value="some_data")

    # Poll doesn't actually matter since we mock'ed the sleep
    thread.start(mock_fetch_func, poll_every=0.01)

    # Give the thread a moment to run (it's a daemon thread, so it runs in background)
    # Since the sleep is mocked, there is no actual sleep and the background task
    # will spin until stopped.

    # Manually trigger the callback to simulate data update
    thread.update_data("first_data")
    assert thread.get_data() == "first_data"

    thread.update_data("second_data")
    assert thread.get_data() == "second_data"

    thread.stop()
    mock_fetch_func.assert_called() # Ensure fetch_func was called at least once

def test_threaded_fetcher_run_method_stops_gracefully():
    mock_fetch_func = MagicMock(return_value="test_data")
    mock_cb = MagicMock()
    fetcher = ThreadedFetcher(mock_fetch_func, poll_every=0.01, cb=mock_cb)

    # Start the thread
    fetcher.start()

    # Allow it to run for a short period
    time.sleep.assert_called_with(0.01) # Verify sleep was called

    # Stop the thread
    fetcher.stop()

    # Ensure fetch_func was called and callback was triggered
    mock_fetch_func.assert_called()
    mock_cb.assert_called_with("test_data")

    # Verify that after stopping, it doesn't call fetch_func again
    call_count_before_stop = mock_fetch_func.call_count
    # Simulate a short delay to ensure the loop would have run again if not stopped
    time.sleep(0.02)
    assert mock_fetch_func.call_count == call_count_before_stop

def test_threaded_fetcher_error_handling():
    mock_fetch_func = MagicMock(side_effect=Exception("Test Error"))
    mock_cb = MagicMock()
    fetcher = ThreadedFetcher(mock_fetch_func, poll_every=0.01, cb=mock_cb)

    with patch('pprint.pprint') as mock_pprint:
        fetcher.start()
        # Allow it to run for a short period
        time.sleep.assert_called_with(0.01)
        fetcher.stop()
        mock_pprint.assert_called_with("Exception: Exception('Test Error')")
    mock_cb.assert_not_called() # Callback should not be called on exception

def test_caching_thread_stop_method():
    thread = CachingThread()
    mock_fetch_func = MagicMock(return_value="some_data")
    thread.start(mock_fetch_func, poll_every=0.01)

    # Ensure the thread is running and has made at least one call
    time.sleep.assert_called_with(0.01)
    mock_fetch_func.assert_called()

    thread.stop()
    # Verify that the fetcher's stop method was called
    assert thread.thread.stopped == True
    # Verify that join was called (mocked to prevent blocking)
    thread.thread.join.assert_called_once()

    # Ensure no more calls after stop
    call_count_after_stop = mock_fetch_func.call_count
    time.sleep(0.02)
    assert mock_fetch_func.call_count == call_count_after_stop

def test_caching_thread_default_poll_every():
    thread = CachingThread()
    mock_fetch_func = MagicMock(return_value="some_data")
 
    # Start without specifying poll_every
    thread.start(mock_fetch_func)
 
    # Check that the ThreadedFetcher was initialized with the default
    assert thread.thread.poll_every == DEFAULT_POLL_EVERY
 
    thread.stop()
