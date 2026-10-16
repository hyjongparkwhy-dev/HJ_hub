class FakeStore:
    def __init__(self, mb=30.0, known_urls=(), known_keys=()):
        self.mb, self.known_urls, self.known_keys = mb, set(known_urls), set(known_keys)
        self.inserted, self.purged_days, self.runs = [], [], []

    def database_mb(self):
        return self.mb

    def known(self, urls, keys):
        return self.known_urls & set(urls), self.known_keys & set(keys)

    def insert(self, items, vectors):
        self.inserted.extend(zip(items, vectors))
        return len(items)

    def purge(self, days):
        self.purged_days.append(days)
        return 2

    def record_run(self, stats):
        self.runs.append(stats)


class FakeEmbedder:
    def __init__(self):
        self.calls = []

    def vectors(self, texts):
        self.calls.append(list(texts))
        return [[0.0] * 384 for _ in texts]
