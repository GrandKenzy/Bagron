from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.compiler import Compiler


def _function_ir(ir_text: str, name: str) -> str:
    marker = f'fn_{name}_'
    start = ir_text.find('define ', ir_text.find(marker) - 120)
    if start < 0:
        raise AssertionError(f'No se encontro la funcion LLVM para {name}')
    end = ir_text.find('\ndefine ', start + 1)
    return ir_text[start:] if end < 0 else ir_text[start:end]


class FixedArrayBackendTests(unittest.TestCase):
    def compile_source(self, source: str, profile: str = 'prod') -> str:
        source = (
            f"clause Optimizations '{profile}'\n"
            + source.rstrip()
            + '\n\nfunc main() int32:\n'
            + '    return 0\n'
        )
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        ir_path = Compiler().compile(path, executable=False)
        return Path(ir_path).read_text(encoding='utf-8')

    def test_proven_array_omits_zero_initialization_in_prod(self):
        ir = self.compile_source(
            'func complete() int32:\n'
            '    data: int32[4]\n'
            '    data[0] = 10\n'
            '    data[1] = 20\n'
            '    data[2] = 30\n'
            '    data[3] = 40\n'
            '    return data[2]\n'
        )
        body = _function_ir(ir, 'complete')
        self.assertNotIn('store [4 x i32] [i32 0', body)

    def test_unproven_array_keeps_zero_initialization(self):
        ir = self.compile_source(
            'func incomplete() int32:\n'
            '    data: int32[4]\n'
            '    data[0] = 10\n'
            '    data[1] = 20\n'
            '    return data[1]\n',
            profile='dev',
        )
        body = _function_ir(ir, 'incomplete')
        self.assertIn('store [4 x i32] [i32 0', body)

    def test_dev_profile_keeps_explicit_zero_initialization(self):
        ir = self.compile_source(
            'func complete() int32:\n'
            '    data: int32[2]\n'
            '    data[0] = 10\n'
            '    data[1] = 20\n'
            '    return data[1]\n',
            profile='dev',
        )
        body = _function_ir(ir, 'complete')
        self.assertIn('store [2 x i32] [i32 0', body)

    def test_private_scratch_call_omits_caller_zero_initialization(self):
        ir = self.compile_source(
            'private func fill(data: int32[4], length: Len_t, size: Size_t) void:\n'
            '    data[0] = 10\n'
            '    data[1] = 20\n'
            '    data[2] = 30\n'
            '    data[3] = 40\n'
            '    return\n'
            'func caller() int32:\n'
            '    data: int32[4]\n'
            '    fill(data)\n'
            '    return data[3]\n'
        )
        body = _function_ir(ir, 'caller')
        self.assertNotIn('store [4 x i32] [i32 0', body)


if __name__ == '__main__':
    unittest.main()
