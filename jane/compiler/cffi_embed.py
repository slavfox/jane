# Copyright (c) 2020, Slavfox
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
import logging
from hashlib import sha1
import os
import platform
import shutil
import sys
from distutils.ccompiler import CCompiler, new_compiler
from distutils.sysconfig import (
    customize_compiler,
    get_python_inc,
    get_config_var as distutils_var,
)
from pathlib import Path
from typing import Union
from textwrap import dedent

import cffi

logger = logging.getLogger(__name__)

pyproper_dir = Path(__file__).resolve().parent

PYPY = platform.python_implementation() == "PyPy"
NT = os.name == "nt"
DARWIN = sys.platform == "darwin"

if DARWIN:
    SHLIB_SUFFIX = ".dylib"
else:
    SHLIB_SUFFIX = distutils_var("SHLIB_SUFFIX")
    if SHLIB_SUFFIX is None:
        if NT:
            SHLIB_SUFFIX = ".dll"
        else:
            SHLIB_SUFFIX = ".so"


def lib_filename(libname: str) -> str:
    prefix = "lib" if not NT else ""
    return f"{prefix}{libname}{SHLIB_SUFFIX}"


def filename_lib(filename: str) -> str:
    if filename.startswith("lib") and not NT:
        filename = filename[3:]
    if filename.endswith(SHLIB_SUFFIX):
        filename = filename[: -len(SHLIB_SUFFIX)]
    return filename


PYLIB_DIR = Path(distutils_var("LIBDIR"))
if PYPY:
    PYLIB = "pypy3-c"
    PYLIB_FILENAME = lib_filename(PYLIB)
else:
    PYLIB_FILENAME = distutils_var("LDLIBRARY")
    PYLIB = filename_lib(PYLIB_FILENAME)
PYLIB_PATH = PYLIB_DIR / PYLIB_FILENAME


class Compiler:
    """
    Compiles the cffi entry point to the entire application.
    Can be made to build
    """

    PY_MAIN_DECL = "int py_main(int argc, char *argv[]);"

    PY_INIT_SRC = dedent(
        """
    from {jane_hash} import ffi

    @ffi.def_extern()
    def py_main(argc, argv):
        import sys
        sys.path.insert(0, 'lib/')
        sys.path.insert(0, 'lib/pylib.zip')
        sys.argv[:] = [ffi.string(argv[i]).decode() for i in range(argc)]
        from {import_path} import {entry_fun}
        res = {entry_fun}()
        return res
    """
    )

    C_ENTRY_POINT_SRC = dedent(
        f"""
    #ifndef CFFI_DLLEXPORT
    #  if defined(_MSC_VER)
    #    define CFFI_DLLEXPORT  extern __declspec(dllimport)
    #  else
    #    define CFFI_DLLEXPORT  extern
    #  endif
    #endif

    CFFI_DLLEXPORT {PY_MAIN_DECL}
    """
    )

    C_EXECUTABLE_SRC = dedent(
        f"""
    #include <Python.h>

    {PY_MAIN_DECL}

    int main(int argc, char *argv[]){{
        return py_main(argc, argv);
    }};
    """
    )

    def __init__(
        self,
        import_path: str,
        build_dir: Union[str, Path],
        executable: bool = True,
        program_name: str = None,
        compiler: str = None,
    ):
        # ToDo: more robust regex matching
        import_parts, self.entry_point = import_path.split(":")
        try:
            __import__(import_parts)
        except ImportError:
            raise ImportError(f"{import_parts} is not importable.")
        self._import_path_parts = import_parts.split(".")
        self.import_path = import_parts
        self.program_name = program_name or self._import_path_parts[0]

        if isinstance(build_dir, str):
            self.build_dir = Path(build_dir)
        else:
            self.build_dir = build_dir

        self._src_path: Path = self.build_dir / "src"
        self._dist_path: Path = self.build_dir / "dist"
        self._build_lib_path: Path = self._dist_path / "lib"
        self._entry_point_c_path: Path = self._src_path / "entry_point.c"
        self._executable_filename = f"{self.program_name}.c"
        self._hash = f"jane_{sha1(import_parts.encode()).hexdigest()}"

        self.ffi_builder: cffi.FFI = self._make_ffi_builder()
        self._compiler: CCompiler = new_compiler(compiler)
        customize_compiler(self._compiler)

    def _make_ffi_builder(self):
        ffi_builder = cffi.FFI()
        ffi_builder.embedding_api(self.PY_MAIN_DECL)

        ffi_builder.set_source(
            self._hash,
            self.C_ENTRY_POINT_SRC,
            include_dirs=[str(pyproper_dir)],
        )
        ffi_builder.embedding_init_code(
            self.PY_INIT_SRC.format(
                jane_hash=self._hash,
                import_path=self.import_path,
                entry_fun=self.entry_point,
            )
        )
        return ffi_builder

    def _prepare_entry_point(self):
        pass

    def output_sources(self):
        self._src_path.mkdir(parents=True, exist_ok=True)
        self.ffi_builder.emit_c_code(str(self._entry_point_c_path))
        with (self._src_path / self._executable_filename).open("w") as f:
            f.write(self.C_EXECUTABLE_SRC)

    def init_dependencies(self):
        py_inc = get_python_inc()
        platspec_py_inc = get_python_inc(plat_specific=1)

        self._compiler.add_include_dir(py_inc)
        self._compiler.add_include_dir(platspec_py_inc)

        # Workaround for virtualenvs
        self._build_lib_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Copying {PYLIB_PATH} to lib/")
        shutil.copy(str(PYLIB_PATH), str(self._dist_path / "lib"))
        self._compiler.add_library_dir(str(self._dist_path / "lib"))
        self._compiler.add_library(PYLIB)

    def compile(self, debug=False):
        self.output_sources()
        self.init_dependencies()
        objs = self._compiler.compile(
            [
                str(self._entry_point_c_path),
                str(self._src_path / self._executable_filename),
            ],
            debug=debug,
        )
        self._compiler.link_executable(
            objs,
            self.program_name,
            str(self._dist_path),
            extra_preargs=["-Wl,-rpath,./lib"],
        )


if __name__ == "__main__":
    Compiler("jane.foo:main", "build").compile()
