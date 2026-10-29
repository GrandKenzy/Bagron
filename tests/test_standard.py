from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import CompilationError, Compiler


class StandardLibraryTests(unittest.TestCase):
    def test_print_writes_chain_using_windows_abi(self):
        project_source = Path(__file__).resolve().parents[1] / 'standard.bg'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(project_source, root / 'standard.bg')
            main = root / '_main.bg'
            main.write_text(
                'import standard\n'
                '@unsafe\n'
                'func main() int32:\n'
                '    message: chain = "Hola"\n'
                '    source: const char[6] = "Adios"\n'
                '    converted: chain = source\n'
                '    buffer: char[5] = "Hola"\n'
                '    print(message)\n'
                '    print(" / DOLLAR")\n'
                '    print(converted)\n'
                '    printa(buffer)\n'
                '    return 0\n',
                encoding='utf-8',
            )

            artifacts = Compiler().compile(main, executable=True)
            module = artifacts.ir.read_text(encoding='utf-8')
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(0, result.returncode)
        self.assertEqual(b'Hola / DOLLARAdiosHola\x00', result.stdout)
        self.assertEqual(5, module.count('call i32 @"WriteFile"'))
        self.assertRegex(module, r'call void @"print"\([^)]*i64 5\)')
        self.assertRegex(module, r'call void @"printa"\([^)]*i64 5, i64 1\)')

    def test_print_writes_immutable_global_chains(self):
        project_source = Path(__file__).resolve().parents[1] / 'standard.bg'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(project_source, root / 'standard.bg')
            (root / 'alphabet.bg').write_text(
                'public NumericString: chain = "0123456789"\n'
                'public AlphabetString: chain = '
                '"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"\n',
                encoding='utf-8',
            )
            main = root / '_main.bg'
            main.write_text(
                'import standard\n'
                'import alphabet\n'
                '@unsafe\n'
                'func main() int32:\n'
                '    print(NumericString)\n'
                '    print(AlphabetString)\n'
                '    return 0\n',
                encoding='utf-8',
            )

            artifacts = Compiler().compile(main, executable=True)
            module = artifacts.ir.read_text(encoding='utf-8')
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(0, result.returncode)
        self.assertEqual(
            b'0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz',
            result.stdout,
        )
        self.assertIn('getelementptr inbounds [11 x i8]', module)
        self.assertIn('getelementptr inbounds [53 x i8]', module)

    def test_printa_rejects_scalar_char(self):
        project_source = Path(__file__).resolve().parents[1] / 'standard.bg'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(project_source, root / 'standard.bg')
            main = root / '_main.bg'
            main.write_text(
                'import standard\n'
                '@unsafe\n'
                'func main() int32:\n'
                '    letter: char = "A"\n'
                '    printa(letter)\n'
                '    return 0\n',
                encoding='utf-8',
            )

            with self.assertRaisesRegex(CompilationError, 'printa'):
                Compiler().compile(main, executable=False)

    def test_printb_writes_raw_or_hex_bytes(self):
        project_source = Path(__file__).resolve().parents[1] / 'standard.bg'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(project_source, root / 'standard.bg')
            main = root / '_main.bg'
            main.write_text(
                'import standard\n'
                '@unsafe\n'
                'func main() int32:\n'
                '    raw: byte[3] = {65, 0, 255}\n'
                '    encoded: byte[2] = {0, 255}\n'
                '    printb(raw, false)\n'
                '    printb(encoded, true)\n'
                '    return 0\n',
                encoding='utf-8',
            )

            artifacts = Compiler().compile(main, executable=True)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(0, result.returncode)
        self.assertEqual(b'A\x00\xff00FF', result.stdout)

    def test_serialize_int_appends_decimal_text(self):
        project_source = Path(__file__).resolve().parents[1] / 'standard.bg'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(project_source, root / 'standard.bg')
            main = root / '_main.bg'
            main.write_text(
                'import standard\n'
                '@unsafe\n'
                'func main() int32:\n'
                '    positive: char[50] = "Mi edad es: "\n'
                '    negative: char[50] = "Negativo: "\n'
                '    zero: char[50] = "Cero: "\n'
                '    positioned: char[50] = "Posicion: 999"\n'
                '    serialize_int(positive, 20)\n'
                '    serialize_int(negative, -20)\n'
                '    serialize_int(zero, 0)\n'
                '    serialize_int_at(positioned, 10, 123)\n'
                '    printa(positive)\n'
                '    printa(negative)\n'
                '    printa(zero)\n'
                '    printa(positioned)\n'
                '    return 0\n',
                encoding='utf-8',
            )

            artifacts = Compiler().compile(main, executable=True)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(0, result.returncode)
        expected = b''.join(
            value.ljust(50, b'\x00')
            for value in (
                b'Mi edad es: 20',
                b'Negativo: -20',
                b'Cero: 0',
                b'Posicion: 123',
            )
        )
        self.assertEqual(expected, result.stdout)

    def test_nested_static_array_metadata_and_print_int(self):
        project_source = Path(__file__).resolve().parents[1] / 'standard.bg'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(project_source, root / 'standard.bg')
            main = root / '_main.bg'
            main.write_text(
                'import standard\n'
                '@unsafe\n'
                'func check_leaf(\n'
                '    data: int32[],\n'
                '    length: Len_t,\n'
                '    element_size: Size_t\n'
                ') int32:\n'
                '    if length != 4:\n'
                '        return 10\n'
                '    if element_size != 4:\n'
                '        return 11\n'
                '    if data[0] != 11:\n'
                '        return 12\n'
                '    if data[3] != -44:\n'
                '        return 13\n'
                '    print_int(data[0])\n'
                '    print(":")\n'
                '    print_int(data[3])\n'
                '    print("\\n")\n'
                '    return 0\n'
                '@unsafe\n'
                'func check_middle(\n'
                '    data: int32[],\n'
                '    length: Len_t,\n'
                '    element_size: Size_t\n'
                ') int32:\n'
                '    return check_leaf(data)\n'
                '@unsafe\n'
                'func check_outer(\n'
                '    data: int32[],\n'
                '    length: Len_t,\n'
                '    element_size: Size_t\n'
                ') int32:\n'
                '    return check_middle(data)\n'
                '@unsafe\n'
                'func main() int32:\n'
                '    values: int32[4] = {11, 22, 33, -44}\n'
                '    return check_outer(values)\n',
                encoding='utf-8',
            )

            artifacts = Compiler().compile(main, executable=True)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(0, result.returncode)
        self.assertEqual(b'11:-44\n', result.stdout)

    def test_nested_multiple_arrays_keep_metadata_and_contents_separate(self):
        project_source = Path(__file__).resolve().parents[1] / 'standard.bg'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(project_source, root / 'standard.bg')
            main = root / '_main.bg'
            main.write_text(
                'import standard\n'
                '@unsafe\n'
                'func check_leaf(\n'
                '    numbers: int32[],\n'
                '    numbers_length: Len_t,\n'
                '    numbers_size: Size_t,\n'
                '    raw: byte[],\n'
                '    raw_length: Len_t,\n'
                '    raw_size: Size_t\n'
                ') int32:\n'
                '    if numbers_length != 4:\n'
                '        return 10\n'
                '    if numbers_size != 4:\n'
                '        return 11\n'
                '    if raw_length != 3:\n'
                '        return 12\n'
                '    if raw_size != 1:\n'
                '        return 13\n'
                '    if numbers[0] != 11:\n'
                '        return 14\n'
                '    if numbers[3] != -44:\n'
                '        return 15\n'
                '    if raw[0] != 65:\n'
                '        return 16\n'
                '    if raw[1] != 0:\n'
                '        return 17\n'
                '    if raw[2] != 255:\n'
                '        return 18\n'
                '    print_int(numbers[0])\n'
                '    print(":")\n'
                '    print_int(numbers[3])\n'
                '    print("\\n")\n'
                '    printb(raw, false)\n'
                '    return 0\n'
                '@unsafe\n'
                'func check_middle(\n'
                '    numbers: int32[],\n'
                '    numbers_length: Len_t,\n'
                '    numbers_size: Size_t,\n'
                '    raw: byte[],\n'
                '    raw_length: Len_t,\n'
                '    raw_size: Size_t\n'
                ') int32:\n'
                '    return check_leaf(numbers, raw)\n'
                '@unsafe\n'
                'func check_outer(\n'
                '    numbers: int32[],\n'
                '    numbers_length: Len_t,\n'
                '    numbers_size: Size_t,\n'
                '    raw: byte[],\n'
                '    raw_length: Len_t,\n'
                '    raw_size: Size_t\n'
                ') int32:\n'
                '    return check_middle(numbers, raw)\n'
                '@unsafe\n'
                'func main() int32:\n'
                '    numbers: int32[4] = {11, 22, 33, -44}\n'
                '    raw: byte[3] = {65, 0, 255}\n'
                '    return check_outer(numbers, raw)\n',
                encoding='utf-8',
            )

            artifacts = Compiler().compile(main, executable=True)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(0, result.returncode)
        self.assertEqual(b'11:-44\nA\x00\xff', result.stdout)

    def test_recursive_chain_and_char_array_inversion_with_reordered_parameters(self):
        project_source = Path(__file__).resolve().parents[1] / 'standard.bg'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(project_source, root / 'standard.bg')
            main = root / '_main.bg'
            main.write_text(
                'import standard\n'
                '@unsafe\n'
                'func invert_forward(\n'
                '    chars: char[],\n'
                '    chars_length: Len_t,\n'
                '    chars_size: Size_t,\n'
                '    source: chain,\n'
                '    source_length: Len_t,\n'
                '    step: int32\n'
                ') int32:\n'
                '    if step > 10:\n'
                '        return 10\n'
                '    if chars_length != 12:\n'
                '        return 11\n'
                '    if chars_size != 1:\n'
                '        return 12\n'
                '    if source_length != 12:\n'
                '        return 13\n'
                '    expected: char = source[10 - step]\n'
                '    chars[step] = expected\n'
                '    if chars[step] != expected:\n'
                '        return 14\n'
                '    return invert_reverse(source, chars, step + 1)\n'
                '@unsafe\n'
                'func invert_reverse(\n'
                '    source: chain,\n'
                '    source_length: Len_t,\n'
                '    chars: char[],\n'
                '    chars_length: Len_t,\n'
                '    chars_size: Size_t,\n'
                '    step: int32\n'
                ') int32:\n'
                '    if source_length != 12:\n'
                '        return 20\n'
                '    if chars_length != 12:\n'
                '        return 21\n'
                '    if chars_size != 1:\n'
                '        return 22\n'
                '    if source[0] != 65:\n'
                '        return 23\n'
                '    if source[10] != 75:\n'
                '        return 24\n'
                '    if step > 10:\n'
                '        print(source)\n'
                '        print("|")\n'
                '        printa(chars)\n'
                '        return 0\n'
                '    return invert_forward(chars, source, step)\n'
                '@unsafe\n'
                'func main() int32:\n'
                '    chars: char[12] = "ABCDEFGHIJK"\n'
                '    source: chain = "ABCDEFGHIJK"\n'
                '    return invert_forward(chars, source, 0)\n',
                encoding='utf-8',
            )

            artifacts = Compiler().compile(main, executable=True)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(0, result.returncode)
        self.assertEqual(b'ABCDEFGHIJK|KJIHGFEDCBA\x00', result.stdout)

    def test_recursive_multiple_fixed_matrices_keep_shape_and_reference(self):
        project_source = Path(__file__).resolve().parents[1] / 'standard.bg'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(project_source, root / 'standard.bg')
            main = root / '_main.bg'
            main.write_text(
                'import standard\n'
                '@unsafe\n'
                'func walk_forward(\n'
                '    numbers: int32[2][3],\n'
                '    numbers_length: Len_t,\n'
                '    numbers_size: Size_t,\n'
                '    raw: byte[2][2],\n'
                '    raw_length: Len_t,\n'
                '    raw_size: Size_t,\n'
                '    step: int32\n'
                ') int32:\n'
                '    if numbers_length != 2:\n'
                '        return 10\n'
                '    if numbers_size != 12:\n'
                '        return 11\n'
                '    if raw_length != 2:\n'
                '        return 12\n'
                '    if raw_size != 2:\n'
                '        return 13\n'
                '    if numbers[0][0] != 11:\n'
                '        return 14\n'
                '    if raw[1][1] != 44:\n'
                '        return 15\n'
                '    if step == 10:\n'
                '        numbers[1][2] = 99\n'
                '        raw[0][1] = 7\n'
                '        if raw[0][1] != 7:\n'
                '            return 16\n'
                '        print_int(numbers[1][2])\n'
                '        return 0\n'
                '    return walk_reverse(raw, numbers, step + 1)\n'
                '@unsafe\n'
                'func walk_reverse(\n'
                '    raw: byte[2][2],\n'
                '    raw_length: Len_t,\n'
                '    raw_size: Size_t,\n'
                '    numbers: int32[2][3],\n'
                '    numbers_length: Len_t,\n'
                '    numbers_size: Size_t,\n'
                '    step: int32\n'
                ') int32:\n'
                '    if raw_length != 2:\n'
                '        return 20\n'
                '    if raw_size != 2:\n'
                '        return 21\n'
                '    if numbers_length != 2:\n'
                '        return 22\n'
                '    if numbers_size != 12:\n'
                '        return 23\n'
                '    if numbers[1][0] != 44:\n'
                '        return 24\n'
                '    if step == 10:\n'
                '        return walk_forward(numbers, raw, step)\n'
                '    return walk_forward(numbers, raw, step)\n'
                '@unsafe\n'
                'func main() int32:\n'
                '    numbers: int32[2][3] = {{11, 22, 33}, {44, 55, 66}}\n'
                '    raw: byte[2][2] = {{1, 2}, {3, 44}}\n'
                '    result: int32 = walk_forward(numbers, raw, 0)\n'
                '    if result == 0:\n'
                '        if numbers[1][2] != 99:\n'
                '            result = 30\n'
                '    if result == 0:\n'
                '        if raw[0][1] != 7:\n'
                '            result = 31\n'
                '    return result\n',
                encoding='utf-8',
            )

            artifacts = Compiler().compile(main, executable=True)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(0, result.returncode)
        self.assertEqual(b'99', result.stdout)

    def test_recursive_three_dimensional_matrices_preserve_outer_width(self):
        project_source = Path(__file__).resolve().parents[1] / 'standard.bg'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(project_source, root / 'standard.bg')
            main = root / '_main.bg'
            main.write_text(
                'import standard\n'
                '@unsafe\n'
                'func walk_forward(\n'
                '    numbers: int16[2][3][4],\n'
                '    numbers_length: Len_t,\n'
                '    numbers_size: Size_t,\n'
                '    raw3d: byte[3][2][2],\n'
                '    raw_length: Len_t,\n'
                '    raw_size: Size_t,\n'
                '    step: int32\n'
                ') int32:\n'
                '    if numbers_length != 2:\n'
                '        return 10\n'
                '    if numbers_size != 24:\n'
                '        return 11\n'
                '    if raw_length != 3:\n'
                '        return 12\n'
                '    if raw_size != 4:\n'
                '        return 13\n'
                '    if numbers[1][2][3] != 123:\n'
                '        return 14\n'
                '    if raw3d[2][1][1] != 77:\n'
                '        return 15\n'
                '    if step == 10:\n'
                '        numbers[1][2][3] = 321\n'
                '        raw3d[2][1][1] = 88\n'
                '        print_int(numbers[1][2][3])\n'
                '        return 0\n'
                '    return walk_reverse(raw3d, numbers, step + 1)\n'
                '@unsafe\n'
                'func walk_reverse(\n'
                '    raw3d: byte[3][2][2],\n'
                '    raw_length: Len_t,\n'
                '    raw_size: Size_t,\n'
                '    numbers: int16[2][3][4],\n'
                '    numbers_length: Len_t,\n'
                '    numbers_size: Size_t,\n'
                '    step: int32\n'
                ') int32:\n'
                '    if raw_length != 3:\n'
                '        return 20\n'
                '    if raw_size != 4:\n'
                '        return 21\n'
                '    if numbers_length != 2:\n'
                '        return 22\n'
                '    if numbers_size != 24:\n'
                '        return 23\n'
                '    if raw3d[0][1][0] != 55:\n'
                '        return 24\n'
                '    return walk_forward(numbers, raw3d, step)\n'
                '@unsafe\n'
                'func main() int32:\n'
                '    numbers: int16[2][3][4]\n'
                '    raw3d: byte[3][2][2]\n'
                '    numbers[1][2][3] = 123\n'
                '    raw3d[0][1][0] = 55\n'
                '    raw3d[2][1][1] = 77\n'
                '    result: int32 = walk_forward(numbers, raw3d, 0)\n'
                '    if result == 0:\n'
                '        if numbers[1][2][3] != 321:\n'
                '            result = 30\n'
                '    if result == 0:\n'
                '        if raw3d[2][1][1] != 88:\n'
                '            result = 31\n'
                '    return result\n',
                encoding='utf-8',
            )

            artifacts = Compiler().compile(main, executable=True)
            result = subprocess.run(
                [str(artifacts.executable)],
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(0, result.returncode)
        self.assertEqual(b'321', result.stdout)


if __name__ == '__main__':
    unittest.main()
