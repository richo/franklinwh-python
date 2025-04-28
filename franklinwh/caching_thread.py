# This is a background thread that polls the franklin API and returns its results
from .client import Stats, empty_stats
from threading import Thread, Lock
import time
import pprint

class CachingThread(object):
    def __init__(self, client):
        self.thread = ThreadedFetcher(client, 60, self.update_stats)
        self.data = None
        self.lock = Lock()
        self.thread.start()


    def update_stats(self, data):
        with self.lock:
            self.data = data

    def get_stats(self):
        with self.lock:
            return self.data


class ThreadedFetcher(Thread):
    def __init__(self, client, poll_every, cb):
        super().__init__()
        self.daemon = True
        self.client = client
        self.poll_every = poll_every
        self.cb = cb

    def run(self):
        while True:
            try:
                stats = self.client.get_stats()
                self.cb(stats)
            except Exception as e:
                # TODO(richo) better logging
                pprint.pprint("Exception: %s" % repr(e))
            time.sleep(self.poll_every)
