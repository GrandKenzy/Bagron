import core, gram
from core.initiator import rules

grammar = {
    gram.PROGRAM: gram.Many(
        gram.Ref(gram.DECLARATION)
    ),
    gram.DECLARATION: gram.Alt(
        gram.Ref(rules.EGL_TYPE_DECL),
        gram.Ref(rules.EGL_FUNC_DECL),
        gram.Ref(rules.EGL_VAR_DECL),
        gram.Ref(rules.EGL_IF_STATEMENT),
        gram.Ref(rules.EGL_FOR_STATEMENT),
        gram.Ref(rules.EGL_INCLUDE),
        gram.Ref(rules.EGL_IMPORT),
        gram.Ref(rules.EGL_CLASS),
        gram.Ref(rules.EGL_CLAUSE),
        gram.Ref(rules.EGL_METHOD_CALL),
        gram.Ref(rules.EGL_MEMBER_ACCESS),
        gram.Ref(rules.EGL_CALL),
        gram.Ref(rules.EGL_ASSIGN),
    )
}