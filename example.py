import core.grammar
import gram
import core

from core.backend import c





def procesar():
    ast = gram.process(
        core.grammar.grammar,
        source_or_file='example.txt'
    )
    
    content = core.processor.process(ast)
    c.process(content)

if __name__ == '__main__':
    gram.config.LEXER_COMMENT_TOKEN = ';'
    gram.config.LEXER_IGNORE_EMPTY_LINES = True
    gram.config.LEXER_IGNORE_NEWLINES = True
    gram.config.LEXER_SAVE_COMMENTS = True
    gram.config.LEXER_SUPPORT_DOCSTRINGS = True
    gram.config.PARSER_ADD_INFO = True
    
    # importantes para el LOG.
    gram.config.INFO_GENERATE_LOGFILE_ON_ERROR = True; gram.config.INFO_GENERATE_LOGFILE = True
    procesar()