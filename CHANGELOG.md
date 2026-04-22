# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
### Added
- Interactive TUI for partition selection in `cmc uva login --ui` using `textual`.
- Support for `partitions.yaml` with global and host-specific default partitions.
- Enhanced banner in `cmc uva login --ui` that displays both the `cmc` command and the actual `ijob` SSH command.
- Confirmation prompt before starting the login process.
- "Default" column in the partition selection table with `*` marker for the default partition.
- Shortcut 'd' in the TUI to quickly select the default partition.
- Refactored partition table data generation into the `Uva` class for better maintainability.