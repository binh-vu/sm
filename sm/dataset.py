from __future__ import annotations

import random
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import md5
from operator import attrgetter
from pathlib import Path
from typing import (
    Generator,
    Generic,
    Literal,
    Optional,
    Protocol,
    Sequence,
    TypeVar,
    Union,
)
from urllib.parse import urlparse
from zipfile import Path as ZipPath
from zipfile import ZipFile

import orjson
from serde import json
from slugify import slugify
from typing_extensions import Self

from sm.inputs.prelude import ColumnBasedTable, Context, Link
from sm.misc.funcs import batch
from sm.misc.matrix import Matrix
from sm.outputs.semantic_model import SemanticModel

T = TypeVar("T", covariant=True)


@dataclass
class Example(Generic[T]):
    id: str
    sms: list[SemanticModel]
    table: T


@dataclass
class FullTable:
    table: ColumnBasedTable
    context: Context
    links: Matrix[list[Link]]

    def nrows(self) -> int:
        return self.table.nrows()

    def select_rows(self, indices: list[int]) -> FullTable:
        """Select a subset of rows based on a boolean mask"""
        return FullTable(
            table=self.table.select_rows(indices),
            context=self.context,
            links=Matrix([self.links.data[i] for i in indices]),
        )

    def remove_empty_links(self) -> Self:
        return self.__class__(
            table=self.table,
            context=self.context,
            links=self.links.map(
                lambda links: [link for link in links if link.end > link.start]
            ),
        )

    def to_dict(self):
        return {
            "version": 2,
            "table": self.table.to_dict(),
            "context": self.context.to_dict(),
            "links": [
                [[link.to_dict() for link in cell] for cell in row]
                for row in self.links.data
            ],
        }

    @classmethod
    def from_dict(cls, obj: dict):
        version = obj["version"]
        if not (version == "1.2" or version == "1.1" or version == 2):
            raise ValueError(f"Unknown version: {version}")

        table = ColumnBasedTable.from_dict(obj["table"])
        if "links" in obj:
            links = Matrix(
                [
                    [[Link.from_dict(link) for link in cell] for cell in row]
                    for row in obj["links"]
                ]
            )
        else:
            links = Matrix.default(table.shape(), list)

        return cls(
            table=table,
            context=Context.from_dict(obj["context"]),
            links=links,
        )


@dataclass
class Dataset:
    location: Path

    @contextmanager
    def _open(self) -> Generator[Union[ZipPath, Path], None, None]:
        if self.is_zip_file():
            # it is a zip file
            with ZipFile(self.location, mode="r") as zf:
                root = ZipPath(zf)
                if self.description_dir(root).exists():
                    yield root

                subdirs = list(root.iterdir())
                if len(subdirs) == 1 and self.description_dir(subdirs[0]).exists():
                    yield subdirs[0]
                else:
                    raise ValueError("Invalid dataset format")
        else:
            yield self.location

    def description_dir(self, root: Union[Path, ZipPath]) -> Union[Path, ZipPath]:
        return root / "descriptions"

    def table_dir(self, root: Union[Path, ZipPath]) -> Union[Path, ZipPath]:
        return root / "tables"

    def is_zip_file(self):
        return self.location.name.endswith(".zip")

    def load(self) -> list[Example[FullTable]]:
        """Load dataset from a folder. Assuming the following structure:

        descriptions (containing semantic descriptions of tables)
        ├── <table_fs_id>
        │   ├── version.01.json
        │   ├── version.02.json
        │   └── ...
            or
        ├── <table_fs_id>.json
        ├── ...
        tables (containing list of tables, the type of table depends on )
        ├── <table_fs_id>.json[.gz|.bz2|.lz4]
        ├── ...

        We also support compressing formats such as .zip.
        descriptions
        ├── part-<num>.zip (no nested version folders)
        │   ├── <table_fs_id>.json
        |   |   ...
        tables
        ├── part-<num>.zip
        │   ├── <table_fs_id>.json
        |   |   ...

        Args:
            data_dir:

        Returns:
        """
        examples = []
        with self._open() as root:
            descdir = self.description_dir(root)
            tabledir = self.table_dir(root)

            for infile in sorted(tabledir.iterdir(), key=attrgetter("name")):
                suffixes = Path(infile.name).suffixes
                if infile.name.startswith(".") or len(suffixes) == 0:
                    continue

                if suffixes[0] == ".json":
                    example_id = infile.name[: -sum(len(x) for x in suffixes)]
                    table = FullTable.from_dict(orjson.loads(infile.read_bytes()))

                    if descdir.exists():
                        if (descdir / example_id).exists():
                            desc_file = max(
                                (descdir / example_id).iterdir(),
                                key=lambda file: int(file.name.split(".")[1]),
                            )
                            assert desc_file is not None
                        else:
                            desc_file = descdir / f"{example_id}.json"
                            assert desc_file.exists()

                        raw_sms = orjson.loads(desc_file.read_bytes())
                        sms = [SemanticModel.from_dict(sm) for sm in raw_sms]
                    else:
                        sms = []

                    examples.append(
                        Example(id=table.table.table_id, sms=sms, table=table)
                    )
                elif infile.name.endswith(".zip"):
                    assert (
                        isinstance(infile, Path)
                        and isinstance(descdir, Path)
                        and not self.is_zip_file()
                    ), "Must not be a zip file"
                    part: dict[str, FullTable] = {}
                    with ZipFile(infile, mode="r") as zf:
                        for file in zf.infolist():
                            if not file.filename.endswith(".json"):
                                continue

                            table_id = Path(file.filename).stem
                            with zf.open(file, mode="r") as f:
                                table = FullTable.from_dict(orjson.loads(f.read()))
                            part[table_id] = table

                    if descdir.exists():
                        lst = []
                        with ZipFile(descdir / infile.name, mode="r") as zf:
                            for file in zf.infolist():
                                table_id = Path(file.filename).stem
                                if table_id not in part:
                                    continue

                                assert file.filename.endswith(".json")
                                with zf.open(file, mode="r") as f:
                                    sms = [
                                        SemanticModel.from_dict(sm)
                                        for sm in orjson.loads(f.read())
                                    ]
                                    lst.append(
                                        Example(
                                            id=table_id, sms=sms, table=part[table_id]
                                        )
                                    )
                    else:
                        lst = [
                            Example(id=table.table.table_id, sms=[], table=table)
                            for table in part.values()
                        ]
                    assert len(lst) == len(part)
                    examples.extend(lst)

            return examples

    def save(
        self,
        examples: list[Example[FullTable]],
        individual_table_compressed: Optional[Literal["gz", "bz2", "lz4"]] = None,
        batch_compressed: bool = False,
        batch_size: int = 100,
        table_fmt_indent: Literal[0, 2] = 0,
        clean_previous_data: bool = True,
    ):
        descdir = self.description_dir(self.location)
        tabledir = self.table_dir(self.location)
        assert (
            not self.is_zip_file()
            and isinstance(descdir, Path)
            and isinstance(tabledir, Path)
        )

        if descdir.exists() and clean_previous_data:
            shutil.rmtree(descdir)
        descdir.mkdir(parents=True, exist_ok=True)

        if tabledir.exists() and clean_previous_data:
            shutil.rmtree(tabledir)
        tabledir.mkdir(parents=True, exist_ok=True)

        if batch_compressed:
            for i, bexamples in enumerate(batch(batch_size, examples)):
                bexamples: list[Example[FullTable]]
                filename = f"part-{i:04d}.zip"
                with ZipFile(descdir / filename, "w") as dzf, ZipFile(
                    tabledir / filename, "w"
                ) as tzf:
                    for e in bexamples:
                        ename = get_friendly_fs_id(e.table.table.table_id) + ".json"
                        dzf.writestr(
                            ename,
                            data=orjson.dumps([sm.to_dict() for sm in e.sms]),
                        )
                        tzf.writestr(
                            ename,
                            data=orjson.dumps(e.table.to_dict()),
                        )
        else:
            for e in examples:
                filename = get_friendly_fs_id(e.table.table.table_id)
                (descdir / filename).mkdir(exist_ok=True)
                compressed_filename = (
                    filename + f".json.{individual_table_compressed}"
                    if individual_table_compressed is not None
                    else filename + ".json"
                )
                json.ser(
                    [sm.to_dict() for sm in e.sms],
                    descdir / filename / "version.01.json",
                    indent=2,
                )
                json.ser(
                    e.table, tabledir / compressed_filename, indent=table_fmt_indent
                )


def get_friendly_fs_id(id: str) -> str:
    if id.startswith("http://") or id.startswith("https://"):
        if id.find("dbpedia.org") != -1:
            return (
                slugify(
                    urlparse(id).path.replace("/resource/", "").replace("/", "_")
                ).replace("-", "_")
                + "_"
                + md5(id.encode()).hexdigest()
            )

        if id.find("wikipedia.org") != -1:
            return (
                slugify(
                    urlparse(id).path.replace("/wiki/", "").replace("/", "_")
                ).replace("-", "_")
                + "_"
                + md5(id.encode()).hexdigest()
            )

        raise NotImplementedError()
    return slugify(id.replace("/", "_"), lowercase=False).replace("-", "_")


class SampleableTable(Protocol):
    def nrows(self) -> int:
        ...

    def select_rows(self, indices: list[int]) -> Self:
        ...


ST = TypeVar("ST", bound=SampleableTable, covariant=True)


def sample_table_data(
    examples: Sequence[Example[ST]], n_rows: int, seed: Optional[int] = None
) -> Sequence[Example[ST]]:
    """Sample data from each table in examples.

    Args:
        examples: list of examples
        n_rows: number of rows to sample per table
        seed: random seed
    """
    rng = random.Random(seed)
    new_exs = []
    for ex in examples:
        tbl_nrows = ex.table.nrows()
        if tbl_nrows <= n_rows:
            new_exs.append(ex)
        else:
            indices = rng.sample(range(tbl_nrows), n_rows)
            new_exs.append(
                Example(id=ex.id, sms=ex.sms, table=ex.table.select_rows(indices))
            )

    return new_exs
