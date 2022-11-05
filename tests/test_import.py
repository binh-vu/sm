import pkgutil
import sm
from pathlib import Path
from importlib import import_module


def test_import(pkg=sm):
    stack = [(pkg.__name__, Path(pkg.__file__).parent.absolute())]

    while len(stack) > 0:
        pkgname, pkgpath = stack.pop()
        for m in pkgutil.iter_modules([str(pkgpath)]):
            mname = f"{pkgname}.{m.name}"
            if m.ispkg:
                stack.append((mname, pkgpath / m.name))
            import_module(mname)
