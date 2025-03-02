from __future__ import annotations
from pathlib import Path

from sm.outputs.semantic_model import SemanticModel


class SmYamlFormatter: ...


def to_simple_yaml(obj: SemanticModel, outfile: Path):
    # return SmYamlFormatter().to_simple_yaml(obj)
