# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
### Added
- `cmc hpc check` command for comprehensive environment health checks (VPN, SSH, Quota).
- `cmc hpc slurm monitor` interactive TUI for real-time job monitoring and management.
- `--cluster` flag for `cmc hpc slurm gpu-usage` to provide a cluster-wide GPU availability heat map.
- `--billing` flag for `cmc hpc slurm quota` to display core-hour usage and billing reports.
- Interactive TUI for partition selection in `cmc uva login --ui` using `textual`.
- Support for `partitions.yaml` with global and host-specific default partitions.
- Enhanced banner in `cmc uva login --ui` that displays both the `cmc` command and the actual `ijob` SSH command.
- Confirmation prompt before starting the login process.
- "Default" column in the partition selection table with `*` marker for the default partition.
- Shortcut 'd' in the TUI to quickly select the default partition.
- Refactored partition table data generation into the `Uva` class for better maintainability.

### Fixed
- Fixed an issue where `console.table` output caused "Can't open" errors in certain terminal environments by implementing a simplified text-based table for the GPU heat map.
