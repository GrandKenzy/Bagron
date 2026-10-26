
from gram import config, sessions

BAGRON_SESSION = sessions.Session("Session From Bagron", 'Many')
BAGRON_SESSION.clear_global()
BAGRON_SESSION.init()

config.LEXER_ADD_ERROR = True
config.PARSER_ADD_ERROR = True
config.PARSER_ADD_INFO = True
config.LEXER_IGNORE_EMPTY_LINES = True
config.LEXER_SUPPORT_DOCSTRINGS = True
config.LEXER_COMMENT_TOKEN = ';'
config.INFO_GENERATE_LOGFILE = True
config.INFO_GENERATE_LOGFILE_ON_ERROR = True

from core.frontend.syntax.keywords import *  # noqa: I001

from core.frontend.syntax import items

from core.frontend.syntax.reserved import *


BAGRON_SESSION.migrate()

__all__ = [
    'BAGRON_SESSION',
    'items'
]
