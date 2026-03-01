import fnmatch
import json
import time
from datetime import timedelta

import jwt
import pytest

from app.core import token_blacklist as token_blacklist_module


class FakeRedis:
    def __init__(self):
        self.store = {}
        self.ttl_store = {}

    def exists(self, key):
        return 1 if key in self.store else 0

    def setex(self, key, ttl, value):
        if isinstance(ttl, timedelta):
            ttl = int(ttl.total_seconds())
        self.store[key] = value
        self.ttl_store[key] = int(ttl)
        return True

    def get(self, key):
        return self.store.get(key)

    def delete(self, *keys):
        deleted = 0
        for key in keys:
            if key in self.store:
                del self.store[key]
                deleted += 1
            self.ttl_store.pop(key, None)
        return deleted

    def keys(self, pattern):
        return [key for key in self.store if fnmatch.fnmatch(key, pattern)]

    def scan_iter(self, match=None, count=None):
        _ = count
        pattern = match or "*"
        for key in list(self.store.keys()):
            if fnmatch.fnmatch(key, pattern):
                yield key

    def ttl(self, key):
        return self.ttl_store.get(key, -2)


def _make_token(jti: str, user_id: str, exp_seconds: int = 600) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "jti": jti,
        "iat": now,
        "exp": now + exp_seconds,
        "type": "access",
    }
    return jwt.encode(payload, "test-secret", algorithm="HS256")


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.fixture
def manager(monkeypatch: pytest.MonkeyPatch, fake_redis: FakeRedis):
    monkeypatch.setattr(token_blacklist_module, "get_redis_client", lambda: fake_redis)
    monkeypatch.setattr(token_blacklist_module, "get_security_config", lambda: object())
    config = token_blacklist_module.TokenBlacklistConfig(
        enable_metrics=False,
        audit_token_operations=False,
    )
    return token_blacklist_module.TokenBlacklistManager(config=config)


def test_revoke_user_tokens_revokes_using_active_index_keys(manager, fake_redis):
    user_id = "user-1"
    active_key = f"token:active:{user_id}:jti-1"
    exp = int(time.time()) + 600
    fake_redis.setex(active_key, 600, json.dumps({"jti": "jti-1", "exp": exp}))

    revoked = manager.revoke_user_tokens(user_id)

    assert revoked == 1
    assert fake_redis.exists(active_key) == 0
    assert fake_redis.exists("token:blacklist:jti-1") == 1
    assert fake_redis.ttl("token:blacklist:jti-1") == 600


def test_revoke_user_tokens_honors_exclude_by_jti_and_hash(manager, fake_redis):
    user_id = "user-2"
    excluded_token = _make_token("exclude-jti", user_id, exp_seconds=500)
    excluded_hash = manager._hash_token(excluded_token)
    exp = int(time.time()) + 500

    keep_by_jti_key = f"token:active:{user_id}:exclude-jti"
    keep_by_hash_key = f"token:active:{user_id}:hash-session"
    revoke_key = f"token:active:{user_id}:revoke-jti"

    fake_redis.setex(keep_by_jti_key, 500, json.dumps({"jti": "exclude-jti", "exp": exp}))
    fake_redis.setex(
        keep_by_hash_key,
        500,
        json.dumps(
            {
                "jti": "different-jti",
                "token_hash": excluded_hash,
                "exp": exp,
            }
        ),
    )
    fake_redis.setex(revoke_key, 500, json.dumps({"jti": "revoke-jti", "exp": exp}))

    revoked = manager.revoke_user_tokens(user_id, exclude_tokens=[excluded_token])

    assert revoked == 1
    assert fake_redis.exists(keep_by_jti_key) == 1
    assert fake_redis.exists(keep_by_hash_key) == 1
    assert fake_redis.exists(revoke_key) == 0
    assert fake_redis.exists("token:blacklist:exclude-jti") == 0
    assert fake_redis.exists("token:blacklist:different-jti") == 0
    assert fake_redis.exists("token:blacklist:revoke-jti") == 1


def test_is_blacklisted_checks_jti_blacklist_when_hash_key_missing(manager, fake_redis):
    token = _make_token("jti-fallback", "user-3", exp_seconds=300)
    token_hash = manager._hash_token(token)
    token_hash_key = manager._create_blacklist_key(token_hash)
    token_id_key = "token:blacklist:jti-fallback"

    assert fake_redis.exists(token_hash_key) == 0
    fake_redis.setex(token_id_key, 300, "user_revoke")

    assert manager.is_blacklisted(token) is True


def test_is_blacklisted_keeps_token_hash_flow(manager, fake_redis):
    token = _make_token("hash-flow", "user-4", exp_seconds=300)
    token_hash = manager._hash_token(token)
    token_hash_key = manager._create_blacklist_key(token_hash)
    fake_redis.setex(token_hash_key, 300, "legacy_blacklist")

    assert manager.is_blacklisted(token) is True
