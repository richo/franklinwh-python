# This is a background thread that polls the franklin API and returns its results
from .client import Stats, empty_stats
from threading import Thread, Lock
import time
import pprint

class CachingThread(object):
    def __init__(self):
        self.thread = None
        self.data = None
        self.lock = Lock()

    def start(self, fetch_func):
        self.thread = ThreadedFetcher(fetch_func, 60, self.update_data)
        self.thread.start()

    def update_data(self, data):
        with self.lock:
            self.data = data

    def get_data(self):
        with self.lock:
            return self.data

class ThreadedFetcher(Thread):
    def __init__(self, client, poll_every, cb):
        super().__init__()
        self.daemon = True
        self.fetch_func = fetch_func
        self.poll_every = poll_every
        self.cb = cb

    def run(self):
        while True:
            try:
                stats = self.fetch_func()
                self.cb(stats)
            except Exception as e:
                # TODO(richo) better logging
                pprint.pprint("Exception: %s" % repr(e))
            time.sleep(self.poll_every)
