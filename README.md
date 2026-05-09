# Cloudmesh AI HPC

Cloudmesh AI HPC is a tool designed to simplify access and management of resources on High Performance Computing (HPC) clusters, including those at the University of Virginia (UVA) such as Rivanna. It provides a streamlined CLI to handle Slurm jobs, Apptainer images, storage checks, and remote file editing.

## Features

- **Interactive Login**: Simplified interactive job submission using `ijob`, including an interactive UI for partition selection.
- **Slurm Management**: Easy access to Slurm directives and job cancellation.
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

All commands are accessed via the `cmc uva` group.

### General Information
```bash
cmc uva info
cmc uva config
```

### Login and Interactive Sessions
Log into an interactive node. You can specify a host and a configuration key (e.g., `v100`, `a100`).

```bash
# Basic login
cmc uva login <key>

# Interactive UI to browse and select from all available partition keys
cmc uva login --ui

# Login with specific host and sbatch parameters
cmc uva login <key> --host <host> --sbatch "nodes:1,time:01:00:00"
```

### Slurm Commands
Manage Slurm directives and jobs.

**View Directives:**
```bash
cmc uva slurm info <key> [--host <host>]
```

**Run a Job (Interactive):**
```bash
cmc uva slurm run <key> [--sbatch "param:value,param2:value2"] [--host <host>]
```

**Cancel a Job:**
```bash
cmc uva slurm cancel <job_id>
```

### Image Management
Build Apptainer images from a definition file.

```bash
cmc uva image build <definition_file>
```

### Storage
Check storage usage for a specific directory.

```bash
cmc uva storage info <directory>
```

### VPN Management
Manage your VPN connection to UVA.

```bash
# Connect to VPN
cmc uva vpn on

# Disconnect from VPN
cmc uva vpn off

# Show current IP and connection info
cmc uva vpn info

# Check if VPN is enabled
cmc uva vpn status
```

### Remote Editing
Edit a file on the remote host using a specified editor (defaults to `emacs`).

```bash
cmc uva edit <filename> [--editor <editor_name>]
```

### Jupyter Notebooks
Start a Jupyter notebook on the cluster.

```bash
cmc uva jupyter [--port <port>]
```

### Tutorials and Support
Quickly open helpful links in your browser.

```bash
# Open tutorials (optional keyword: pod, rclone, globus, apptainer, training, hpc, system)
cmc uva tutorial [keyword]

# Open the support request form
cmc uva ticket
```

## Configuration

The tool uses a built-in directive map to handle Slurm configurations for various hosts (e.g., `rivanna`, `hipergator`). These directives include:
- `partition`
- `account`
- `gres` (GPU requests)
- `constraint`

You can override these using the `--sbatch` option in the format `key:value,key2:value2`.

## Debugging

Most commands support a `--debug` flag. When enabled, the tool will print the exact SSH commands it intends to execute without actually running them.

Example:
```bash
cmc uva slurm cancel 12345 --debug
## Core Dependencies
This project depends on the following core components of the Cloudmesh AI ecosystem:
- [cloudmesh-ai-common](https://github.com/cloudmesh-ai/cloudmesh-ai-common)
- [cloudmesh-ai-cmc](https://github.com/cloudmesh-ai/cloudmesh-ai-cmc)
