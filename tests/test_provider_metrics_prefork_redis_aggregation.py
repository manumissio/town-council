from pipeline import metrics


class FakeRedis:
    def __init__(self):
        self.kv = {}
        self.hashes = {}

    def ping(self):
        return True

    def incrby(self, key, amount):
        self.kv[key] = int(self.kv.get(key, 0)) + int(amount)

    def hincrby(self, key, field, amount):
        bucket = self.hashes.setdefault(key, {})
        bucket[field] = int(bucket.get(field, 0)) + int(amount)

    def hincrbyfloat(self, key, field, amount):
        bucket = self.hashes.setdefault(key, {})
        bucket[field] = float(bucket.get(field, 0.0)) + float(amount)


def test_record_provider_metrics_mirror_to_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(metrics, "_redis_client", lambda: fake)

    metrics.record_provider_request("http", "summarize_text", "gemma", "ok", 111.0)
    metrics.record_provider_timeout("http", "summarize_text", "gemma")
    metrics.record_provider_retry("http", "summarize_text", "gemma")
    metrics.record_provider_token_counts("http", "summarize_text", "gemma", "ok", 120, 35)
    metrics.record_provider_ttft("http", "summarize_text", "gemma", "ok", 230.0)
    metrics.record_provider_tokens_per_sec("http", "summarize_text", "gemma", "ok", 17.5)

    label4 = metrics._provider_labels_key("http", "summarize_text", "gemma", "ok")
    label3 = metrics._provider_base_labels_key("http", "summarize_text", "gemma")

    assert fake.kv[f"tc:provider:req_total:{label4}"] == 1
    assert fake.kv[f"tc:provider:timeouts_total:{label3}"] == 1
    assert fake.kv[f"tc:provider:retries_total:{label3}"] == 1
    assert fake.kv[f"tc:provider:prompt_tokens_total:{label4}"] == 120
    assert fake.kv[f"tc:provider:completion_tokens_total:{label4}"] == 35

    ttft_bucket_key = f"tc:provider:ttft_ms:bucket:{label4}"
    tps_bucket_key = f"tc:provider:tps:bucket:{label4}"
    assert fake.hashes[ttft_bucket_key]["250.0"] == 1
    assert fake.hashes[tps_bucket_key]["20.0"] == 1
