
from gram import config, sessions

EASY_C_SESSION = sessions.Session("Session From Easy C", 'Many')
EASY_C_SESSION.clear_global()
EASY_C_SESSION.init()

config.LEXER_ADD_ERROR = True
config.PARSER_ADD_ERROR = True
config.PARSER_ADD_INFO = True
config.PARSER_ADD_ERROR = True
config.LEXER_IGNORE_EMPTY_LINES = True
config.LEXER_SUPPORT_DOCSTRINGS = True
config.LEXER_COMMENT_TOKEN = ';'
config.INFO_GENERATE_LOGFILE = True
config.INFO_GENERATE_LOGFILE_ON_ERROR = True

from core.frontend.EASYC.syntax.keywords import *  # noqa: I001

from core.frontend.EASYC.syntax import items

from core.frontend.EASYC.syntax.reserved import *


EASY_C_SESSION.migrate()

__all__ = [
    'EASY_C_SESSION',
    'items'
]