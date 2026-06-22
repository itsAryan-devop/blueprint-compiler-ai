r"""Integrity smoke test -- run after EVERY save.

A truncated or half-saved file fails to import or compile, so this catches that
whole class of problem instantly:

    .\venv\Scripts\python.exe smoke_test.py

It (1) imports every package -- which transitively loads/compiles every module
in contracts/, llm/, and pipeline/ -- and (2) compiles the top-level scripts.
Any incomplete file makes it fail loudly with the offending file name.
"""

import glob
import py_compile

import contracts  # noqa: F401  (importing = compile-checks the whole package)
import llm  # noqa: F401
import pipeline  # noqa: F401
import validation  # noqa: F401


def main() -> None:
    for path in sorted(glob.glob("*.py")):
        py_compile.compile(path, doraise=True)
    print("SMOKE OK: contracts / llm / pipeline / validation import; all top-level scripts compile.")


if __name__ == "__main__":
    main()
