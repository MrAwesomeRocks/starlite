# https://github.com/sdispater/pendulum/commit/a2267c02437d6c1ea613a55dbfb7085d376e997b#diff-b70bfb027a8ef3ec4ab07a53a3b8ba83e63334ba3ce5ca6d9d773900ed452e5e
# https://gist.github.com/dmontagu/b91d5fd5319ae6fe004ecd28771d985e
# https://github.com/wjakob/nanobind_example
# https://github.com/wjakob/nanobind
# https://github.com/pybind/cmake_example/issues

import os
import re
import subprocess
import sys
from typing import Any

from packaging.version import Version
from setuptools.command.build_ext import build_ext  # type: ignore[import]
from setuptools.extension import Extension  # type: ignore[import]

# Convert distutils Windows platform specifiers to CMake -A arguments
PLAT_TO_CMAKE = {
    "win32": "Win32",
    "win-amd64": "x64",
    "win-arm32": "ARM",
    "win-arm64": "ARM64",
}


# A CMakeExtension needs a sourcedir instead of a file list.
# The name must be the _single_ output extension from the CMake build.
# If you need multiple extensions, see scikit-build.
class CMakeExtension(Extension):  # type: ignore[misc]
    def __init__(self, name: str, sourcedir: str = "") -> None:
        Extension.__init__(self, name, sources=[])
        self.sourcedir = os.path.abspath(sourcedir)


class ExtensionBuilder(build_ext):  # type: ignore[misc]
    def run(self) -> None:
        self.validate_cmake()
        super().run()

    def build_extension(self, ext: Extension) -> None:
        if isinstance(ext, CMakeExtension):
            self.build_cmake_extension(ext)
        else:
            super().build_extension(ext)

    def validate_cmake(self) -> None:
        """Check for valid CMake version."""
        cmake_extensions = [x for x in self.extensions if isinstance(x, CMakeExtension)]
        if len(cmake_extensions) > 0:
            try:
                out = subprocess.check_output(["cmake", "--version"])
            except OSError as e:
                raise RuntimeError(
                    "CMake must be installed to build the following extensions: "
                    + ", ".join(e.name for e in cmake_extensions)
                ) from e

            cmake_version = Version(re.search(r"version\s*([\d.]+)", out.decode()).group(1))  # type: ignore
            if cmake_version < Version("3.18.0"):
                raise RuntimeError("CMake >= 3.18.0 is required to build extentions")

    def build_cmake_extension(self, ext: Extension) -> None:
        """Build a CMake native extension."""
        extdir = os.path.abspath(os.path.dirname(self.get_ext_fullpath(ext.name)))

        # required for auto-detection & inclusion of auxiliary "native" libs
        if not extdir.endswith(os.path.sep):
            extdir += os.path.sep

        debug = int(os.environ.get("DEBUG", 0)) if self.debug is None else self.debug
        cfg = "Debug" if debug else "Release"

        # CMake lets you override the generator - we need to check this.
        # Can be set with Conda-Build, for example.
        cmake_generator = os.environ.get("CMAKE_GENERATOR", "")

        # Set Python_EXECUTABLE instead if you use PYBIND11_FINDPYTHON
        # EXAMPLE_VERSION_INFO shows you how to pass a value into the C++ code
        # from Python.
        cmake_args = [
            f"-DCMAKE_LIBRARY_OUTPUT_DIRECTORY={extdir}",
            f"-DPYTHON_EXECUTABLE={sys.executable}",
            f"-DCMAKE_BUILD_TYPE={cfg}",  # not used on MSVC, but no harm
        ]
        build_args = []
        # Adding CMake arguments set as environment variable
        # (needed e.g. to build for ARM OSx on conda-forge)
        if "CMAKE_ARGS" in os.environ:
            cmake_args += [item for item in os.environ["CMAKE_ARGS"].split(" ") if item]

        # In this example, we pass in the version to C++. You might not need to.
        cmake_args += [f"-DEXAMPLE_VERSION_INFO={self.distribution.get_version()}"]

        if self.compiler.compiler_type != "msvc":
            # Using Ninja-build since it a) is available as a wheel and b)
            # multithreads automatically. MSVC would require all variables be
            # exported for Ninja to pick it up, which is a little tricky to do.
            # Users can override the generator with CMAKE_GENERATOR in CMake
            # 3.15+.
            if not cmake_generator or cmake_generator == "Ninja":
                try:
                    import ninja  # pylint: disable=import-outside-toplevel

                    ninja_executable_path = os.path.join(ninja.BIN_DIR, "ninja")
                    cmake_args += [
                        "-GNinja",
                        f"-DCMAKE_MAKE_PROGRAM:FILEPATH={ninja_executable_path}",
                    ]
                except ImportError:
                    pass
        else:
            # Single config generators are handled "normally"
            single_config = any(x in cmake_generator for x in ("NMake", "Ninja"))

            # CMake allows an arch-in-generator style for backward compatibility
            contains_arch = any(x in cmake_generator for x in ("ARM", "Win64"))

            # Specify the arch if using MSVC generator, but only if it doesn't
            # contain a backward-compatibility arch spec already in the
            # generator name.
            if not single_config and not contains_arch:
                cmake_args += ["-A", PLAT_TO_CMAKE[self.plat_name]]

            # Multi-config generators have a different way to specify configs
            if not single_config:
                cmake_args += [f"-DCMAKE_LIBRARY_OUTPUT_DIRECTORY_{cfg.upper()}={extdir}"]
                build_args += ["--config", cfg]

        if sys.platform.startswith("darwin"):
            # Cross-compile support for macOS - respect ARCHFLAGS if set
            arches = re.findall(r"-arch (\S+)", os.environ.get("ARCHFLAGS", ""))
            if arches:
                cmake_args += [f"-DCMAKE_OSX_ARCHITECTURES={';'.join(arches)}"]

        # Set CMAKE_BUILD_PARALLEL_LEVEL to control the parallel build level
        # across all generators.
        if "CMAKE_BUILD_PARALLEL_LEVEL" not in os.environ:
            # self.parallel is a Python 3 only way to set parallel jobs by hand
            # using -j in the build_ext call, not supported by pip or PyPA-build.
            if hasattr(self, "parallel") and self.parallel:
                # CMake 3.12+ only.
                build_args += [f"-j{self.parallel}"]

        build_temp = os.path.join(self.build_temp, ext.name)
        if not os.path.exists(build_temp):
            os.makedirs(build_temp)

        subprocess.check_call(["cmake", ext.sourcedir] + cmake_args, cwd=build_temp)
        subprocess.check_call(["cmake", "--build", "."] + build_args, cwd=build_temp)


def build(setup_kwargs: dict[str, Any]) -> dict[str, Any]:
    """Poetry entrypoint."""
    cmake_modules = [CMakeExtension("starlite._extensions.radix_tree")]
    ext_modules = cmake_modules

    setup_kwargs.update(
        {
            "ext_modules": ext_modules,
            "cmdclass": dict(build_ext=ExtensionBuilder),
            "zip_safe": False,
        }
    )
    return setup_kwargs


if __name__ == "__main__":
    print(build({}))
