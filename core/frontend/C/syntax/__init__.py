from gram import config, sessions

C_SESSION = sessions.Session("Session From C", 'Many')
C_SESSION.clear_global()
C_SESSION.init()

config.LEXER_ADD_ERROR = True
config.PARSER_ADD_ERROR = True
config.PARSER_ADD_INFO = True
config.PARSER_ADD_ERROR = True
config.LEXER_IGNORE_EMPTY_LINES = True
config.LEXER_SUPPORT_DOCSTRINGS = False
config.LEXER_COMMENT_TOKEN = '//'
config.INFO_GENERATE_LOGFILE = True
config.INFO_GENERATE_LOGFILE_ON_ERROR = True

from core.frontend.C.syntax.keywords import *  # noqa: I001

from core.frontend.C.syntax import items

from core.frontend.C.syntax.reserved import *
 
 
C_SESSION.migrate()

__all__ = [
    'C_SESSION',
    'items'
]