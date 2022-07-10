import os
import shutil
import sys

from setuptools import Distribution, Extension
from setuptools.command.build_ext import build_ext
from setuptools.errors import BaseError as DistutilsError
from setuptools.errors import CCompilerError

with_extensions = os.getenv("STARLITE_EXTENSIONS", None)

if with_extensions == "1" or with_extensions is None:
    build_extensions = True

if with_extensions == "0" or hasattr(sys, "pypy_version_info"):
    build_extensions = False

extensions = (
    [
        Extension("starlite.routing._route_map", ["starlite/routing/_route_map.c", "starlite/routing/_hashmap.c"]),
    ]
    if build_extensions
    else []
)


class ExtBuilder(build_ext):  # type: ignore[misc]
    # This class allows C extension building to fail.

    built_extensions: list[Extension] = []

    def run(self) -> None:
        try:
            build_ext.run(self)
        except (DistutilsError, FileNotFoundError):
            print("  Unable to build the C extensions, Starlite will use the pure python code instead.")  # noqa: T201

    def build_extension(self, ext: Extension) -> None:
        try:
            build_ext.build_extension(self, ext)
        except (CCompilerError, DistutilsError, ValueError):
            print(  # noqa: T201
                f'  Unable to build the "{ext.name}" C extension, '
                "Starlite will use the pure python version of the extension."
            )


def build(setup_kwargs: dict) -> dict:
    """
    This function is mandatory in order to build the extensions.
    """
    distribution = Distribution({"name": "starlite", "ext_modules": extensions})
    # distribution.package_dir = "starlite"  # type: ignore[attr-defined]

    cmd = build_ext(distribution)
    cmd.ensure_finalized()
    cmd.run()

    # Copy built extensions back to the project
    for output in cmd.get_outputs():
        relative_extension = os.path.relpath(output, cmd.build_lib)
        if not os.path.exists(output):
            continue

        shutil.copyfile(output, relative_extension)
        mode = os.stat(relative_extension).st_mode
        mode |= (mode & 0o444) >> 2
        os.chmod(relative_extension, mode)

    return setup_kwargs


if __name__ == "__main__":
    build({})
