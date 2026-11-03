
from gram import sessions
from gram.core.lexer import tokens

# `**` se tokeniza como dos `*` para representar niveles de puntero de Bagron.
# Gram 3.0 mantiene la API de símbolos global, pero todavía no expone una
# operación equivalente en `Session`; se aplica antes de copiar el catálogo
# hacia la sesión aislada.
if '**' in tokens.MAP_SYMBOLS:
    tokens.disabled_symbol('**')

BAGRON_SESSION = sessions.Session("Session From Bagron", 'Many')
BAGRON_SESSION.clear_global()
BAGRON_SESSION.init()

_BAGRON_SESSION_CONFIG = {
    'LEXER_ADD_ERROR': True,
    'PARSER_ADD_ERROR': True,
    'PARSER_ADD_INFO': True,
    'LEXER_IGNORE_EMPTY_LINES': True,
    'LEXER_SUPPORT_DOCSTRINGS': True,
    'LEXER_COMMENT_TOKEN': ';',
    # La telemetría sigue disponible en memoria para diagnosticar errores,
    # pero la compilación normal no persiste trazas por módulo en disco.
    'INFO_GENERATE_LOGFILE': False,
    'INFO_GENERATE_LOGFILE_ON_ERROR': False,
}

from core.frontend.syntax.keywords import register_keywords

register_keywords(BAGRON_SESSION)

from core.frontend.syntax import items

from core.frontend.syntax.reserved import *


BAGRON_SESSION.migrate()
for _key, _value in _BAGRON_SESSION_CONFIG.items():
    BAGRON_SESSION.set_config(_key, _value)

__all__ = [
    'BAGRON_SESSION',
    'items'
]
