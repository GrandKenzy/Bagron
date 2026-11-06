from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.compiler import Compiler


class FixedArrayFlowTests(unittest.TestCase):
    def compile_source(self, source: str) -> Compiler:
        source = "clause Optimizations 'dev'\n" + source.rstrip() + (
            '\n\nfunc main() int32:\n'
            '    return 0\n'
        )
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        compiler = Compiler()
        compiler.compile(path, executable=False)
        return compiler

    def test_proves_sequential_complete_writes(self):
        compiler = self.compile_source(
            'func complete() int32:\n'
            '    data: int32[4]\n'
            '    data[0] = 10\n'
            '    data[1] = 20\n'
            '    data[2] = 30\n'
            '    data[3] = 40\n'
            '    return data[2]\n'
        )
        self.assertEqual(
            {'data'},
            compiler.storage.functions['complete'].definite_array_writes,
        )

    def test_rejects_missing_element(self):
        compiler = self.compile_source(
            'func incomplete() int32:\n'
            '    data: int32[4]\n'
            '    data[0] = 10\n'
            '    data[1] = 20\n'
            '    data[2] = 30\n'
            '    return data[2]\n'
        )
        self.assertEqual(
            set(),
            compiler.storage.functions['incomplete'].definite_array_writes,
        )

    def test_rejects_read_before_write(self):
        compiler = self.compile_source(
            'func read_first() int32:\n'
            '    data: int32[2]\n'
            '    value: int32 = data[0]\n'
            '    data[0] = 10\n'
            '    data[1] = 20\n'
            '    return value\n'
        )
        self.assertEqual(
            set(),
            compiler.storage.functions['read_first'].definite_array_writes,
        )

    def test_intersection_of_branches_must_be_complete(self):
        compiler = self.compile_source(
            'func branched(flag: bool) int32:\n'
            '    data: int32[2]\n'
            '    if flag:\n'
            '        data[0] = 10\n'
            '        data[1] = 20\n'
            '    else:\n'
            '        data[0] = 30\n'
            '        data[1] = 40\n'
            '    return data[1]\n'
        )
        self.assertEqual(
            {'data'},
            compiler.storage.functions['branched'].definite_array_writes,
        )

    def test_constant_range_loop_can_prove_complete_write(self):
        compiler = self.compile_source(
            'func looped() int32:\n'
            '    data: int32[4]\n'
            '    for i: uint32 ran (0, 4, 1):\n'
            '        data[i] = 7\n'
            '    return data[3]\n'
        )
        self.assertEqual(
            {'data'},
            compiler.storage.functions['looped'].definite_array_writes,
        )

    def test_fixed_array_parameters_are_not_local_write_candidates(self):
        compiler = self.compile_source(
            'func inspect(data: int32[2], length: Len_t, size: Size_t) int32:\n'
            '    return data[0]\n'
        )
        self.assertEqual(
            set(),
            compiler.storage.functions['inspect'].definite_array_writes,
        )

    def test_private_scratch_helper_proves_caller_array(self):
        compiler = self.compile_source(
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
        summary = compiler.storage.functions['fill'].fixed_array_parameter_summary
        self.assertFalse(summary['data'].requires_initialized)
        self.assertTrue(summary['data'].fully_written_on_return)
        self.assertEqual(
            {'data'},
            compiler.storage.functions['caller'].definite_array_writes,
        )

    def test_private_input_helper_requires_initialized_array(self):
        compiler = self.compile_source(
            'private func read_first(data: int32[4], length: Len_t, size: Size_t) int32:\n'
            '    return data[0]\n'
            'func caller() int32:\n'
            '    data: int32[4]\n'
            '    return read_first(data)\n'
        )
        summary = compiler.storage.functions[
            'read_first'
        ].fixed_array_parameter_summary
        self.assertTrue(summary['data'].requires_initialized)
        self.assertFalse(summary['data'].fully_written_on_return)
        self.assertEqual(
            set(),
            compiler.storage.functions['caller'].definite_array_writes,
        )

    def test_compound_index_is_not_mistaken_for_constant(self):
        compiler = self.compile_source(
            '@unsafe\n'
            'func dynamic_index() int32:\n'
            '    data: int32[4]\n'
            '    index: uint32 = 1\n'
            '    value: int32 = data[index - 1]\n'
            '    data[0] = 10\n'
            '    data[1] = 20\n'
            '    data[2] = 30\n'
            '    data[3] = 40\n'
            '    return value\n'
        )
        self.assertEqual(
            set(),
            compiler.storage.functions['dynamic_index'].definite_array_writes,
        )

    def test_loop_recurrence_proves_scratch_schedule(self):
        compiler = self.compile_source(
            '@unsafe\n'
            'private func schedule(data: uint32[64], length: Len_t, size: Size_t) void:\n'
            '    for i: uint32 ran (0, 16, 1):\n'
            '        data[i] = 1\n'
            '    for i: uint32 ran (16, 64, 1):\n'
            '        previous: uint32 = data[i - 16]\n'
            '        data[i] = previous\n'
            '    return\n'
        )
        summary = compiler.storage.functions[
            'schedule'
        ].fixed_array_parameter_summary
        self.assertFalse(summary['data'].requires_initialized)
        self.assertTrue(summary['data'].fully_written_on_return)


if __name__ == '__main__':
    unittest.main()
