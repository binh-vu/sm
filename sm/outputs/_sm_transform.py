from __future__ import annotations

from copy import copy
from typing import Callable, Literal, Mapping, Optional, Sequence

from graph.interface import NodeID
from rdflib import RDFS
from sm.namespaces.namespace import KnowledgeGraphNamespace
from sm.outputs.semantic_model import (
    ClassNode,
    DataNode,
    Edge,
    LiteralNode,
    LiteralNodeDataType,
    SemanticModel,
)
from sm.typing import IRI, InternalID


def replace_class_nodes_by_subject_columns(sm: SemanticModel, id_props: set[IRI]):
    """Replace a class node by its subject column (if have). One class node must have maximum one subject column"""
    rm_nodes = []
    for cnode in sm.iter_nodes():
        if isinstance(cnode, ClassNode):
            inedges = sm.in_edges(cnode.id)
            outedges = sm.out_edges(cnode.id)
            id_edges = [outedge for outedge in outedges if outedge.abs_uri in id_props]
            if len(id_edges) == 0:
                continue
            if len(id_edges) > 1:
                raise Exception(
                    f"Assuming one class node only has one subject column. Node: {cnode.id} have {len(id_edges)} subject columns: {id_edges}"
                )

            id_edge = id_edges[0]

            # update edges
            for inedge in inedges:
                sm.remove_edge(inedge.id)
                inedge.target = id_edge.target
                sm.add_edge(inedge)
            for outedge in outedges:
                sm.remove_edge(outedge.id)
                outedge.source = id_edge.target
                sm.add_edge(outedge)
            sm.remove_edge(id_edge.id)
            rm_nodes.append(cnode.id)
    for uid in rm_nodes:
        sm.remove_node(uid)


def remove_isolated_nodes(sm: SemanticModel) -> None:
    """In-placed remove isolated nodes in a semantic model"""
    rm_nodes = []
    for n in sm.iter_nodes():
        if sm.degree(n.id) == 0:
            rm_nodes.append(n.id)
    for uid in rm_nodes:
        sm.remove_node(uid)


def remove_literal_nodes(sm: SemanticModel):
    for n in sm.iter_nodes():
        if isinstance(n, LiteralNode):
            sm.remove_node(n.id)


def create_sm_nodes(
    columns: Sequence[str] | Mapping[int, str],
) -> Mapping[int, ClassNode | DataNode | LiteralNode]:
    """Create a mapping from column index to DataNode from the given columns"""
    nodes = {}
    if isinstance(columns, Sequence):
        for ci, cname in enumerate(columns):
            nodes[ci] = DataNode(ci, cname)
    else:
        for ci, cname in columns.items():
            nodes[ci] = DataNode(ci, cname)
    return nodes


def create_sm_from_cta_cpa(
    kgns: KnowledgeGraphNamespace,
    nodes: Mapping[NodeID, ClassNode | DataNode | LiteralNode],
    cpa: Sequence[tuple[NodeID, NodeID, InternalID]],
    cta: Mapping[int, InternalID],
    validate: bool = True,
    on_untype_source_column_node: Literal[
        "create-class", "remove-link"
    ] = "create-class",
    get_cls_label: Optional[Callable[[InternalID], str]] = None,
    get_prop_label: Optional[Callable[[InternalID], str]] = None,
) -> SemanticModel:
    """Create a semantic model from outputs of CPA and CTA tasks

    # Arguments
        nodes: a mapping from node id to DataNode or LiteralNode (leaf nodes) or Statement (represent n-ary relation)
            that we can't generate automatically from the cta (sources and targets in CPA should all be in this map).
        cpa: list of triples (source, target, predicate)
        cta: mapping from column index to class id
        validate: whether to validate the input to make sure it's correct classes and properties
    """
    if get_cls_label is None:
        get_cls_label = lambda ent_id: kgns.get_rel_uri(kgns.id_to_uri(ent_id))
    if get_prop_label is None:
        get_prop_label = lambda prop_id: kgns.get_rel_uri(kgns.id_to_uri(prop_id))

    if validate:
        for source, target, predicate in cpa:
            assert kgns.is_id(predicate)
        for col_index, ent_id in cta.items():
            assert kgns.is_id(ent_id)
        for node in nodes.values():
            if isinstance(node, ClassNode):
                assert kgns.is_uri_in_ns(node.abs_uri)
            elif (
                isinstance(node, LiteralNode)
                and node.datatype == LiteralNodeDataType.Entity
            ):
                assert kgns.is_uri(node.value) and kgns.is_uri_in_main_ns(node.value)

    sm = SemanticModel()
    # make a copy because when we add node into sm, we will modify the node id
    nodes = {uid: copy(u) for uid, u in nodes.items()}

    classmap = {}  # mapping from column to its class node
    # mapping from node id to sm node id, this mapping is built dynamically when iterating over cpa result.
    nodemap: dict[NodeID, int] = {}

    col2id = {u.col_index: uid for uid, u in nodes.items() if isinstance(u, DataNode)}
    for col_index, ent_id in cta.items():

        # somehow, they may end-up predict multiple classes, we need to select one
        if ent_id.find(" ") != -1:
            ent_id = ent_id.split(" ")[0]
        curl = kgns.id_to_uri(ent_id)

        cnode = ClassNode(
            abs_uri=curl,
            rel_uri=kgns.get_rel_uri(kgns.id_to_uri(ent_id)),
            readable_label=get_cls_label(ent_id),
        )
        dnode = nodes[col2id[col_index]]
        sm.add_node(cnode)
        nodemap[col2id[col_index]] = sm.add_node(dnode)
        classmap[col_index] = cnode.id
        sm.add_edge(
            Edge(
                source=cnode.id,
                target=dnode.id,
                abs_uri=str(RDFS.label),
                rel_uri=kgns.get_rel_uri(RDFS.label),
            )
        )

    for source, target, predicate in cpa:
        unode = nodes[source]
        vnode = nodes[target]

        if source not in nodemap:
            nodemap[source] = sm.add_node(unode)
        if target not in nodemap:
            nodemap[target] = sm.add_node(vnode)

    # detect and handle untype source column node
    remove_rel_from_nodes = set()

    for source, target, predicate in cpa:
        unode = nodes[source]
        if isinstance(unode, DataNode):
            if unode.col_index not in classmap:
                # discover untyped source column node
                if on_untype_source_column_node == "create-class":
                    # this data node has an outgoing edge, but it's untyped
                    # so we create an entity class to represent its type
                    cnode_id = sm.add_node(
                        ClassNode(
                            abs_uri=kgns.entity_uri,
                            rel_uri=kgns.get_rel_uri(kgns.entity_uri),
                            readable_label=kgns.entity_label,
                        )
                    )
                    classmap[unode.col_index] = cnode_id
                    sm.add_edge(
                        Edge(
                            source=cnode_id,
                            target=unode.id,
                            abs_uri=str(RDFS.label),
                            rel_uri=kgns.get_rel_uri(RDFS.label),
                        )
                    )
                else:
                    assert on_untype_source_column_node == "remove-link"
                    vnode = nodes[target]

                    if (
                        isinstance(vnode, ClassNode)
                        and vnode.abs_uri == kgns.statement_uri
                    ):
                        # this is a statement node, so we need to remove link
                        # from the statement node too because statement node
                        # can't live without the source
                        remove_rel_from_nodes.add(target)
                    remove_rel_from_nodes.add(source)

    if len(remove_rel_from_nodes) > 0:
        assert on_untype_source_column_node == "remove-link"
        cpa = [
            (source, target, predicate)
            for source, target, predicate in cpa
            if source not in remove_rel_from_nodes
        ]

    for source, target, predicate in cpa:
        unode = nodes[source]
        vnode = nodes[target]

        # if source not in nodemap:
        #     nodemap[source] = sm.add_node(unode)
        # if target not in nodemap:
        #     nodemap[target] = sm.add_node(vnode)

        if isinstance(unode, DataNode):
            # outgoing edge is from a class node instead of a data node
            assert unode.col_index in classmap
            # if unode.col_index not in classmap:
            #     # this data node has an outgoing edge, but it's untyped
            #     # so we create an entity class to represent its type
            #     curl = kgns.get_entity_abs_uri(self.ENTITY_ID)
            #     cnode_id = sm.add_node(
            #         ClassNode(
            #             abs_uri=curl,
            #             rel_uri=kgns.get_entity_rel_uri(self.ENTITY_ID),
            #             readable_label=self.kgns.entity_label,
            #         )
            #     )
            #     classmap[unode.col_index] = cnode_id
            #     sm.add_edge(
            #         Edge(
            #             source=cnode_id,
            #             target=unode.id,
            #             abs_uri=str(RDFS.label),
            #             rel_uri=kgns.get_rel_uri(RDFS.label),
            #         )
            #     )
            suid = classmap[unode.col_index]
            source = sm.get_node(suid)
        else:
            source = unode

        if isinstance(vnode, DataNode):
            # if this is an entity column, the link should map to its class
            if vnode.col_index in classmap:
                target = sm.get_node(classmap[vnode.col_index])
            else:
                target = vnode
        else:
            target = vnode

        sm.add_edge(
            Edge(
                source=source.id,
                target=target.id,
                abs_uri=(tmp_abs_uri := kgns.id_to_uri(predicate)),
                rel_uri=kgns.get_rel_uri(tmp_abs_uri),
                readable_label=get_prop_label(predicate),
            )
        )

    return sm
