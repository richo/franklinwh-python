# This is a background thread that polls the franklin API and returns its results
from threading import Thread, Lock
import time
import pprint

# The default polling interval is measured in seconds.

# Defaulting to 58 seconds avoids re-creating the connection (and redoing
# the TLS security handshake) on every sensor update since there are
# timeouts that close the connection after 60 seconds.
DEFAULT_POLL_EVERY = 58

class CachingThread(object):
    def __init__(self):
        self.thread: ThreadedFetcher = None # type: ignore
        # Needs to be None so that home assistant knows there is no values yet.
        self.data = None
        self.lock = Lock()

    def start(self, fetch_func, poll_every=DEFAULT_POLL_EVERY):
        self.thread = ThreadedFetcher(fetch_func, poll_every, self.update_data)
        self.thread.start()

    def stop(self):
        self.thread.stop()
        self.thread.join()

    def update_data(self, data):
        with self.lock:
            self.data = data

    def get_data(self):
        with self.lock:
            return self.data

class ThreadedFetcher(Thread):
    def __init__(self, fetch_func, poll_every, cb):
        super().__init__()
        self.daemon = True
        self.stopped = False
        self.fetch_func = fetch_func
        self.poll_every = poll_every
        self.cb = cb

    def stop(self):
        self.stopped = True

    def run(self):
        while not self.stopped:
            try:
                stats = self.fetch_func()
                self.cb(stats)
            except Exception as e:
                # TODO(richo) better logging
                pprint.pprint("Exception: %s" % repr(e))
            time.sleep(self.poll_every)
