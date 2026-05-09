# Cloudmesh AI HPC

Cloudmesh AI HPC is a tool designed to simplify access and management of resources on High Performance Computing (HPC) clusters, including those at the University of Virginia (UVA) such as Rivanna. It provides a streamlined CLI to handle Slurm jobs, Apptainer images, storage checks, and remote file editing.

## Features

- **Interactive Login**: Simplified interactive job submission using `ijob`, including an interactive UI for partition selection.
- **Slurm Management**: Full lifecycle management of Slurm jobs, including status monitoring, listing active jobs, and cancellation.
- **Local Configuration**: Persist your preferred host and partition defaults locally.
- **Image Building**: Build Apptainer images directly on the cluster.
- **Storage Monitoring**: Quickly check directory sizes on the remote host.
- **Remote Editing**: Edit files on the cluster using your preferred editor.
- **VPN Management**: Integrated VPN control for secure cluster access.
- **Quick Links**: Access to UVA tutorials and support tickets.
- **Jupyter Integration**: Quick setup for Jupyter notebooks.

## Installation

To install this package, you can use `pip` from the root of the project:

```bash
pip install .
```

## Usage

All commands are accessed via the `cmc hpc` group.

### General Information
```bash
# Show current configuration and available partitions
cmc hpc info
cmc hpc info <host>

# Show hardware and queue configuration
cmc hpc config
```

### Login and Interactive Sessions
Log into an interactive node. You can specify a host and a configuration key (e.g., `v100`, `a100`).

```bash
# Basic login
cmc hpc login <key>

# Interactive UI to browse and select from all available partition keys
cmc hpc login --ui

# Login with specific host and sbatch parameters
cmc hpc login <key> --host <host> --sbatch "nodes:1,time:01:00:00"
```

### Slurm Commands
Manage Slurm directives and jobs.

**View Directives:**
```bash
cmc hpc slurm info <key> [--host <host>]
```

**Run a Job (Interactive):**
```bash
cmc hpc slurm run <key> [--sbatch "param:value,param2:value2"] [--host <host>]
```

**Monitor Jobs:**
```bash
# Get status of a specific job
cmc hpc slurm status <job_id>

# List all active jobs for the current user
cmc hpc slurm list
```

**Cancel a Job:**
```bash
cmc hpc slurm cancel <job_id>
```

### Configuration & Defaults
You can set your preferred default host and partition so you don't have to specify them in every command.

```bash
# Set default host and partition
cmc hpc set-default --host uva --partition a100
```

These settings are stored in `~/.cloudmesh/hpc.yaml`. You can also manually edit this file to add custom partitions.

### Image Management
Build Apptainer images from a definition file.

```bash
cmc hpc image build <definition_file>
```

### Storage
Check storage usage for a specific directory.

```bash
cmc hpc storage info <directory>
```

### VPN Management
Manage your VPN connection to UVA.

```bash
# Connect to VPN
cmc hpc vpn on

# Disconnect from VPN
cmc hpc vpn off

# Show current IP and connection info
cmc hpc vpn info

# Check if VPN is enabled
cmc hpc vpn status
```

### Remote Editing
Edit a file on the remote host using a specified editor (defaults to `emacs`).

```bash
cmc hpc edit <filename> [--editor <editor_name>]
```

### Jupyter Notebooks
Start a Jupyter notebook on the cluster.

```bash
cmc hpc jupyter [--port <port>]
```

### Tutorials and Support
Quickly open helpful links in your browser.

```bash
# Open tutorials (optional keyword: pod, rclone, globus, apptainer, training, hpc, system)
cmc hpc tutorial [keyword]

# Open the support request form
cmc hpc ticket
```

## Configuration Details

The tool uses a built-in directive map to handle Slurm configurations for various hosts. These directives include:
- `partition`
- `account`
- `gres` (GPU requests)
- `constraint`

**Sbatch Parameters**: You can override any directive using the `--sbatch` option. The format must be `key:value`, with multiple parameters separated by commas (e.g., `nodes:2,time:02:00:00`).

## Debugging

Most commands support a `--debug` flag. When enabled, the tool will print the exact SSH commands it intends to execute without actually running them.

Example:
```bash
cmc hpc slurm cancel 12345 --debug
```

## Core Dependencies
This project depends on the following core components of the Cloudmesh AI ecosystem:
- [cloudmesh-ai-common](https://github.com/cloudmesh-ai/cloudmesh-ai-common)
- [cloudmesh-ai-cmc](https://github.com/cloudmesh-ai/cloudmesh-ai-cmc)
- [cloudmesh-ai-vpn](https://github.com/cloudmesh-ai/cloudmesh-ai-vpn)
