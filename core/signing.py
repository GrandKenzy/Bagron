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


def _positive_int(value: object, *, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise CentralSignatureError(f'{context} debe ser un entero positivo')
    return value


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


def _trusted_roles() -> dict[str, dict[str, object]]:
    """Load TUF role policy from the embedded trust root."""
    root_path = Path(__file__).with_name('central_root.json')
    try:
        root = json.loads(root_path.read_text(encoding='utf-8'))
        keys = root.get('keys', {})
        if not isinstance(keys, dict) or not keys:
            raise ValueError('keys no es un objeto no vacio')
        roles = root.get('roles')
        if roles is None:
            return {
                role: {'keyids': list(keys), 'threshold': 1}
                for role in ('root', 'timestamp', 'snapshot', 'targets')
            }
        if not isinstance(roles, dict):
            raise ValueError('roles no es un objeto')
        return _validate_roles(roles, set(str(key_id) for key_id in keys))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise CentralSignatureError(f'No se pudo cargar la política raíz de Central: {error}') from error


def _validate_roles(
    raw_roles: object,
    known_keys: set[str],
) -> dict[str, dict[str, object]]:
    """Validate TUF role thresholds and key references."""
    if not isinstance(raw_roles, dict):
        raise CentralSignatureError('Los roles TUF no son un objeto valido')
    roles: dict[str, dict[str, object]] = {}
    for role_name, raw_role in raw_roles.items():
        if not isinstance(role_name, str) or not isinstance(raw_role, dict):
            raise CentralSignatureError('La declaracion de roles TUF no es valida')
        keyids = raw_role.get('keyids')
        if not isinstance(keyids, list) or not keyids or any(
            not isinstance(key_id, str) or not key_id for key_id in keyids
        ):
            raise CentralSignatureError(f'El rol TUF {role_name!r} no tiene keyids validos')
        if len(set(keyids)) != len(keyids) or any(key_id not in known_keys for key_id in keyids):
            raise CentralSignatureError(f'El rol TUF {role_name!r} referencia claves desconocidas')
        roles[role_name] = {
            'keyids': keyids,
            'threshold': _positive_int(
                raw_role.get('threshold'),
                context=f'El threshold del rol TUF {role_name!r}',
            ),
        }
        if roles[role_name]['threshold'] > len(keyids):
            raise CentralSignatureError(f'El threshold del rol TUF {role_name!r} es inalcanzable')
    return roles


def _metadata_keys(signed: dict[str, object]) -> dict[str, bytes]:
    """Decode the public keys carried by a TUF root statement."""
    raw_keys = signed.get('keys')
    if not isinstance(raw_keys, dict) or not raw_keys:
        raise CentralSignatureError('La raiz TUF no contiene claves')
    decoded: dict[str, bytes] = {}
    for key_id, raw_key in raw_keys.items():
        if not isinstance(key_id, str) or not key_id:
            raise CentralSignatureError('La raiz TUF contiene un keyid invalido')
        value = raw_key
        if isinstance(raw_key, dict):
            keyval = raw_key.get('keyval', raw_key)
            value = keyval.get('public') if isinstance(keyval, dict) else keyval
        decoded[key_id] = _decode_key(value, context=f'La clave TUF {key_id!r}')
    return decoded


def _expiry(signed: dict[str, object], *, context: str) -> datetime:
    expires = signed.get('expires')
    if not isinstance(expires, str) or not expires.strip():
        raise CentralSignatureError(f'{context} no contiene una expiracion valida')
    try:
        expiry = datetime.fromisoformat(expires.replace('Z', '+00:00'))
    except ValueError as error:
        raise CentralSignatureError(f'La fecha de expiracion de {context} no es valida') from error
    if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
        raise CentralSignatureError(f'Los metadatos {context} de Central estan expirados')
    return expiry


def _verify_envelope(
    envelope: object,
    *,
    role_name: str,
    keys: dict[str, bytes],
    roles: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Verify one signed TUF metadata envelope for a specific role."""
    if not isinstance(envelope, dict):
        raise CentralSignatureError(f'Los metadatos TUF del rol {role_name!r} no son un objeto')
    signed = envelope.get('signed')
    signatures = envelope.get('signatures')
    if not isinstance(signed, dict) or not isinstance(signatures, list):
        raise CentralSignatureError(f'Los metadatos TUF del rol {role_name!r} no son validos')
    _positive_int(signed.get('version'), context=f'La version TUF de {role_name!r}')
    _expiry(signed, context=role_name)
    role = roles.get(role_name)
    if not isinstance(role, dict):
        raise CentralSignatureError(f'Falta el rol TUF {role_name!r}')
    keyids = role.get('keyids')
    threshold = role.get('threshold')
    if not isinstance(keyids, list) or not isinstance(threshold, int):
        raise CentralSignatureError(f'El rol TUF {role_name!r} no es valido')
    signed_bytes = _canonical(signed)
    verified: set[str] = set()
    for item in signatures:
        if not isinstance(item, dict):
            continue
        key_id = item.get('keyid')
        if not isinstance(key_id, str) or key_id not in keyids or key_id in verified:
            continue
        public_bytes = keys.get(key_id)
        if public_bytes is None:
            continue
        try:
            Ed25519PublicKey.from_public_bytes(public_bytes).verify(
                _decode_signature(item.get('sig', '')),
                signed_bytes,
            )
        except Exception as error:
            raise CentralSignatureError(
                f'La firma TUF del rol {role_name!r} no es valida'
            ) from error
        verified.add(key_id)
    if len(verified) < threshold:
        raise CentralSignatureError(
            f'No se alcanzo el threshold del rol TUF {role_name!r}'
        )
    return signed


def _metadata_record(
    signed: dict[str, object],
    names: tuple[str, ...],
    *,
    context: str,
) -> dict[str, object]:
    raw_meta = signed.get('meta')
    if not isinstance(raw_meta, dict):
        raise CentralSignatureError(f'{context} no contiene meta TUF')
    for name in names:
        record = raw_meta.get(name)
        if isinstance(record, dict):
            return record
    raise CentralSignatureError(f'{context} no referencia los metadatos esperados')


def _verify_full_tuf(metadata: dict[str, object]) -> dict[str, object]:
    """Verify root, timestamp, snapshot and targets metadata as one chain."""
    trusted_keys = _trusted_keys()
    trusted_roles = _trusted_roles()
    root_signed = _verify_envelope(
        metadata.get('root'),
        role_name='root',
        keys=trusted_keys,
        roles=trusted_roles,
    )
    if root_signed.get('_type') != 'root':
        raise CentralSignatureError('La raiz TUF tiene un tipo de metadatos invalido')
    root_keys = _metadata_keys(root_signed)
    root_roles = _validate_roles(
        root_signed.get('roles'),
        set(root_keys),
    )
    # A rotated root must be authorized by both the previous trust root and
    # the keys it introduces before it can authorize the remaining roles.
    _verify_envelope(
        metadata.get('root'),
        role_name='root',
        keys=root_keys,
        roles=root_roles,
    )
    timestamp = _verify_envelope(
        metadata.get('timestamp'),
        role_name='timestamp',
        keys=root_keys,
        roles=root_roles,
    )
    if timestamp.get('_type') != 'timestamp':
        raise CentralSignatureError('Los metadatos timestamp TUF tienen un tipo invalido')
    snapshot = _verify_envelope(
        metadata.get('snapshot'),
        role_name='snapshot',
        keys=root_keys,
        roles=root_roles,
    )
    if snapshot.get('_type') != 'snapshot':
        raise CentralSignatureError('Los metadatos snapshot TUF tienen un tipo invalido')
    targets = _verify_envelope(
        metadata.get('targets'),
        role_name='targets',
        keys=root_keys,
        roles=root_roles,
    )
    if targets.get('_type') != 'targets':
        raise CentralSignatureError('Los metadatos targets TUF tienen un tipo invalido')
    snapshot_record = _metadata_record(
        timestamp,
        ('snapshot.json', 'snapshot'),
        context='timestamp TUF',
    )
    targets_record = _metadata_record(
        snapshot,
        ('targets.json', 'targets'),
        context='snapshot TUF',
    )
    if snapshot_record.get('version') != snapshot.get('version'):
        raise CentralSignatureError('timestamp TUF referencia una version snapshot distinta')
    if targets_record.get('version') != targets.get('version'):
        raise CentralSignatureError('snapshot TUF referencia una version targets distinta')
    return targets


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


def central_metadata_version(package_info: dict[str, object]) -> int | None:
    """Return the signed targets version when Central supplied metadata."""
    metadata = _parse_metadata(package_info)
    if metadata is None:
        return None
    if {'root', 'timestamp', 'snapshot', 'targets'}.issubset(metadata):
        targets = metadata.get('targets')
        signed = targets.get('signed') if isinstance(targets, dict) else None
    else:
        signed = metadata.get('signed')
    if not isinstance(signed, dict):
        raise CentralSignatureError('Los metadatos TUF no contienen targets firmados')
    return _positive_int(signed.get('version'), context='La version TUF')


def verify_central_artifact(
    package_info: dict[str, object],
    artifact: bytes,
    *,
    resolved_name: str,
    resolved_version: str,
    package_format: str,
    require: bool = False,
    minimum_version: int | None = None,
) -> bool:
    """Verify Central target metadata and its Ed25519/TUF signatures.

    Complete root/timestamp/snapshot/targets metadata is verified as a TUF
    chain. A single signed targets statement remains compatible during the
    catalog migration. Set ``BAGRON_REQUIRE_CENTRAL_SIGNATURES=1`` once
    Central publishes signed metadata for every official target.
    """
    metadata = _parse_metadata(package_info)
    if metadata is None:
        if require:
            raise CentralSignatureError('Central no proporcionó metadatos TUF firmados')
        return False
    tuf_roles = {'root', 'timestamp', 'snapshot', 'targets'}
    present_roles = tuf_roles.intersection(metadata)
    full_chain_verified = False
    if present_roles:
        if present_roles != tuf_roles:
            raise CentralSignatureError('Los metadatos TUF estan incompletos')
        signed = _verify_full_tuf(metadata)
        signatures: list[dict[str, object]] = []
        full_chain_verified = True
    else:
        signed = metadata.get('signed')
        signatures = metadata.get('signatures')
        if not isinstance(signed, dict) or not isinstance(signatures, list):
            raise CentralSignatureError('Los metadatos TUF no tienen signed y signatures validos')
    if signed.get('_type') != 'targets':
        raise CentralSignatureError('El tipo de metadatos TUF no es targets')
    targets_version = _positive_int(signed.get('version'), context='La version TUF')
    if minimum_version is not None:
        if isinstance(minimum_version, bool) or not isinstance(minimum_version, int):
            raise CentralSignatureError('La version minima TUF no es valida')
        if targets_version < minimum_version:
            raise CentralSignatureError('Central devolvio metadatos TUF anteriores al lockfile')
    _expiry(signed, context='targets')

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
        if field == 'length':
            if isinstance(actual, bool) or not isinstance(actual, int):
                raise CentralSignatureError('Los metadatos TUF contienen un length invalido')
        elif field in {'name', 'version', 'package_format', 'sha256'} and not isinstance(actual, str):
            raise CentralSignatureError(f'Los metadatos TUF contienen {field} invalido')
        if actual != value:
            raise CentralSignatureError(f'Los metadatos TUF no coinciden en {field}')

    if full_chain_verified:
        return True
    signed_bytes = _canonical(signed)
    keys = _trusted_keys()
    signatures = [item for item in signatures if isinstance(item, dict)]
    if not signatures:
        raise CentralSignatureError('Los metadatos TUF no contienen firmas')
    raw_threshold = metadata.get('threshold', 1)
    threshold = _positive_int(raw_threshold, context='El threshold TUF')
    verified_key_ids: set[str] = set()
    for item in signatures:
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
        verified_key_ids.add(key_id)
    if len(verified_key_ids) < threshold:
        raise CentralSignatureError(
            'No se alcanzo el threshold de firmas TUF de claves raíz confiables'
        )
    return True


__all__ = [
    'CentralSignatureError',
    'central_metadata_version',
    'verify_central_artifact',
]
