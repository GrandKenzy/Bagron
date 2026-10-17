import sys
import unittest
from pathlib import Path

# Asegurar que la raíz del proyecto esté en sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import vendor


def run_all_tests():
    test_dir = ROOT / 'test'
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(test_dir), pattern='test_*.py')

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    run_all_tests()
