#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import secrets
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SLICE_DIR = SCRIPT_PATH.parent
ROOT_DIR = SLICE_DIR.parent.parent.parent.parent.parent
BACKEND_DIR = ROOT_DIR / 'backend-hormonia'
BACKEND_PYTHON = BACKEND_DIR / '.venv' / 'bin' / 'python'
DEFAULT_MASKED_ENV_FILE = Path('/tmp/gsd-s06-proof.env')
DEFAULT_BOOTSTRAP_FILE = Path('/tmp/gsd-s06-browser-bootstrap')
DEFAULT_EMAIL = 'session-first-proof@example.com'
DEFAULT_BASE_URL = 'http://localhost:5173'
DEFAULT_PROOF_NAME = 'S06 Mounted Proof Admin'
DEFAULT_WUZAPI_TOKEN = 'mounted-proof-local-token'

os.chdir(BACKEND_DIR)
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.security import create_password_reset_token  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.user import AuthProvider, User, UserRole  # noqa: E402
from app.utils.security import get_password_hash  # noqa: E402
from app.utils.timezone import now_sao_paulo  # noqa: E402


@dataclass(slots=True)
class SeedResult:
    email: str
    password: str
    rotated_password: str
    reset_token: str
    user_id: str
    masked_env_file: Path | None
    bootstrap_file: Path | None


def _normalize_email(email: str) -> str:
    return (email or '').strip().lower()


def _generate_password(prefix: str) -> str:
    return f'{prefix}@{secrets.token_hex(6)}!Aa9'


def _mask_value(value: str, *, prefix: int = 3, suffix: int = 2) -> str:
    if not value:
        return ''
    if len(value) <= prefix + suffix:
        return '*' * len(value)
    return f"{value[:prefix]}***{value[-suffix:]}"


def _mask_email(email: str) -> str:
    local_part, _, domain = email.partition('@')
    if not domain:
        return _mask_value(email)
    return f"{_mask_value(local_part, prefix=2, suffix=1)}@{domain}"


def _render_exports(seed: SeedResult, *, base_url: str) -> str:
    exports = {
        'E2E_BASE_URL': base_url,
        'E2E_SESSION_FIRST_EMAIL': seed.email,
        'E2E_SESSION_FIRST_PASSWORD': seed.password,
        'E2E_SESSION_FIRST_ROTATED_PASSWORD': seed.rotated_password,
        'E2E_SESSION_FIRST_RESET_TOKEN': seed.reset_token,
    }
    return '\n'.join(f"export {key}={shlex.quote(value)}" for key, value in exports.items())


def _write_masked_env_file(path: Path, seed: SeedResult, *, base_url: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = '\n'.join(
        [
            '# S06 mounted proof contract (masked)',
            f"export E2E_BASE_URL={shlex.quote(base_url)}",
            f"export E2E_SESSION_FIRST_EMAIL={shlex.quote(_mask_email(seed.email))}",
            f"export E2E_SESSION_FIRST_PASSWORD={shlex.quote(_mask_value(seed.password))}",
            (
                'export E2E_SESSION_FIRST_ROTATED_PASSWORD='
                f"{shlex.quote(_mask_value(seed.rotated_password))}"
            ),
            f"export E2E_SESSION_FIRST_RESET_TOKEN={shlex.quote(_mask_value(seed.reset_token, prefix=6, suffix=4))}",
            f"export E2E_SESSION_FIRST_USER_ID={shlex.quote(_mask_value(seed.user_id, prefix=8, suffix=4))}",
            (
                'export E2E_SESSION_FIRST_BOOTSTRAP='
                f"{shlex.quote(str(seed.bootstrap_file) if seed.bootstrap_file else '')}"
            ),
            '',
        ]
    )
    path.write_text(content, encoding='utf-8')


def _write_bootstrap_file(path: Path, *, email: str, base_url: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"""#!/usr/bin/env bash
set -euo pipefail
export FIREBASE_ADMIN_PROJECT_ID=''
export FIREBASE_ADMIN_CLIENT_EMAIL=''
export FIREBASE_ADMIN_PRIVATE_KEY=''
export WHATSAPP_WUZAPI_TOKEN='{DEFAULT_WUZAPI_TOKEN}'
export WHATSAPP_WUZAPI_USE_MOCK='true'
export VITE_FIREBASE_API_KEY=''
export VITE_FIREBASE_PROJECT_ID=''
export VITE_FIREBASE_APP_ID=''
export VITE_FIREBASE_AUTH_DOMAIN=''
export E2E_BASE_URL={shlex.quote(base_url)}
eval "$({shlex.quote(str(BACKEND_PYTHON))} {shlex.quote(str(SCRIPT_PATH))} --email {shlex.quote(email)} --base-url {shlex.quote(base_url)} --emit-shell-exports)"
if [[ $# -gt 0 ]]; then
  exec "$@"
fi
"""
    path.write_text(content, encoding='utf-8')
    os.chmod(path, 0o700)


def _seed_user(*, email: str, password: str, rotated_password: str) -> SeedResult:
    session = SessionLocal()
    normalized_email = _normalize_email(email)
    now = now_sao_paulo()

    try:
        user = session.query(User).filter(User.email == normalized_email).first()
        if user is None:
            user = User(
                email=normalized_email,
                full_name=DEFAULT_PROOF_NAME,
                role=UserRole.ADMIN,
                is_active=True,
                auth_provider=AuthProvider.LOCAL,
                permissions=[],
                firebase_custom_claims={},
            )
            session.add(user)

        user.email = normalized_email
        user.full_name = DEFAULT_PROOF_NAME
        user.role = UserRole.ADMIN
        user.is_active = True
        user.auth_provider = AuthProvider.LOCAL
        user.hashed_password = get_password_hash(password)
        user.force_change_password = False
        user.last_password_change = now
        user.failed_login_attempts = 0
        user.is_locked = False
        user.locked_until = None
        user.updated_at = now
        if getattr(user, 'permissions', None) is None:
            user.permissions = []
        if getattr(user, 'firebase_custom_claims', None) is None:
            user.firebase_custom_claims = {}

        session.flush()
        reset_token = create_password_reset_token(normalized_email)
        session.commit()
        session.refresh(user)

        return SeedResult(
            email=normalized_email,
            password=password,
            rotated_password=rotated_password,
            reset_token=reset_token,
            user_id=str(user.id),
            masked_env_file=None,
            bootstrap_file=None,
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Seed an ephemeral proof admin for S06 mounted runtime proof.')
    parser.add_argument('--email', default=DEFAULT_EMAIL)
    parser.add_argument('--password')
    parser.add_argument('--rotated-password')
    parser.add_argument('--base-url', default=DEFAULT_BASE_URL)
    parser.add_argument('--write-masked-env', type=Path, default=DEFAULT_MASKED_ENV_FILE)
    parser.add_argument('--write-bootstrap', type=Path, default=DEFAULT_BOOTSTRAP_FILE)
    parser.add_argument('--emit-shell-exports', action='store_true')
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    password = args.password or _generate_password('Proof')
    rotated_password = args.rotated_password or _generate_password('Rotate')

    seed = _seed_user(email=args.email, password=password, rotated_password=rotated_password)
    seed.masked_env_file = args.write_masked_env
    seed.bootstrap_file = args.write_bootstrap

    if args.write_bootstrap:
        _write_bootstrap_file(args.write_bootstrap, email=seed.email, base_url=args.base_url)
    if args.write_masked_env:
        _write_masked_env_file(args.write_masked_env, seed, base_url=args.base_url)

    if args.emit_shell_exports:
        sys.stdout.write(_render_exports(seed, base_url=args.base_url))
        return 0

    lines = [
        'seed_status=ready',
        f'user_id={_mask_value(seed.user_id, prefix=8, suffix=4)}',
        f'email={_mask_email(seed.email)}',
        f'password={_mask_value(seed.password)}',
        f'rotated_password={_mask_value(seed.rotated_password)}',
        f'reset_token={_mask_value(seed.reset_token, prefix=6, suffix=4)}',
        f'masked_env_file={args.write_masked_env}',
        f'bootstrap_file={args.write_bootstrap}',
        f'base_url={args.base_url}',
    ]
    sys.stdout.write('\n'.join(lines) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
