# Copyright (c) 2020 Slavfox
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
import logging
import py_compile
import os
import shutil
from modulefinder import Module, ModuleFinder
from pathlib import Path
from pprint import pformat
from typing import Union
from warnings import catch_warnings, simplefilter
from distutils.sysconfig import get_python_lib

logger = logging.getLogger(__name__)


def pyc_output_filename(module_name: str) -> str:
    segments = module_name.split(".")
    segments[-1] = segments[-1] + ".pyc"
    return os.path.join(*segments)


def initpyc_output_filename(module_name: str) -> str:
    segments = module_name.split(".")
    segments.append("__init__.pyc")
    return os.path.join(*segments)


class LibPackager:
    KNOWN_PROBLEMATIC_MODULES = ["setuptools.msvc"]

    def __init__(self, build_dir: Union[str, Path]):
        if isinstance(build_dir, str):
            self.build_dir = Path(build_dir)
        else:
            self.build_dir = build_dir

        self.zip_build_dir = self.build_dir / "libs"
        self.dist_lib_dir = self.build_dir / "dist" / "lib"
        self.dylib_dir = self.build_dir / "dist" / "lib" / "lib-dynload"
        self.stdlib_path = get_python_lib(standard_lib=True)
        self.stdlib_name = os.path.basename(self.stdlib_path)

        self.finder = ModuleFinder()

    def find_modules(self, entry_point: str):
        self.finder.run_script(entry_point)
        return self.finder.modules

    def copy_modules(self):
        shutil.rmtree(self.zip_build_dir, ignore_errors=True)
        self.zip_build_dir.mkdir(parents=True, exist_ok=True)
        self.dylib_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Copying stdlib.")
        self._copy_stdlib()

        logger.info(f"Packaging {self.stdlib_name}.zip")
        shutil.make_archive(
            self.build_dir / "dist" / "lib" / "pylib",
            "zip",
            str(self.zip_build_dir / self.stdlib_name),
        )

        logger.info("Copying modules to build directory.")
        for name, mod in self.finder.modules.items():
            self._copy_module(mod)

        logger.info("Packaging pylib.zip.")
        shutil.make_archive(
            self.build_dir / "dist" / "lib" / "pylib",
            "zip",
            str(self.zip_build_dir),
        )
        logger.info("Done!")
        logger.warning(f"Bad modules: \n" f"{pformat(self.finder.badmodules)}")

    def _copy_stdlib(self):
        # broken atm
        def copier(src: str, dest: str):
            if src.endswith(".py"):
                try:
                    with catch_warnings():
                        simplefilter("ignore")
                        py_compile.compile(src, dest)
                except SyntaxError:
                    return
            elif src.endswith(".pyc"):
                shutil.copy2(src, dest)
            else:
                relpath = Path(src).relative_to(self.stdlib_path)
                shutil.copy2(src, str(self.dist_lib_dir / relpath))

        shutil.copytree(
            self.stdlib_path, str(self.zip_build_dir / self.stdlib_name),
            copy_function=copier,
            ignore=shutil.ignore_patterns('test', 'lib2to3')
        )

    def _copy_module(self, module: Module):
        if not module.__file__:
            # sys, builtins, etc - just return quietly
            return
        module_path = Path(module.__file__)
        if module_path.name.endswith(".py"):
            if str(module_path).startswith(str(self.stdlib_path)):
                return
            if module_path.name == "__init__.py":
                target_path = (
                    self.zip_build_dir
                    / "lib"
                    / initpyc_output_filename(module.__name__)
                )
            else:
                target_path = (
                    self.zip_build_dir
                    / "lib"
                    / pyc_output_filename(module.__name__)
                )
            target_path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Compiling {module.__name__} to {target_path}")
            py_compile.compile(str(module_path), str(target_path))
        else:
            # dynamic libraries, copy them
            shutil.copy2(
                str(module_path),
                self.dylib_dir / "lib-dynload" / module_path.name
            )
