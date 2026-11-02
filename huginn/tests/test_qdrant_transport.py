"""RM-045 — Qdrant transport safety for huginn.

Threat TH-06 (docs/THREAT_MODEL.md): the Qdrant API key and the
memory payloads cross the network, and before this slice any
``http://`` URL was accepted for any host, the key was handed
to the client with no handling audit, and wrapped client
exceptions — whose text the ravens do not control — could
carry the key back to the caller and, in ``auto`` mode, into
an INFO log record. This slice pins:

* ``HuginnConfig.allow_insecure_http`` defaults to False;
* ``https`` is accepted for any host; plain ``http`` only for
  a loopback host (localhost / 127.0.0.0/8 / ::1) or with the
  opt-in; a non-http(s) scheme or a hostless URL is refused
  at construction with a typed configuration error whose
  message carries neither the key nor the URL;
* the key is excluded from the config's ``repr``, is handed
  to the client constructor (the audit's positive control),
  and never rides a wrapped client error — on the
  explicit-backend raises, on ``auto``'s recorded fallback
  reason and its INFO log, and on ``health()``'s unhealthy
  error string. (RM-054 supersedes this slice's original
  mechanism — client text with the key masked — with the
  general rule: no client text at all in a typed message,
  only the exception's class name; the facade still scrubs
  the strings it reports, as defence in depth.)

All proof is against fake clients (a live Qdrant round-trip
stays NOT PROVEN): the leaky fakes deliberately embed the key
in their exception text, the way a server or proxy error
quoting an auth header would.
"""

import logging
import sys
import types

import pytest

from huginn import HuginnConfig, HuginnMemory
from huginn.errors import HuginnBackendError, HuginnConfigurationError
from huginn.qdrant_backend import QdrantBackend
from huginn.text import HashingEmbedder

KEY = "SECRET-QDRANT-KEY-045"
INSECURE_MSG = (
    "qdrant_url uses plain http for a non-localhost host; "
    "use https or set allow_insecure_http=True"
)


def _cfg(**overrides):
    base = {"backend": "qdrant", "qdrant_api_key": KEY}
    base.update(overrides)
    return HuginnConfig(**base)


# ─── transport rule ───────────────────────────────────────────────────


def test_allow_insecure_http_defaults_off():
    assert HuginnConfig().allow_insecure_http is False


def test_default_and_loopback_http_urls_are_accepted():
    assert HuginnConfig().qdrant_url == "http://localhost:6333"
    for url in (
        "http://localhost:6333",
        "http://LOCALHOST:6333",
        "http://127.0.0.1:6333",
        "http://127.0.0.2:6333",
        "http://[::1]:6333",
        "http://dev.localhost:6333",
    ):
        assert _cfg(qdrant_url=url).qdrant_url == url


def test_https_remote_is_accepted_without_opt_in():
    cfg = _cfg(qdrant_url="https://qdrant.example:6334")
    assert cfg.allow_insecure_http is False


def test_http_remote_is_refused_without_opt_in():
    with pytest.raises(HuginnConfigurationError) as caught:
        _cfg(qdrant_url="http://qdrant.example:6333")
    assert str(caught.value) == INSECURE_MSG
    # The refusal names neither the key nor the URL.
    assert KEY not in str(caught.value)
    assert "qdrant.example" not in str(caught.value)


def test_http_remote_is_accepted_with_opt_in():
    cfg = _cfg(qdrant_url="http://qdrant.example:6333", allow_insecure_http=True)
    assert cfg.qdrant_url == "http://qdrant.example:6333"


def test_loopback_lookalikes_are_refused():
    for url in (
        "http://localhost.evil.example:6333",
        "http://127.0.0.1.evil.example:6333",
        "http://notlocalhost:6333",
    ):
        with pytest.raises(HuginnConfigurationError) as caught:
            _cfg(qdrant_url=url)
        assert str(caught.value) == INSECURE_MSG


def test_non_http_schemes_are_refused():
    for url in ("ftp://localhost:6333", "localhost:6333", "qdrant://localhost"):
        with pytest.raises(HuginnConfigurationError) as caught:
            _cfg(qdrant_url=url)
        assert str(caught.value) == "qdrant_url must use http or https"
        assert KEY not in str(caught.value)


def test_hostless_urls_are_refused():
    for url in ("http://", "https://", "http:///path"):
        with pytest.raises(HuginnConfigurationError) as caught:
            _cfg(qdrant_url=url)
        assert str(caught.value) == "qdrant_url must include a host"


# ─── key handling ─────────────────────────────────────────────────────


def test_config_repr_never_shows_the_key():
    cfg = _cfg(qdrant_url="https://qdrant.example:6334")
    assert KEY not in repr(cfg)
    assert "qdrant_api_key" not in repr(cfg)


class _NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _FakeModels(types.SimpleNamespace):
    Distance = types.SimpleNamespace(COSINE="cosine")

    @staticmethod
    def VectorParams(size, distance):
        return _NS(size=size, distance=distance)

    @staticmethod
    def PointStruct(id, vector, payload):
        return _NS(id=id, vector=vector, payload=payload)

    @staticmethod
    def PointIdsList(points):
        return _NS(points=points)


class _RecordingClient:
    """A healthy fake that records how it was constructed."""

    instances = []

    def __init__(self, url=None, api_key=None, timeout=None):
        self.url = url
        self.api_key = api_key
        self.timeout = timeout
        _RecordingClient.instances.append(self)

    def get_collections(self):
        return _NS(collections=[])

    def get_collection(self, name):
        return _NS(name=name)

    def count(self, collection_name):
        return _NS(count=0)

    def close(self):
        pass


class _LeakyDownClient:
    """Fails the probe with the key embedded in the error text."""

    def __init__(self, url=None, api_key=None, timeout=None):
        pass

    def get_collections(self):
        raise RuntimeError(f"401 unauthorized: api-key {KEY} rejected")


class _LeakyOpsClient:
    """Passes ping/collection; every operation leaks the key."""

    def get_collections(self):
        return _NS(collections=[])

    def get_collection(self, name):
        return _NS(name=name)

    def _boom(self):
        raise RuntimeError(f"server echoed header api-key: {KEY}")

    def upsert(self, **kwargs):
        self._boom()

    def delete(self, **kwargs):
        self._boom()

    def retrieve(self, **kwargs):
        self._boom()

    def query_points(self, **kwargs):
        self._boom()

    def count(self, **kwargs):
        self._boom()


class _LeakyCreateClient:
    """Collection creation fails with the key in the error text."""

    def get_collections(self):
        return _NS(collections=[])

    def get_collection(self, name):
        raise RuntimeError("missing")

    def create_collection(self, **kwargs):
        raise RuntimeError(f"create denied for key {KEY}")


def _fake_module(monkeypatch, client_cls):
    module = types.ModuleType("qdrant_client")
    module.QdrantClient = client_cls
    module.models = _FakeModels
    monkeypatch.setitem(sys.modules, "qdrant_client", module)
    return module


def _backend(client):
    backend = QdrantBackend(
        _cfg(qdrant_url="https://qdrant.example:6334"),
        HashingEmbedder(dim=64),
    )
    backend._client = client
    backend._models = _FakeModels
    return backend


def test_client_constructor_receives_url_key_and_timeout(monkeypatch):
    _RecordingClient.instances.clear()
    _fake_module(monkeypatch, _RecordingClient)
    backend = QdrantBackend(
        _cfg(qdrant_url="https://qdrant.example:6334", qdrant_timeout=3.5),
        HashingEmbedder(dim=64),
    )
    backend.ping()
    (client,) = _RecordingClient.instances
    # The audit's positive control: the key's one destination
    # is the client constructor, exactly as configured.
    assert client.url == "https://qdrant.example:6334"
    assert client.api_key == KEY
    assert client.timeout == 3.5
    backend.close()


def test_ping_error_carries_no_client_text(monkeypatch):
    _fake_module(monkeypatch, _LeakyDownClient)
    backend = QdrantBackend(
        _cfg(qdrant_url="https://qdrant.example:6334"),
        HashingEmbedder(dim=64),
    )
    with pytest.raises(HuginnBackendError) as caught:
        backend.ping()
    # RM-054: neither the key nor any other client wording —
    # only the exception's class name survives the wrap.
    assert KEY not in str(caught.value)
    assert "unauthorized" not in str(caught.value)
    assert "RuntimeError" in str(caught.value)
    backend.close()


def test_operation_errors_carry_no_client_text():
    backend = _backend(_LeakyOpsClient())
    operations = [
        lambda: backend.upsert(
            "text", category="general", importance=5, tags=[],
            emotional_valence=0.0,
        ),
        lambda: backend.delete(1),
        lambda: backend.get(1),
        lambda: backend.search(
            "text", limit=5, category=None, min_importance=1
        ),
        lambda: backend.count(),
    ]
    for operation in operations:
        with pytest.raises(HuginnBackendError) as caught:
            operation()
        assert KEY not in str(caught.value), str(caught.value)
        assert "server echoed header" not in str(caught.value)
        assert "RuntimeError" in str(caught.value)
    backend.close()


def test_collection_create_error_carries_no_client_text():
    backend = _backend(_LeakyCreateClient())
    with pytest.raises(HuginnBackendError) as caught:
        backend.upsert(
            "text", category="general", importance=5, tags=[],
            emotional_valence=0.0,
        )
    assert KEY not in str(caught.value)
    assert "create denied" not in str(caught.value)
    assert "RuntimeError" in str(caught.value)
    backend.close()


def test_auto_fallback_reason_and_log_are_scrubbed(monkeypatch, tmp_path, caplog):
    _fake_module(monkeypatch, _LeakyDownClient)
    cfg = HuginnConfig(
        backend="auto",
        qdrant_url="https://qdrant.example:6334",
        qdrant_api_key=KEY,
        local_db_path=str(tmp_path / "h.db"),
    )
    huginn = HuginnMemory(config=cfg)
    try:
        with caplog.at_level(logging.INFO, logger="huginn"):
            huginn.upsert_memory(content="fallback still lands", category="fact")
        health = huginn.health()
    finally:
        huginn.close()
    assert health["status"] == "degraded"
    assert KEY not in health["fallback_reason"]
    assert "unauthorized" not in health["fallback_reason"]
    assert "RuntimeError" in health["fallback_reason"]
    for record in caplog.records:
        assert KEY not in record.getMessage(), record.getMessage()


def test_explicit_health_error_is_scrubbed(monkeypatch, tmp_path):
    _fake_module(monkeypatch, _LeakyDownClient)
    huginn = HuginnMemory(
        config=_cfg(
            qdrant_url="https://qdrant.example:6334",
            embedder="hashing",
            vector_dim=64,
        )
    )
    try:
        health = huginn.health()
    finally:
        huginn.close()
    assert health["status"] == "unhealthy"
    assert KEY not in health["error"]
    assert "unauthorized" not in health["error"]
    assert "RuntimeError" in health["error"]
