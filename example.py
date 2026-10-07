import core.grammar
import gram
import core

from core.backend import c



def write(output: str, lines: list[str]):
    with open(output, 'w') as f:
        for line in lines:
            f.write(line + '\n')



def procesar():
    ast = gram.process(
        core.grammar.grammar,
        source_or_file='example.txt'
    )
    
    content = core.processor.process(ast)
    lines = [
        "#include <stdint.h>",
        "#include <stdio.h>",
        "#include <stdbool.h>"
    ]
    
    c.process(content)
 
    for item in core.processor.objects.get_items():
        print(item.compiled)
        if item.is_valid():
            lines.append(item.compiled)
 
    write('output.c', lines)

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