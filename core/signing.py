"""Verification of Central's Ed25519/TUF-style artifact metadata."""
from __future__ import annotations

from base64 import b64decode
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class CentralSignatureError(RuntimeError):
    """Raised when signed Central metadata is missing, stale or invalid."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def _decode_key(value: object, *, context: str) -> bytes:
    try:
        raw = b64decode(str(value), validate=True)
    except Exception as error:
        raise CentralSignatureError(f'{context} no es una clave Ed25519 base64 valida') from error
    if len(raw) != 32:
        raise CentralSignatureError(f'{context} no tiene 32 bytes')
    return raw


def _decode_signature(value: object) -> bytes:
    try:
        raw = b64decode(str(value), validate=True)
    except Exception as error:
        raise CentralSignatureError('La firma Ed25519 no es base64 valida') from error
    if len(raw) != 64:
        raise CentralSignatureError('La firma Ed25519 no tiene 64 bytes')
    return raw


def _trusted_keys() -> dict[str, bytes]:
    root_path = Path(__file__).with_name('central_root.json')
    try:
        root = json.loads(root_path.read_text(encoding='utf-8'))
        keys = root.get('keys', {})
        if not isinstance(keys, dict):
            raise ValueError('keys no es un objeto')
        return {
            str(key_id): _decode_key(value, context=f'La clave raíz {key_id!r}')
            for key_id, value in keys.items()
        }
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise CentralSignatureError(f'No se pudo cargar la raíz de confianza de Central: {error}') from error


def _parse_metadata(package_info: dict[str, object]) -> dict[str, object] | None:
    raw = package_info.get('tuf') or package_info.get('tuf_metadata')
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as error:
            raise CentralSignatureError(f'Los metadatos TUF no son JSON validos: {error}') from error
    if not isinstance(raw, dict):
        raise CentralSignatureError('Los metadatos TUF no son un objeto')
    return raw


def verify_central_artifact(
    package_info: dict[str, object],
    artifact: bytes,
    *,
    resolved_name: str,
    resolved_version: str,
    package_format: str,
    require: bool = False,
) -> bool:
    """Verify a Central target statement and its Ed25519 signature.

    Missing metadata remains compatible during the catalog migration. Set
    ``BAGRON_REQUIRE_CENTRAL_SIGNATURES=1`` once Central publishes every
    official target with this metadata.
    """
    metadata = _parse_metadata(package_info)
    if metadata is None:
        if require:
            raise CentralSignatureError('Central no proporcionó metadatos TUF firmados')
        return False
    signed = metadata.get('signed')
    signatures = metadata.get('signatures')
    if not isinstance(signed, dict) or not isinstance(signatures, list):
        raise CentralSignatureError('Los metadatos TUF no tienen signed y signatures validos')
    if signed.get('_type') not in {'targets', 'snapshot'}:
        raise CentralSignatureError('El tipo de metadatos TUF no es targets')
    expires = str(signed.get('expires', ''))
    try:
        expiry = datetime.fromisoformat(expires.replace('Z', '+00:00'))
    except ValueError as error:
        raise CentralSignatureError('La fecha de expiracion TUF no es valida') from error
    if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
        raise CentralSignatureError('Los metadatos TUF de Central estan expirados')

    target = signed.get('target')
    if not isinstance(target, dict):
        targets = signed.get('targets')
        if isinstance(targets, dict):
            target = (
                targets.get(f'{resolved_name}/{resolved_version}')
                or targets.get(f'{resolved_name}/{resolved_version}.lib')
                or targets.get(resolved_name)
            )
    if not isinstance(target, dict):
        raise CentralSignatureError('Los metadatos TUF no describen el paquete solicitado')
    custom = target.get('custom', {})
    if not isinstance(custom, dict):
        custom = {}
    hashes = target.get('hashes', {})
    if not isinstance(hashes, dict):
        hashes = {}
    expected = {
        'name': resolved_name,
        'version': resolved_version,
        'package_format': package_format,
        'length': len(artifact),
        'sha256': hashlib.sha256(artifact).hexdigest(),
    }
    for field, value in expected.items():
        actual = target.get(field)
        if field in {'name', 'version', 'package_format'} and actual is None:
            actual = custom.get(field)
        if field == 'sha256':
            actual = hashes.get('sha256', target.get('sha256'))
        if str(actual) != str(value):
            raise CentralSignatureError(f'Los metadatos TUF no coinciden en {field}')

    signed_bytes = _canonical(signed)
    keys = _trusted_keys()
    verified = False
    for item in signatures:
        if not isinstance(item, dict):
            continue
        key_id = str(item.get('keyid', ''))
        public_bytes = keys.get(key_id)
        if public_bytes is None:
            continue
        try:
            Ed25519PublicKey.from_public_bytes(public_bytes).verify(
                _decode_signature(item.get('sig', '')),
                signed_bytes,
            )
        except Exception as error:
            raise CentralSignatureError('La firma TUF de Central no es valida') from error
        verified = True
        break
    if not verified:
        raise CentralSignatureError('No se encontro una firma TUF de una clave raíz confiable')
    return True


__all__ = ['CentralSignatureError', 'verify_central_artifact']
