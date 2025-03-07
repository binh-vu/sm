from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Sequence

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
            <property_uri>: <node>

    prefixes:
        <namespace>: <url>
    ```

    If `<node>` can be:
        - the column name (string)
        - column index (`{column: <index>}`)
        - a literal value (`{literal:<type>: <value>}`)
        - an entity value (`{entity: <value>}`)
        - a nested class (`{type: <class_uri>, props: {...}}`)
        - a list of the above for multiple values for the same property.

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
    col_fmt: dict[int, str | dict] = {}
    counter = Counter((col.clean_name for col in table.columns))
    for col in table.columns:
        colname = col.clean_name or ""
        if colname.strip() == "" or counter[col.clean_name] > 1:
            col_fmt[col.index] = {"column": col.index}
        else:
            col_fmt[col.index] = colname

    def serialize_node(node: ClassNode | LiteralNode | DataNode):
        if isinstance(node, ClassNode):
            used_uris.add(node.abs_uri)
            outdict = {"type": ns.get_rel_uri(node.abs_uri), "props": {}}
            for edge in sm.out_edges(node.id):
                used_uris.add(edge.abs_uri)
                prop = ns.get_rel_uri(edge.abs_uri)
                ser_node = serialize_node(sm.get_node(edge.target))
                if prop in outdict["props"]:
                    if not isinstance(outdict["props"], Sequence):
                        outdict["props"][prop] = [outdict["props"][prop]]
                    outdict["props"][prop].append(ser_node)
                else:
                    outdict["props"][prop] = ser_node
            return outdict

        if isinstance(node, DataNode):
            return col_fmt[node.col_index]
        if isinstance(node, LiteralNode):
            if node.datatype == LiteralNodeDataType.Entity:
                key = "entity"
            else:
                key = "literal-{}".format(node.datatype.value)
            return {key: node.value}

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
    if len(indict["prefixes"]) == 0:
        assert len(indict["model"]) == 0
        return sm
    namespace = Namespace.from_prefix2ns(indict["prefixes"])

    def deserialize_node(
        obj: list | dict | str | int,
    ) -> DataNode | LiteralNode | ClassNode | list[DataNode | LiteralNode | ClassNode]:
        if isinstance(obj, str):
            if not sm.has_data_node(name2col[obj].index):
                # must be a column name
                node = DataNode(col_index=name2col[obj].index, label=obj)
                sm.add_node(node)
            else:
                node = sm.get_data_node(name2col[obj].index)
            return node

        if isinstance(obj, list):
            # recursive deserialization
            return [deserialize_node(o) for o in obj]  # type: ignore

        if isinstance(obj, int):
            node = DataNode(
                col_index=obj,
                label=table.get_column_by_index(obj).clean_name or "",
            )
            sm.add_node(node)
            return node

        assert isinstance(obj, dict)
        if "column" in obj:
            node = DataNode(
                col_index=obj["column"],
                label=table.get_column_by_index(obj["column"]).clean_name or "",
            )
            sm.add_node(node)
            return node

        if "props" not in obj:
            _type, _value = next(iter((obj.items())))
            node = LiteralNode(
                value=_value,
                datatype=(
                    LiteralNodeDataType.Entity
                    if _type == "entity"
                    else LiteralNodeDataType(_type.split("-", 1)[1])
                ),
            )
            if sm.has_literal_node(node.value):
                return sm.get_literal_node(node.value)
            sm.add_node(node)
            return node

        node = ClassNode(
            abs_uri=namespace.get_abs_uri(obj["type"]), rel_uri=obj["type"]
        )
        sm.add_node(node)
        for prop, value in obj["props"].items():
            deser_values = deserialize_node(value)
            if not isinstance(deser_values, list):
                deser_values = [deser_values]
            for deser_value in deser_values:
                edge = Edge(
                    source=node.id,
                    target=deser_value.id,
                    abs_uri=namespace.get_abs_uri(prop),
                    rel_uri=prop,
                )
                sm.add_edge(edge)
        return node

    for node in indict["model"]:
        deserialize_node(node)
    return sm
