import enum
import tempfile
from copy import copy
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, List, Literal, Optional, Set, Tuple, Union, cast

import matplotlib.pyplot as plt
import orjson
import pydot
from colorama import Back, Fore, Style, init
from graph.retworkx import BaseEdge, BaseNode, RetworkXDiGraph
from IPython import get_ipython
from IPython.display import display
from PIL import Image
from rdflib.namespace import RDFS
from sm.misc.bijection import Bijection
from sm.misc.funcs import auto_wrap, group_by
from sm.namespaces.namespace import Namespace


@dataclass
class SemanticType:
    class_abs_uri: str
    predicate_abs_uri: str
    class_rel_uri: str
    predicate_rel_uri: str
    qualifier_abs_uri: Optional[str] = None
    qualifier_rel_uri: Optional[str] = None

    @property
    def label(self):
        if self.qualifier_abs_uri is None:
            return (self.class_rel_uri, self.predicate_rel_uri)
        else:
            return (
                self.class_rel_uri,
                self.predicate_rel_uri,
                self.qualifier_rel_uri,
            )

    def is_entity_type(self) -> bool:
        """Telling if this semantic type is for entity column"""
        return self.predicate_abs_uri in {
            "http://www.w3.org/2000/01/rdf-schema#label",
            "http://schema.org/name",
        }

    def __hash__(self):
        return hash(
            (self.class_abs_uri, self.predicate_abs_uri, self.qualifier_abs_uri)
        )

    def __eq__(self, other):
        if not isinstance(other, SemanticType):
            return False

        return (
            self.class_abs_uri == other.class_abs_uri
            and self.predicate_abs_uri == other.predicate_abs_uri
            and self.qualifier_abs_uri == other.qualifier_abs_uri
        )

    def __str__(self):
        if self.qualifier_abs_uri is None:
            return f"{self.class_rel_uri}--{self.predicate_rel_uri}"
        else:
            return f"{self.class_rel_uri}--{self.predicate_rel_uri}--{self.qualifier_rel_uri}"

    def __repr__(self):
        return f"SType({self})"

    def to_dict(self):
        return {
            "class_abs_uri": self.class_abs_uri,
            "predicate_abs_uri": self.predicate_abs_uri,
            "class_rel_uri": self.class_rel_uri,
            "predicate_rel_uri": self.predicate_rel_uri,
            "qualifier_abs_uri": self.qualifier_abs_uri,
            "qualifier_rel_uri": self.qualifier_rel_uri,
        }

    @classmethod
    def from_dict(cls, obj: dict):
        return cls(**obj)


@dataclass(eq=True)
class ClassNode(BaseNode[int]):
    abs_uri: str
    rel_uri: str
    approximation: bool = False
    readable_label: Optional[str] = None
    id: int = -1  # id is set automatically after adding to graph

    @property
    def label(self):
        return self.readable_label or self.rel_uri

    def _is_value_equal(self, other: "ClassNode") -> bool:
        """Compare if the "value" of this node and the other node is equal.
        Meaning we do not care about the id as it can be changed
        by the insertion other.

        This function is here for SemanticModel.is_equal to use
        """
        return (
            self.abs_uri == other.abs_uri and self.approximation == other.approximation
        )


@dataclass(eq=True)
class DataNode(BaseNode[int]):
    col_index: int
    label: str
    id: int = -1  # id is set automatically after adding to graph

    def _is_value_equal(self, other: "DataNode") -> bool:
        """Compare if the "value" of this node and the other node is equal.
        Meaning we do not care about the id as it can be changed
        by the insertion other.

        This function is here for SemanticModel.is_equal to use
        """
        return self.col_index == other.col_index and self.label == other.label


class LiteralNodeDataType(str, enum.Enum):
    String = "string"
    # although the string is entity-id, the expected value is the entity's full URI
    Entity = "entity-id"


@dataclass(eq=True)
class LiteralNode(BaseNode[int]):
    value: str
    # readable label of the literal node, should not confuse it with value
    readable_label: Optional[str] = None
    # whether the literal node is in the surround context of the dataset
    is_in_context: bool = False
    datatype: LiteralNodeDataType = LiteralNodeDataType.String
    id: int = -1  # id is set automatically after adding to graph

    @property
    def label(self):
        return self.readable_label or self.value

    def _is_value_equal(self, other: "LiteralNode") -> bool:
        """Compare if the "value" of this node and the other node is equal.
        Meaning we do not care about the id as it can be changed
        by the insertion other.

        This function is here for SemanticModel.is_equal to use
        """
        return (
            self.value == other.value
            and self.is_in_context == other.is_in_context
            and self.datatype == other.datatype
        )


Node = Union[ClassNode, DataNode, LiteralNode]


@dataclass(eq=True)
class Edge(BaseEdge[int, str]):
    source: int
    target: int
    abs_uri: str
    rel_uri: str
    approximation: bool = False
    readable_label: Optional[str] = None
    id: int = -1  # id is set automatically after adding to graph

    @property
    def key(self):
        return self.abs_uri

    @property
    def label(self):
        return self.readable_label or self.rel_uri

    def _is_value_equal(self, other: "Edge") -> bool:
        """Compare if the "value" of this edge and the other edge is equal.
        Meaning we do not care about the source, target, and id of the edge as it can be changed
        by the insertion other.

        This function is here for SemanticModel.is_equal to use
        """
        return (
            self.abs_uri == other.abs_uri and self.approximation == other.approximation
        )


class SemanticModel(RetworkXDiGraph[str, Node, Edge]):
    def __init__(self, check_cycle=False, multigraph=True):
        super().__init__(check_cycle=check_cycle, multigraph=multigraph)
        self.column2id: List[int] = []
        self.value2id: Dict[str, int] = {}

    def get_data_node(self, column_index: int) -> DataNode:
        try:
            return self._graph.get_node_data(self.column2id[column_index])
        except IndexError as e:
            raise KeyError(f"Column index {column_index} is not in the model") from e
        except OverflowError as e:
            raise KeyError(f"Column index {column_index} is not in the model") from e

    def get_literal_node(self, value: str) -> LiteralNode:
        """Get literal node by value. Throw error when the value does not found"""
        return self._graph.get_node_data(self.value2id[value])

    def has_data_node(self, column_index: int) -> bool:
        return column_index < len(self.column2id) and self.column2id[column_index] != -1

    def has_literal_node(self, value: str) -> bool:
        return value in self.value2id

    def add_node(self, node: Node) -> int:
        node_id = super().add_node(node)
        if isinstance(node, DataNode):
            while len(self.column2id) - 1 < node.col_index:
                self.column2id.append(-1)
            assert self.column2id[node.col_index] == -1
            self.column2id[node.col_index] = node_id
        elif isinstance(node, LiteralNode):
            assert node.value not in self.value2id
            self.value2id[node.value] = node_id
        return node_id

    def remove_node(self, node_id: int):
        node = self._graph.get_node_data(node_id)
        if isinstance(node, DataNode):
            self.column2id[node.col_index] = -1
        elif isinstance(node, LiteralNode):
            del self.value2id[node.value]
        return super().remove_node(node_id)

    def get_semantic_types_of_column(
        self, col_index: int, statement_uri: Optional[str] = None
    ) -> List[SemanticType]:
        """Get semantic types (class & property) of a column.

        Args:
            col_index: column index
            statement_uri: a special class to indicate that the column is part of an n-ary relationship (e.g., Wikidata statement)
        """
        dnode = self.get_data_node(col_index)
        sem_types = set()
        for e in self.in_edges(dnode.id):
            u = self.get_node(e.source)
            assert isinstance(u, ClassNode)
            if u.abs_uri == statement_uri:
                # it's part of an n-ary relationship u -> prop -> statement -> qual -> v
                # if we have an n-ary relationship, a statement should only have one incoming edge
                (pe,) = self.in_edges(u.id)
                pu = self.get_node(pe.source)

                if not isinstance(pu, ClassNode):
                    # this can happen to n-ary relationship, (participate & rank)
                    assert (
                        isinstance(pu, LiteralNode)
                        and pu.datatype == LiteralNodeDataType.Entity
                    )
                    continue

                assert pu.abs_uri != statement_uri
                if pe.abs_uri == e.abs_uri:
                    # main statement property -- do not need to store qualifier
                    sem_types.add(
                        SemanticType(pu.abs_uri, pe.abs_uri, pu.rel_uri, pe.rel_uri)
                    )
                else:
                    # qualifier property
                    sem_types.add(
                        SemanticType(
                            pu.abs_uri,
                            pe.abs_uri,
                            pu.rel_uri,
                            pe.rel_uri,
                            e.abs_uri,
                            e.rel_uri,
                        )
                    )
            else:
                sem_types.add(SemanticType(u.abs_uri, e.abs_uri, u.rel_uri, e.rel_uri))
        return list(sem_types)

    def get_semantic_types(
        self, statement_uri: Optional[str] = None
    ) -> Set[SemanticType]:
        """Get semantic types (class & property) of all columns.

        Args:
            col_index: column index
            statement_uri: a special class to indicate that the column is part of an n-ary relationship (e.g., Wikidata statement)
        """
        sem_types = set()
        for ci, cid in enumerate(self.column2id):
            if cid == -1:
                continue
            sem_types.update(self.get_semantic_types_of_column(ci, statement_uri))
        return sem_types

    def is_equal(self, sm: "SemanticModel") -> bool:
        """Compare if two semantic model is equivalent"""
        if self.num_nodes() != sm.num_nodes() or self.num_edges() != sm.num_edges():
            return False

        # bijection between nodes in two models
        bijection: Bijection[int, int] = Bijection()

        nodes = self.nodes()
        other_nodes = sm.nodes()

        # compare data nodes
        data_nodes = [n for n in nodes if isinstance(n, DataNode)]
        other_data_nodes = {
            n.col_index: n for n in other_nodes if isinstance(n, DataNode)
        }
        if len(data_nodes) != len(other_data_nodes) or any(
            [
                u.col_index not in other_data_nodes
                or not u._is_value_equal(other_data_nodes[u.col_index])
                for u in data_nodes
            ]
        ):
            return False

        # compare literal nodes
        if len(self.value2id) != len(sm.value2id) or any(
            value not in sm.value2id
            or not cast(LiteralNode, self.get_node(id))._is_value_equal(
                cast(LiteralNode, sm.get_node(sm.value2id[value]))
            )
            for value, id in self.value2id.items()
        ):
            return False

        # update bijection with mapping between data and literal nodes
        for u in data_nodes:
            bijection.check_add(u.id, other_data_nodes[u.col_index].id)
        for value in self.value2id:
            bijection.check_add(self.value2id[value], sm.value2id[value])

        # from the data nodes and literal nodes, we check the edges and class nodes
        # until we find a mismatch, or we checked all nodes and edges
        checked_edges = set()
        while True:
            n_mapped = bijection.size()
            for uid, uprime_id in list(bijection.x2prime.items()):
                uri2edges = group_by(self.in_edges(uid), lambda e: e.abs_uri)
                other_uri2edges = group_by(sm.in_edges(uprime_id), lambda e: e.abs_uri)
                if set(uri2edges.keys()) != set(other_uri2edges.keys()):
                    return False

                for uri, edges in uri2edges.items():
                    if len(edges) != len(other_uri2edges[uri]):
                        return False
                    if len(edges) == 1:
                        if not edges[0]._is_value_equal(other_uri2edges[uri][0]):
                            return False

                        u = self.get_node(edges[0].source)
                        uprime = sm.get_node(other_uri2edges[uri][0].source)

                        if (
                            isinstance(u, ClassNode)
                            and isinstance(uprime, ClassNode)
                            and not u._is_value_equal(uprime)
                        ):
                            return False

                        if not bijection.add(
                            edges[0].source, other_uri2edges[uri][0].source
                        ):
                            return False

                        checked_edges.add(edges[0].id)

                    # TODO: handle case where #edges > 1, we can future split them
                    # by the mapped source

            if n_mapped == bijection.size():
                break

        # almost all nodes should mapped by now
        if bijection.size() != len(nodes):
            # exception to see when this happens
            raise NotImplementedError()

        # all edges and class nodes must been checked
        assert len(checked_edges) == self.num_edges()
        return True

    def copy(self):
        sm = super().copy()
        sm.column2id = copy(self.column2id)
        sm.value2id = copy(self.value2id)
        return sm

    def deep_copy(self):
        sm = self.copy()
        for n in sm.iter_nodes():
            sm.update_node(copy(n))
        for e in sm.iter_edges():
            sm.update_edge(copy(e))
        return sm

    def to_dict(self):
        return {
            "version": 1,
            "nodes": [asdict(u) for u in self.iter_nodes()],
            "edges": [asdict(e) for e in self.iter_edges()],
        }

    def to_json_file(self, outfile: Union[str, Path]):
        with open(outfile, "wb") as f:
            f.write(orjson.dumps(self.to_dict(), option=orjson.OPT_INDENT_2))

    @staticmethod
    def from_dict(record: dict):
        sm = SemanticModel()
        id2node = {}
        for u in record["nodes"]:
            if "col_index" in u:
                id2node[u["id"]] = sm.add_node(DataNode(**u))
            elif "abs_uri" in u:
                id2node[u["id"]] = sm.add_node(ClassNode(**u))
            else:
                lnode = LiteralNode(**u)
                lnode.datatype = LiteralNodeDataType(lnode.datatype)
                id2node[u["id"]] = sm.add_node(lnode)
        for e in record["edges"]:
            e["source"] = id2node[e["source"]]
            e["target"] = id2node[e["target"]]
            assert sm.has_node(e["source"]) and sm.has_node(e["target"])
            sm.add_edge(Edge(**e))
        return sm

    @staticmethod
    def from_json_file(infile: Union[str, Path]):
        with open(infile, "rb") as f:
            record = orjson.loads(f.read())
            return SemanticModel.from_dict(record)

    @staticmethod
    def from_yaml_dict(record: dict, ns: Namespace):
        """Parse the semantic model from specific yaml format."""
        sm = SemanticModel()
        id2node = {}
        for u in record["nodes"]:
            uid = u.pop("id")
            if "col_index" in u:
                id2node[uid] = sm.add_node(DataNode(**u))
            elif "uri" in u:
                id2node[uid] = sm.add_node(
                    ClassNode(
                        abs_uri=ns.get_abs_uri(u["uri"]),
                        rel_uri=u["uri"],
                        approximation=u.get("approximation", False),
                        readable_label=u.get("readable_label", None),
                    )
                )
            else:
                lnode = LiteralNode(
                    value=u["value"],
                    readable_label=u.get("readable_label", None),
                    is_in_context=u.get("is_in_context", False),
                    datatype=LiteralNodeDataType(u.get("datatype", "string")),
                )
                id2node[uid] = sm.add_node(lnode)
        for e in record["edges"]:
            source, predicate, target = e.split("---")
            assert sm.has_node(id2node[source]) and sm.has_node(id2node[target])
            sm.add_edge(
                Edge(
                    source=id2node[source],
                    target=id2node[target],
                    abs_uri=ns.get_abs_uri(predicate),
                    rel_uri=predicate,
                )
            )
        return sm

    def add_readable_label(
        self, fn: Callable[[Union[ClassNode, LiteralNode, Edge]], None]
    ):
        """Add readable label to all nodes and edges that don't have one yet.

        Note: this function will mutate the semantic model.
        """
        for node in self.iter_nodes():
            if (
                isinstance(node, (ClassNode, LiteralNode))
                and node.readable_label is None
            ):
                fn(node)
        for edge in self.iter_edges():
            if edge.readable_label is None:
                fn(edge)
        return self

    def draw(
        self,
        filename: Optional[str] = None,
        format: Literal["png", "jpg"] = "png",
        quality: int = 100,
        no_display: bool = False,
        max_char_per_line: int = 20,
    ):
        """
        Parameters
        ----------
        filename : str | none
            output to a file or display immediately (inline if this is jupyter lab)

        format: png | jpg
            image format

        quality: int
            if it's < 100, we will compress the image using PIL

        no_display: bool
            if the code is running inside Jupyter, if enable, it returns the object and manually display (default is
            automatically display)

        max_char_per_line: int
            wrap the text if it's too long

        Returns
        -------
        """
        if filename is None:
            fobj = tempfile.NamedTemporaryFile()
            filename = fobj.name
        else:
            fobj = None

        dot_g = pydot.Dot(graph_type="digraph")
        for u in self.iter_nodes():
            if isinstance(u, ClassNode):
                label = auto_wrap(u.label.replace(":", r"\:"), max_char_per_line)
                dot_g.add_node(
                    pydot.Node(
                        name=u.id,
                        label=label,
                        shape="ellipse",
                        style="filled",
                        color="white",
                        fillcolor="lightgray",
                    )
                )
            elif isinstance(u, DataNode):
                label = auto_wrap(
                    rf"C{u.col_index}\:" + u.label.replace(":", r"\:"),
                    max_char_per_line,
                )
                dot_g.add_node(
                    pydot.Node(
                        name=u.id,
                        label=label,
                        shape="plaintext",
                        style="filled",
                        fillcolor="gold",
                    )
                )
            else:
                if u.readable_label is not None:
                    label = u.readable_label
                else:
                    label = auto_wrap(u.value, max_char_per_line)
                dot_g.add_node(
                    pydot.Node(
                        name=u.id,
                        label=label,
                        shape="plaintext",
                        style="filled",
                        fillcolor="purple",
                    )
                )

        for e in self.iter_edges():
            label = auto_wrap(e.label.replace(":", r"\:"), max_char_per_line)
            dot_g.add_edge(
                pydot.Edge(
                    e.source, e.target, label=label, color="brown", fontcolor="black"
                )
            )

        # graphviz from anaconda does not support jpeg so use png instead
        dot_g.write(filename, prog="dot", format=format)
        if quality < 100:
            im = Image.open(filename)
            im.save(filename, optimize=True, quality=quality)

        if fobj is not None:
            img = Image.open(filename)
            try:
                if no_display:
                    return img
            finally:
                fobj.close()

            try:
                shell = get_ipython().__class__.__name__
                if shell == "ZMQInteractiveShell":
                    display(img)
                else:
                    plt.imshow(img, interpolation="antialiased")
                    plt.show()
            except NameError:
                plt.imshow(img, interpolation="antialiased")
                plt.show()
            finally:
                fobj.close()

    def draw_difference(
        self,
        gold_sm: "SemanticModel",
        filename=None,
        format="jpeg",
        no_display: bool = False,
        max_char_per_line: int = 20,
    ):
        """
        Colors:
        * green, red for edges/nodes in the pred_sm that does not appear in the gold_sm
        * lightgray for edges/nodes that are in the gold_sm but not in the pred_sm

        Parameters
        ----------
        gold_sm : SemanticModel
            the correct semantic model that we are going to compare to
        filename : str | none
            output to a file or display immediately (inline if this is jupyter lab)

        no_display : bool
            if the code is running inside Jupyter, if enable, it returns the object and manually display (default is
            automatically display)

        max_char_per_line: int
            wrap the text if it's too long

        Returns
        -------
        """
        from sm.evaluation.sm_metrics import precision_recall_f1

        if filename is None:
            fobj = tempfile.NamedTemporaryFile()
            filename = fobj.name
        else:
            fobj = None

        bijection = precision_recall_f1(gold_sm, self).bijection
        dot_g = pydot.Dot(graph_type="digraph")
        data_nodes = set()
        for u in self.iter_nodes():
            if isinstance(u, ClassNode):
                if bijection.prime2x[u.id] is None:
                    # this is a wrong node
                    fillcolor = "tomato"
                else:
                    fillcolor = "mediumseagreen"

                label = auto_wrap(u.label.replace(":", r"\:"), max_char_per_line)
                dot_g.add_node(
                    pydot.Node(
                        name=u.id,
                        label=label,
                        shape="ellipse",
                        style="filled",
                        color="white",
                        fillcolor=fillcolor,
                    )
                )
            elif isinstance(u, DataNode):
                data_nodes.add(u.col_index)
                dot_uid = f"C{u.col_index:02d}_{u.label}"
                label = auto_wrap(
                    f"C{u.col_index}: " + u.label.replace(":", r"\:"), max_char_per_line
                )
                dot_g.add_node(
                    pydot.Node(
                        name=dot_uid,
                        label=label,
                        shape="plaintext",
                        style="filled",
                        fillcolor="gold",
                    )
                )
            else:
                raise NotImplementedError()

        # node in gold_sm doesn't appear in the pred_sm
        for u in gold_sm.iter_nodes():
            if isinstance(u, ClassNode):
                if bijection.x2prime[u.id] is None:
                    # class node in gold model need to give a different namespace (`gold:`) to avoid collision
                    dot_uid = ("gold:" + str(u.id)).replace(":", "_")
                    dot_g.add_node(
                        pydot.Node(
                            name=dot_uid,
                            label=auto_wrap(
                                u.label.replace(":", r"\:"), max_char_per_line
                            ),
                            shape="ellipse",
                            style="filled",
                            color="white",
                            fillcolor="lightgray",
                        )
                    )
            elif isinstance(u, DataNode):
                if u.col_index not in data_nodes:
                    dot_uid = f"C{u.col_index:02d}_{u.label}"
                    dot_g.add_node(
                        pydot.Node(
                            name=dot_uid,
                            label=auto_wrap(
                                f"C{u.col_index}: " + u.label.replace(":", r"\:"),
                                max_char_per_line,
                            ),
                            shape="plaintext",
                            style="filled",
                            fillcolor="lightgray",
                        )
                    )
            else:
                raise NotImplementedError()

        # add edges in pred_sm
        x_triples = set()
        for e in gold_sm.iter_edges():
            v = gold_sm.get_node(e.target)
            if isinstance(v, ClassNode):
                target = v.id
            elif isinstance(v, DataNode):
                target = (v.col_index, v.label)
            else:
                target = v.value
            x_triples.add((e.source, e.label, target))

        x_prime_triples = set()
        for e in self.iter_edges():
            uid, vid = e.source, e.target
            v = self.get_node(vid)
            x_prime_triple = (
                bijection.prime2x[uid],
                e.label,
                bijection.prime2x[vid]
                if isinstance(v, ClassNode)
                else ((v.col_index, v.label) if isinstance(v, DataNode) else v.value),
            )
            x_prime_triples.add(x_prime_triple)
            if x_prime_triple in x_triples:
                color = "darkgreen"
            else:
                color = "red"

            dot_u = uid
            dot_v = (
                vid
                if isinstance(v, ClassNode)
                else (
                    f"C{v.col_index:02d}_{v.label}"
                    if isinstance(v, DataNode)
                    else v.value
                )
            )
            dot_g.add_edge(
                pydot.Edge(
                    dot_u,
                    dot_v,
                    label=auto_wrap(e.label.replace(":", r"\:"), max_char_per_line),
                    color=color,
                    fontcolor="black",
                )
            )

        # add edges in gold_sm that is not in pred_sm
        for x_triple in x_triples:
            if x_triple not in x_prime_triples:
                # class node in gold model need to give a different namespace (`gold:`) to avoid collision
                dot_u = (
                    "gold:" + x_triple[0]
                    if bijection.x2prime[x_triple[0]] is None
                    else str(bijection.x2prime[x_triple[0]])
                )
                dot_u = dot_u.replace(":", "_")

                if isinstance(x_triple[2], tuple):
                    dot_v = f"C{x_triple[2][0]:02d}_{x_triple[2][1]}"
                else:
                    dot_v = (
                        "gold:" + x_triple[2]
                        if bijection.x2prime[x_triple[2]] is None
                        else str(bijection.x2prime[x_triple[2]])
                    )
                    dot_v = dot_v.replace(":", "_")

                dot_g.add_edge(
                    pydot.Edge(
                        dot_u,
                        dot_v,
                        label=auto_wrap(
                            x_triple[1].replace(":", r"\:"), max_char_per_line
                        ),
                        color="gray",
                        fontcolor="black",
                    )
                )

        # graphviz from anaconda does not support jpeg so use png instead
        dot_g.write(filename, prog="dot", format="jpeg")

        if fobj is not None:
            img = Image.open(filename)
            try:
                if no_display:
                    return img
            finally:
                fobj.close()

            try:
                shell = get_ipython().__class__.__name__
                if shell == "ZMQInteractiveShell":
                    display(img)
                else:
                    plt.imshow(img, interpolation="antialiased")
                    plt.show()
            except NameError:
                plt.imshow(img, interpolation="antialiased")
                plt.show()
            finally:
                fobj.close()

    def print(
        self,
        colorful: bool = True,
        ignore_isolated_nodes: bool = False,
        env: Literal["terminal", "browser", "notebook"] = "terminal",
        _cache={},
    ) -> Optional[str]:
        """Print the semantic model to the environment if possible. When env is browser, users have to print it manually"""
        if colorful and "init_colorama" not in _cache:
            init()
            _cache["init_colorama"] = True

        def terminal_rnode(node: Node):
            if isinstance(node, ClassNode):
                return f"{Back.LIGHTGREEN_EX}{Fore.BLACK}[{node.id}] {node.label}{Style.RESET_ALL}"
            if isinstance(node, DataNode):
                return f"{Back.LIGHTYELLOW_EX}{Fore.BLACK}[{node.id}] {node.label} (column {node.col_index}){Style.RESET_ALL}".replace(
                    "\n", "\\n"
                )
            if isinstance(node, LiteralNode):
                return f"{Back.LIGHTCYAN_EX}{Fore.BLACK}[{node.id}] {node.readable_label}{Style.RESET_ALL}"

        def browser_rnode(node: Node):
            style = "padding: 2px; border-radius: 3px;"
            if isinstance(node, ClassNode):
                return f'<span style="background: #b7eb8f; color: black; {style}">[{node.id}] {node.label}</span>'
            if isinstance(node, DataNode):
                return f'<span style="background: #ffe58f; color: black; {style}">[{node.id}] {node.label} (column {node.col_index})</span>'
            if isinstance(node, LiteralNode):
                return f"<span style=\"background: {'#c6e5ff' if node.is_in_context else '#d3adf7'}; color: black; {style}\">[{node.id}] {node.readable_label}</span>"

        def terminal_redge(edge: Edge):
            return f"─[{edge.id}: {Back.LIGHTMAGENTA_EX}{Fore.BLACK}{edge.label}{Style.RESET_ALL}]→"

        def browser_redge(edge: Edge):
            return f'<span>─[{edge.id}: <span style="text-decoration: underline; background: #ffadd2; color: black">{edge.label}</span>]→</span>'

        if env == "terminal":
            rnode = terminal_rnode
            redge = terminal_redge
        else:
            rnode = browser_rnode
            redge = browser_redge

        visited = {}
        logs = []

        def dfs(start: Node):
            logs.append("\n")
            stack: List[Tuple[int, Optional[Edge], Node]] = [(0, None, start)]
            while len(stack) > 0:
                depth, edge, node = stack.pop()
                if edge is None:
                    msg = f"{rnode(node)}"
                else:
                    msg = f"{redge(edge)} {rnode(node)}"

                if depth > 0:
                    indent = "│   " * (depth - 1)
                    msg = f"{indent}├── {msg}"

                if node.id in visited:
                    msg += f" (visited at {visited[node.id]})"
                    logs.append(f"--.\t{msg}\n")
                    continue

                counter = len(visited)
                visited[node.id] = counter
                logs.append(f"{counter:02d}.\t{msg}\n")
                outedges = sorted(
                    self.out_edges(node.id),
                    key=lambda edge: f"0:{edge.abs_uri}"
                    if edge.abs_uri == str(RDFS.label)
                    else f"1:{edge.abs_uri}",
                    reverse=True,
                )
                for edge in outedges:
                    target = self.get_node(edge.target)
                    stack.append((depth + 1, edge, target))

        """Print the semantic model, assuming it is a tree"""
        nodes = self.nodes()
        if ignore_isolated_nodes:
            nodes = [n for n in nodes if self.degree(n.id) > 0]

        roots = [n for n in nodes if self.in_degree(n.id) == 0]
        for root in roots:
            dfs(root)

        # doing a final pass to make sure all nodes are printed (including cycles)
        while len(visited) < len(nodes):
            n = [n for n in nodes if n.id not in visited and self.out_degree(n.id) > 0][
                0
            ]
            dfs(n)

        if env == "terminal":
            print("".join(logs))
        else:
            html = "<pre>" + "".join(logs) + "</pre>"
            if env == "browser":
                return html
            else:
                assert env == "notebook"
                from IPython.display import display
                from ipywidgets import HTML

                display(HTML(html))
