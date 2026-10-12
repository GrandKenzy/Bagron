import gram

class EGL_CLAUSE(gram.RuleItem):
    name = "EGL_CLAUSE"
    description = "Directiva clause con nombre de cláusula y valor."
    docs = """
    Sintaxis:
        clause <nombre> <valor>

    Ejemplos:
        clause Target 'egl-c'
        clause StackLimit 1024

    `colors` aplica scopes independientes por posición:
    0 = `clause`, 1 = nombre de la cláusula, 2 = valor.
    """

    colors = {
        1: "#0CFF18",
        2: "#C2FF51",
    }
    suggestions_autocomplete = True
    suggestions = {
        1: {
            "prefix": "clause-target",
            "body": "clause Target '${1:egl-c}'",
            "description": "Selecciona el backend de destino de EGL.",
        },
        2: {
            "prefix": "clause-arch",
            "body": "clause Arch '${1:x86_64}'",
            "description": "Selecciona la arquitectura de destino.",
        },
        3: {
            "prefix": "clause-system",
            "body": "clause System '${1:linux}'",
            "description": "Selecciona el sistema operativo de destino.",
        },
        4: {
            "prefix": "clause-stack-limit",
            "body": "clause StackLimit ${1:1024}",
            "description": "Establece el límite de pila para el programa.",
        },
    }
    code = gram.AutoCode()
    grammar = gram.Seq(
        gram.MatchKeyword('clause'),
        gram.MatchGroup('clauses'),
        gram.Alt(
            gram.MatchToken('STRING'),
            gram.MatchToken('NUMBER')
        )
    )