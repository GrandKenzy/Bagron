from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import Compiler


class NestedModuleIntegrationTests(unittest.TestCase):
    def test_nested_modules_execute_and_leave_no_workspace_artifacts(self):
        directory = tempfile.TemporaryDirectory(prefix='bagron-nested-modules-')
        root = Path(directory.name)
        try:
            modules = root / 'modules'
            (modules / 'ui' / 'rendering').mkdir(parents=True)
            (modules / 'ui' / 'widgets.bg').write_text(
                'public func value() int32:\n'
                '    return 7\n',
                encoding='utf-8',
            )
            (modules / 'ui' / 'rendering' / 'draw.bg').write_text(
                'import widgets\n'
                'public func draw() int32:\n'
                '    return widgets.value()\n',
                encoding='utf-8',
            )
            main = root / 'main.bg'
            main.write_text(
                'import draw\n'
                'func main() int32:\n'
                '    return draw.draw()\n',
                encoding='utf-8',
            )

            artifacts = Compiler().compile(main, executable=True)
            self.assertTrue(artifacts.executable.is_file())
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )
            self.assertEqual(7, result.returncode)
        finally:
            directory.cleanup()

        self.assertFalse(root.exists())


if __name__ == '__main__':
    unittest.main()
