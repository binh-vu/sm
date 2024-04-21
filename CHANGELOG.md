# Changelog

## [Unreleased]

### Added

- Add `__str__` to `EntityIdWithScore` class
- Add `assert_not_empty` function to check if a list is not empty
- Add `SemanticModel.is_entity_column` and `SemanticModel.iter_data_nodes` functions

### Fixed

- Add missing prefixes to DBpediaNamespace and main URIs
- Fix division by zero error in `percentage`
- Fix `FullTable.keep_columns` function to make links consistent

## [6.10.1] - 2024-03-12

### Added

- Add `before_shutdown` function to ray map & ray actor map to copy the data stored in shared memory before shutting down the ray cluster to avoid data corruption.

## [6.10.0] - 2024-03-06

### Added

- Add DBpedia namespace

## [6.9.0] - 2024-03-03

### Added

- Add function to remove empty rows from a table
- Add new format (txt -- combination of csv & json) to save table data to easier to edit & view table
