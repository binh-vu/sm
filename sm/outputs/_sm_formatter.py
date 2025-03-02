from __future__ import annotations

from pathlib import Path

from graph.retworkx import BaseEdge, BaseNode, RetworkXDiGraph, has_cycle
from sm.outputs.semantic_model import ClassNode, LiteralNode, SemanticModel, DataNode
from sm.namespaces.prelude import Namespace

def to_simple_yaml(sm: SemanticModel, ns: Namespace, outfile: Path):
    """Save the semantic model to a YAML file with simple formatting as follow:

    ```yaml
    version: "simple-1"
    model:
        <class_uri>:
            <property_uri>: <column name> | {"type": "entity" | "literal", value: <value>}
    prefixes:
        <namespace>: <url>
    ```

    Note:
        - the model must be a tree, an error will be thrown if the model contains cycles.
        - columns that are not used in the model will not be included in the output.
    """
    if has_cycle(sm):
        raise ValueError(
            "The model contains cycles, cannot convert to the simple YAML format"
        )

    output = {}

    def serialize_node(node: ClassNode | LiteralNode | DataNode, outdict: dict):
        if isinstance(node, ClassNode):
            outdict[node.abs_uri

    for u in sm.iter_nodes():
        if sm.in_degree(u.id) == 0:
            continue
