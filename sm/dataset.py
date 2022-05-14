from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile
from typing import List, TypeVar, Generic, Union, Callable
import orjson

from sm.misc import deserialize_json, get_latest_path
from sm.outputs import SemanticModel

T = TypeVar("T")


@dataclass
class Example(Generic[T]):
    sms: List[SemanticModel]
    table: T


def load(
    data_dir: Union[str, Path], table_deser: Callable[[dict], T]
) -> List[Example[T]]:
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
    ├── <table_fs_id>.json
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
        table_deser: deserialize the table from dictionary

    Returns:

    """
    data_dir = Path(data_dir)
    examples = []
    for infile in sorted((data_dir / "tables").iterdir()):
        if infile.name.startswith("."):
            continue
        if infile.name.endswith(".json"):
            example_id = infile.stem

            table = table_deser(deserialize_json(infile))

            if (data_dir / f"descriptions/{example_id}").exists():
                desc_file = get_latest_path(
                    data_dir / f"descriptions/{example_id}/version.json"
                )
                assert desc_file is not None
            else:
                desc_file = data_dir / f"descriptions/{example_id}.json"
                assert desc_file.exists()

            raw_sms = deserialize_json(desc_file)
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
                        table = table_deser(orjson.loads(f.read()))
                    part[table_id] = table

            lst = []
            with ZipFile(data_dir / "descriptions" / infile.name, mode="r") as zf:
                for file in zf.infolist():
                    table_id = Path(file.filename).stem
                    if table_id not in part:
                        continue

                    assert file.filename.endswith(".json")
                    with zf.open(file, mode="r") as f:
                        sms = [
                            SemanticModel.from_dict(sm) for sm in orjson.loads(f.read())
                        ]
                        lst.append(Example(sms=sms, table=part[table_id]))

            assert len(lst) == len(part)
            examples.extend(lst)

    return examples
