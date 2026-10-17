import shutil
import tempfile
import unittest
from pathlib import Path

from core.compiler import compile as compile_project


class TestAggressiveModules(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="ec_test_modules_"))
        self.modules_dir = self.test_dir / "modules"
        self.modules_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_diamond_import_reproducible_and_no_duplicate(self):
        """
        Escenario Diamante:
        main importa mod_a y mod_b.
        Tanto mod_a como mod_b importan mod_c.
        mod_c sólo debe parsearse y añadirse una única vez,
        y mod_c debe estar emitido antes de mod_a y mod_b.
        """
        (self.modules_dir / "mod_c.egl").write_text("x: int = 100\n", encoding="utf-8")
        (self.modules_dir / "mod_a.egl").write_text("import mod_c\ny: int = 200\n", encoding="utf-8")
        (self.modules_dir / "mod_b.egl").write_text("import mod_c\nz: int = 300\n", encoding="utf-8")

        main_content = (
            "import mod_a\n"
            "import mod_b\n"
            "total: int = 500\n"
        )
        (self.test_dir / "main.egl").write_text(main_content, encoding="utf-8")

        storage = compile_project(self.test_dir)

        # 1. Comprobar que mod_c no se duplicó
        module_stems = [m.root.stem for m in storage.ordered_modules]
        self.assertEqual(module_stems.count("mod_c"), 1)

        # 2. Comprobar orden de dependencias: mod_c antes que mod_a y mod_b
        idx_c = module_stems.index("mod_c")
        idx_a = module_stems.index("mod_a")
        idx_b = module_stems.index("mod_b")

        self.assertLess(idx_c, idx_a, "mod_c debe emitirse antes que mod_a")
        self.assertLess(idx_c, idx_b, "mod_c debe emitirse antes que mod_b")

    def test_cycle_dependency_detection(self):
        """
        Escenario Ciclo:
        mod_1 importa mod_2, y mod_2 importa mod_1.
        Debe lanzar RuntimeError alertando sobre dependencia circular.
        """
        (self.modules_dir / "mod_alpha.egl").write_text("import mod_beta\n", encoding="utf-8")
        (self.modules_dir / "mod_beta.egl").write_text("import mod_alpha\n", encoding="utf-8")

        (self.test_dir / "main.egl").write_text("import mod_alpha\n", encoding="utf-8")

        with self.assertRaises(RuntimeError) as ctx:
            compile_project(self.test_dir)

        self.assertIn("Dependencia circular detectada", str(ctx.exception))

    def test_alias_reuses_canonical_cache(self):
        """
        Escenario Re-import con Alias:
        main importa mod_x directamente y también con alias.
        Debe compartir la misma instancia en loaded_modules.
        """
        (self.modules_dir / "mod_x.egl").write_text("valor: int = 42\n", encoding="utf-8")

        main_content = (
            "import mod_x\n"
            "import mod_x as x_alias\n"
        )
        (self.test_dir / "main.egl").write_text(main_content, encoding="utf-8")

        storage = compile_project(self.test_dir)

        self.assertIn("mod_x", storage.modules)
        self.assertIn("x_alias", storage.modules)
        self.assertIs(storage.modules["mod_x"], storage.modules["x_alias"])
        self.assertEqual(len(storage.ordered_modules), 1)

    def test_deep_dependency_chain_emission_order(self):
        """
        Cadena: main -> mod_1 -> mod_2 -> mod_3 -> mod_4
        El orden estricto de emisión en C debe ser:
        mod_4, mod_3, mod_2, mod_1
        """
        (self.modules_dir / "mod_4.egl").write_text("v4: int = 4\n", encoding="utf-8")
        (self.modules_dir / "mod_3.egl").write_text("import mod_4\nv3: int = 3\n", encoding="utf-8")
        (self.modules_dir / "mod_2.egl").write_text("import mod_3\nv2: int = 2\n", encoding="utf-8")
        (self.modules_dir / "mod_1.egl").write_text("import mod_2\nv1: int = 1\n", encoding="utf-8")

        (self.test_dir / "main.egl").write_text("import mod_1\nvmain: int = 0\n", encoding="utf-8")

        storage = compile_project(self.test_dir)
        stems = [m.root.stem for m in storage.ordered_modules]
        self.assertEqual(stems, ["mod_4", "mod_3", "mod_2", "mod_1"])

    def test_mangled_struct_and_enum_cross_module(self):
        """
        mod_types define Color (enum) y Vector (struct).
        main importa mod_types y declara una variable de tipo Vector.
        Verificar que ambos tengan su c_name mangled y que la variable en main
        utilice el tipo de C mangled del struct.
        """
        types_code = (
            "enum Color:\n"
            "    RED\n"
            "    GREEN = 5\n"
            "\n"
            "struct Vector:\n"
            "    x: int\n"
            "    y: int\n"
        )
        (self.modules_dir / "mod_types.egl").write_text(types_code, encoding="utf-8")

        main_code = (
            "import mod_types\n"
            "v: Vector\n"
        )
        (self.test_dir / "main.egl").write_text(main_code, encoding="utf-8")

        storage = compile_project(self.test_dir)
        mod_types = storage.modules["mod_types"]

        # 1. Comprobar c_name mangled en Enum y Struct
        color_enum = mod_types.enums["Color"]
        vector_struct = mod_types.structs["Vector"]
        self.assertTrue(color_enum.c_name.startswith("_ec_"))
        self.assertTrue(color_enum.c_name.endswith("_Color"))
        self.assertTrue(vector_struct.c_name.startswith("_ec_"))
        self.assertTrue(vector_struct.c_name.endswith("_Vector"))

        # 2. Comprobar que la variable 'v' en main resolvió su tipo C al mangled del struct
        var_v = storage.variables["v"]
        from core.backend.ec.visitors.variable import visit_var
        decl_v, _ = visit_var(var_v, storage=storage)
        self.assertIn(vector_struct.c_name, decl_v)


if __name__ == '__main__':
    unittest.main()
