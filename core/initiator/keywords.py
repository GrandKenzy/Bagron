import gram

gram.words.add_group('types')
gram.words.add_group('privacity')

gram.words.add_keyword('void', group='types')
gram.words.add_keyword('char', group='types')

gram.words.add_keyword('double', group='types') # float64
gram.words.add_keyword('float', group='types') # float32
gram.words.add_keyword('middle', group='types') # float 16

gram.words.add_keyword('int', group='types')
gram.words.add_keyword('i8', group='types')
gram.words.add_keyword('i16', group='types')
gram.words.add_keyword('i32', group='types')
gram.words.add_keyword('i64', group='types')

gram.words.add_keyword('uint', group='types')
gram.words.add_keyword('ui8', group='types')
gram.words.add_keyword('ui16', group='types')
gram.words.add_keyword('ui32', group='types')
gram.words.add_keyword('ui64', group='types')

gram.words.add_keyword('public', group='privacity')
gram.words.add_keyword('private', group='privacity')

gram.words.add_keyword('return', group='keywords')