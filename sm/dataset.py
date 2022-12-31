from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile
from typing import List, Literal, Optional, TypeVar, Generic, Union, Callable
import orjson

from sm.misc.funcs import batch, get_latest_path
from sm.misc.matrix import Matrix
from sm.outputs.semantic_model import SemanticModel
from sm.inputs.prelude import ColumnBasedTable, Context, Link
from slugify import slugify
from serde import json
import shutil
from urllib.parse import urlparse
from hashlib import md5

T = TypeVar("T", covariant=True)


@dataclass
class Example(Generic[T]):
    sms: List[SemanticModel]
    table: T


@dataclass
class FullTable:
    table: ColumnBasedTable
    context: Context
    links: Matrix[List[Link]]

    def keep_rows(self, row_index: List[int]):
        """Keep only the rows in the table that are in row_index."""
        self.links.data = [self.links.data[i] for i in row_index]
        self.table._df = None
        for col in self.table.columns:
            col.values = [col.values[i] for i in row_index]

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

        return cls(
            table=ColumnBasedTable.from_dict(obj["table"]),
            context=Context.from_dict(obj["context"]),
            links=Matrix(
                [
                    [[Link.from_dict(link) for link in cell] for cell in row]
                    for row in obj["links"]
                ]
            ),
        )


@dataclass
class Dataset:
    location: Path

    @property
    def description_dir(self) -> Path:
        return self.location / "descriptions"

    @property
    def table_dir(self) -> Path:
        return self.location / "tables"

    def load(self) -> List[Example[FullTable]]:
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
        descdir = self.description_dir
        tabledir = self.table_dir

        examples = []
        for infile in sorted(tabledir.iterdir()):
            suffixes = infile.suffixes
            if infile.name.startswith(".") or len(suffixes) == 0:
                continue

            if suffixes[0] == ".json":
                example_id = infile.name[: -sum(len(x) for x in suffixes)]
                table = json.deser(infile, FullTable)

                if (descdir / example_id).exists():
                    desc_file = get_latest_path(descdir / f"{example_id}/version.json")
                    assert desc_file is not None
                else:
                    desc_file = descdir / f"{example_id}.json"
                    assert desc_file.exists()

                raw_sms = json.deser(desc_file)
                sms = [SemanticModel.from_dict(sm) for sm in raw_sms]

                examples.append(Example(sms=sms, table=table))
            elif infile.name.endswith(".zip"):

                part = {}
                with ZipFile(infile, mode="r") as zf:
                    for file in zf.infolist():
                        if not file.filename.endswith(".json"):
                            continue

                        table_id = Path(file.filename).stem
                        with zf.open(file, mode="r") as f:
                            table = FullTable.from_dict(orjson.loads(f.read()))
                        part[table_id] = table

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
                            lst.append(Example(sms=sms, table=part[table_id]))

                assert len(lst) == len(part)
                examples.extend(lst)

        return examples

    def save(
        self,
        examples: List[Example[FullTable]],
        individual_table_compressed: Optional[Literal["gz", "bz2", "lz4"]] = None,
        batch_compressed: bool = False,
        batch_size: int = 100,
        table_fmt_indent: Literal[0, 2] = 0,
        clean_previous_data: bool = True,
    ):
        descdir = self.description_dir
        if descdir.exists() and clean_previous_data:
            shutil.rmtree(descdir)
        descdir.mkdir(parents=True, exist_ok=True)

        tabledir = self.table_dir
        if tabledir.exists() and clean_previous_data:
            shutil.rmtree(tabledir)
        tabledir.mkdir(parents=True, exist_ok=True)

        if batch_compressed:
            for i, bexamples in enumerate(batch(batch_size, examples)):
                bexamples: List[Example[FullTable]]
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
