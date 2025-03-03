from __future__ import annotations

from collections import Counter
from pathlib import Path

import serde.yaml
from graph.retworkx import BaseEdge, BaseNode, RetworkXDiGraph, has_cycle
from sm.inputs.table import ColumnBasedTable
from sm.misc.prelude import UnreachableError
from sm.namespaces.prelude import Namespace
from sm.outputs.semantic_model import (
    ClassNode,
    DataNode,
    Edge,
    LiteralNode,
    LiteralNodeDataType,
    SemanticModel,
)


def ser_simple_tree_yaml(
    table: ColumnBasedTable, sm: SemanticModel, ns: Namespace, outfile: Path
):
    """Save the semantic model to a YAML file with simple formatting as follow:

    ```yaml
    version: "simple-tree-1"
    model:
        - type: <class_uri>
          props:
            <property_uri>: <column name> (must be string) or <column index> | {"type": "entity" | "literal", value: <value>} | { "type": <class_uri>, [prop: string]: ... }

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

    output = {"version": "simple-tree-1", "model": [], "prefixes": {}}
    used_uris = set()

    # precompute the column format
    col_fmt: dict[int, str | int] = {}
    counter = Counter((col.clean_name for col in table.columns))
    for col in table.columns:
        colname = col.clean_name or ""
        if colname.strip() == "" or counter[col.clean_name] > 1:
            col_fmt[col.index] = col.index
        else:
            col_fmt[col.index] = colname

    def serialize_node(node: ClassNode | LiteralNode | DataNode):
        if isinstance(node, ClassNode):
            used_uris.add(node.abs_uri)
            outdict = {"type": ns.get_rel_uri(node.abs_uri), "props": {}}
            for edge in sm.out_edges(node.id):
                used_uris.add(edge.abs_uri)
                outdict["props"][ns.get_rel_uri(edge.abs_uri)] = serialize_node(
                    sm.get_node(edge.target)
                )
            return outdict

        if isinstance(node, DataNode):
            return col_fmt[node.col_index]
        if isinstance(node, LiteralNode):
            if node.datatype == LiteralNodeDataType.Entity:
                type = "entity"
            else:
                type = "literal:{}".format(node.datatype.value)
            return {"type": type, "value": node.value}

        raise UnreachableError()

    for u in sm.iter_nodes():
        if sm.in_degree(u.id) > 0:
            continue
        if isinstance(u, DataNode):
            # skip data nodes that are not used
            continue
        output["model"].append(serialize_node(u))

    for uri in used_uris:
        prefix = ns.prefix_index.get(uri)
        if prefix is not None:
            output["prefixes"][prefix] = ns.prefix2ns[prefix]

    return serde.yaml.ser(output, outfile)


def deser_simple_tree_yaml(table: ColumnBasedTable, infile: Path) -> SemanticModel:
    indict = serde.yaml.deser(infile)
    assert indict["version"] == "simple-tree-1"

    sm = SemanticModel()
    name2col = {col.clean_name: col for col in table.columns}
    namespace = Namespace.from_prefix2ns(indict["prefixes"])

    def deserialize_node(obj: dict | str | int):
        if isinstance(obj, str):
            # must be a column name
            node = DataNode(col_index=name2col[obj].index, label=obj)
            sm.add_node(node)
            return node
        if isinstance(obj, int):
            node = DataNode(
                col_index=obj,
                label=table.get_column_by_index(obj).clean_name or "",
            )
            sm.add_node(node)
            return node
        assert isinstance(obj, dict)
        if "value" in obj:
            node = LiteralNode(
                value=obj["value"],
                datatype=(
                    LiteralNodeDataType.Entity
                    if obj["type"] == "entity"
                    else LiteralNodeDataType(obj["type"].split(":")[1])
                ),
            )
            sm.add_node(node)
            return node

        node = ClassNode(
            abs_uri=namespace.get_abs_uri(obj["type"]), rel_uri=obj["type"]
        )
        sm.add_node(node)
        for prop, value in obj["props"].items():
            edge = Edge(
                source=node.id,
                target=deserialize_node(value).id,
                abs_uri=namespace.get_abs_uri(prop),
                rel_uri=prop,
            )
            sm.add_edge(edge)
        return node

    for node in indict["model"]:
        deserialize_node(node)
    return sm
