from gram import config, sessions

HEADERS_SESSION = sessions.Session('Session From Headers C', 'Many')
HEADERS_SESSION.clear_global()
HEADERS_SESSION.init()

config.LEXER_ADD_ERROR = True
config.PARSER_ADD_ERROR = True
config.PARSER_ADD_INFO = True
config.PARSER_ADD_ERROR = True
config.LEXER_IGNORE_EMPTY_LINES = True
config.LEXER_SUPPORT_DOCSTRINGS = True
config.LEXER_COMMENT_TOKEN = '//'
config.INFO_GENERATE_LOGFILE = True
config.INFO_GENERATE_LOGFILE_ON_ERROR = True

from core.frontend.HEADERS.headers.syntax.keywords import *
from core.frontend.HEADERS.headers.syntax import items

HEADERS_SESSION.migrate()

__all__ = [
    'HEADERS_SESSION',
    'items',
]