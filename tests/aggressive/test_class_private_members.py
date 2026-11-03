from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class ClassPrivateMemberTests(unittest.TestCase):
    def compile_source(self, source: str, *, executable: bool = False):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / '_main.bg'
        path.write_text(source, encoding='utf-8')
        try:
            result = Compiler().compile(path, executable=executable)
        except Exception:
            directory.cleanup()
            raise
        return directory, result

    def test_private_fields_and_methods_work_inside_the_declaring_class(self):
        source = (
            'class Account:\n'
            '    func __init__(value: int32) void:\n'
            '        self._balance = value\n'
            '    func _close() int32:\n'
            '        return self._balance\n'
            '    func close() int32:\n'
            '        return self._close()\n'
            'func main() int32:\n'
            '    account: Account = Account(7)\n'
            '    return account.close() - 7\n'
        )
        directory, artifacts = self.compile_source(source, executable=True)
        try:
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )
        finally:
            directory.cleanup()
        self.assertEqual(0, result.returncode)

    def test_private_field_is_rejected_outside_the_class(self):
        with self.assertRaisesRegex(CompilationError, 'atributo privado'):
            self.compile_source(
                'class Box:\n'
                '    func __init__(value: int32) void:\n'
                '        self._value = value\n'
                'func main() int32:\n'
                '    box: Box = Box(3)\n'
                '    return box._value\n'
            )

    def test_private_method_is_rejected_outside_the_class(self):
        with self.assertRaisesRegex(CompilationError, 'metodo privado'):
            self.compile_source(
                'class Box:\n'
                '    func __init__(value: int32) void:\n'
                '        self._value = value\n'
                '    func _read() int32:\n'
                '        return self._value\n'
                'func main() int32:\n'
                '    box: Box = Box(3)\n'
                '    return box._read()\n'
            )

    def test_private_parent_members_are_not_visible_in_a_subclass(self):
        with self.assertRaisesRegex(CompilationError, 'atributo privado'):
            self.compile_source(
                'class Base:\n'
                '    func __init__(value: int32) void:\n'
                '        self._value = value\n'
                'class Child(Base):\n'
                '    func __init__(value: int32) void:\n'
                '        super.__init__(value)\n'
                '    func read() int32:\n'
                '        return self._value\n'
                'func main() int32:\n'
                '    child: Child = Child(3)\n'
                '    return child.read()\n'
            )


if __name__ == '__main__':
    unittest.main()

