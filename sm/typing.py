from __future__ import annotations

from typing import Annotated

IRI = Annotated[str, "IRI (e.g., https://www.wikidata.org/wiki/Q5)"]
InternalID = Annotated[str, "Internal ID (e.g., Q5)"]
ExampleId = Annotated[str, "Id of an example (e.g., table id)"]
ColumnIndex = Annotated[int, "Index of a column in the table"]
