# Cloudmesh AI HPC

**Authors**:
*   **Gregor von Laszewski** ([laszewski@gmail.com](mailto:laszewski@gmail.com))a
*   **JP Fleischer**

Cloudmesh AI HPC is a tool designed to simplify access and management of resources on High Performance Computing (HPC) clusters, including those at the University of Virginia (UVA) such as Rivanna. It provides a streamlined CLI to handle Slurm jobs, Apptainer images, storage checks, and remote file editing.

## Installation

### macOS & Linux
**Recommended: Using pipx**
For the best experience with CLI tools, use `pipx` to install `cloudmesh-ai-hpc` in an isolated environment.
```bash
pipx install cloudmesh-ai-hpc
```
*To install from a local directory: `pipx install .`*

**Using pip**
```bash
pip install cloudmesh-ai-hpc
```
*To install from a local directory: `pip install .`*

### Windows
**Using pip**
```powershell
pip install cloudmesh-ai-hpc
```
*To install from a local directory: `pip install .`*

## Usage Examples

### General Information

**1. Show current configuration and available partitions**
```bash
cmc hpc info
```
> ```text
> HPC Configuration Info
> Current Host      : uva
> Default Partition : a100
> Available Hosts   : uva, rivanna
> 
> Partitions
> ┌──────────┬──────────┬──────────────┬──────────────────────────┐
> │ Default  │ Key      │ Partition    │ GRES / Constraint        │
> ├──────────┼──────────┼──────────────┼──────────────────────────┤
> │ *        │ a100     │ gpu          │ gpu:a100:1               │
> │          │ v100     │ bii-gpu      │ gpu:v100:1               │
> └──────────┴──────────┴──────────────┴──────────────────────────┘
> ```

**2. Show hardware and queue configuration**
```bash
cmc hpc config
```
> ```text
> HPC Hardware Configuration
> ┌──────────────────┬──────────────────────────────────────────┐
> │ Component        │ Specification                            │
> ├──────────────────┼──────────────────────────────────────────┤
> │ CPU              │ AMD EPYC 7742 64-Core                      │
> │ GPU              │ NVIDIA A100 80GB                          │
> └──────────────────┴──────────────────────────────────────────┘
> ```

### Remote Execution & Login

**3. Execute a one-off command on the HPC**
```bash
cmc hpc run "ls -la /home/user"
```
> ```text
> total 12
> drwxr-xr-x 2 user user 4096 May  9 09:00 .
> drwxr-xr-x 3 user user 4096 May  9 08:00 ..
> -rw-r--r-- 1 user user  123 May  9 09:00 test.txt
> ```

**4. SSH into an interactive node**
```bash
# Use the login command to establish an SSH session
cmc hpc login a100
```
> ```text
> ssh -tt uva "/opt/rci/bin/ijob --partition=gpu --account=bii_dsc_community --gres=gpu:a100:1"
> ✓ Login process started.
> ```

### Slurm Job Management

**5. Generate and submit a job**
```bash
# Generate a boilerplate .sbatch script
cmc hpc slurm template a100 > my_job.sh
```
> ```text
> #SBATCH --partition=gpu
> #SBATCH --account=bii_dsc_community
> #SBATCH --gres=gpu:a100:1
> #SBATCH --output=slurm-%j.out
> #SBATCH --error=slurm-%j.err
> 
> #!/bin/bash
> echo 'Hello from Slurm job on uva partition a100'
> hostname
> ```

```bash
# Upload and submit a script
cmc hpc slurm submit my_job.sh
```
> ```text
> Submitted: 123456
> ```

**6. Monitor and inspect jobs**
```bash
# Get detailed information about a specific job
cmc hpc slurm job-info 123456
```
> ```text
> JobId=123456 Partition=gpu Account=bii_dsc_community User=user State=RUNNING
> CPU_ تعداد=1 NodeList=gpu-node-01 ...
> ```

```bash
# Get status of a specific job
cmc hpc slurm status 123456
```
> ```text
> JOBID   PARTITION  NAME     USER    ST  TIME  NODES
> 123456  gpu        my_job   user    R   0:05  1
> ```

```bash
# List all active jobs for the current user
cmc hpc slurm list
```
> ```text
> JOBID   PARTITION  NAME     USER    ST  TIME  NODES
> 123456  gpu        my_job   user    R   0:05  1
> 123457  parallel   test_job user    PD  0:00  2
> ```

```bash
# Wait for a job to complete
cmc hpc slurm wait 123456
```
> ```text
> Waiting for job 123456 to complete...
> Job 123456 is PENDING...
> Job 123456 is currently RUNNING...
> Job 123456 has finished (Status: COMPLETED).
> ```

**7. Logs and Resources**
```bash
# Read the output log of a job
cmc hpc slurm logs 123456
```
> ```text
> Hello from Slurm job on uva partition a100
> gpu-node-01
> ```

```bash
# Check disk quota on the HPC
cmc hpc slurm quota
```
> ```text
> Disk quotas for user:
> Filesystem  blocks   quota   limit   grace
> /home       100M     500M    500M    -
> /scratch    10G      1T      1T      -
> ```

```bash
# Check node status for a partition
cmc hpc slurm nodes --partition gpu
```
> ```text
> PARTITION AVAIL  TIMELIMIT  NODES  STATE NODELIST
> gpu       up     infinite   10     mix   gpu-node-[01-10]
> ```

**8. Directives & Cancellation**
```bash
# View Slurm directives for a partition key
cmc hpc slurm info a100
```
> ```text
> Host       : uva
> Partition  : a100
> partition  : gpu
> account    : bii_dsc_community
> gres       : gpu:a100:1
> ```

```bash
# Cancel a Slurm job
cmc hpc slurm cancel 123456
```
> ```text
> Canceling job 123456...
> ✓ Job 123456 cancelled.
> ```

### Configuration & Defaults

**9. Set default host and partition**
```bash
cmc hpc set-default --host uva --partition a100
```
> ```text
> Default host set to uva and partition to a100
> ```

### Image & Storage Management

**10. Build Apptainer images**
```bash
cmc hpc image build my_image.def
```
> ```text
> Cloudmesh HPC Apptainer Build
> Image name       : my_image.sif
> Singularity cache: /scratch/user/.apptainer/
> Definition       : my_image.def
> 
> Building image...
> Time to build my_image.sif (2.4GB) 145s
> ```

**11. Check storage usage**
```bash
cmc hpc storage info /home/user/data
```
> ```text
> Storage Info
> ╭───────────┬──────╮
> │ Directory │ Size │
> ├───────────┼──────┤
> │ /home/user/data │ 1.2G │
> ╰───────────┴──────╯
> ```

### VPN & Remote Tools

**12. Manage VPN connection**
```bash
cmc hpc vpn on
```
> ```text
> ✓ Connected to uva
> ```

```bash
cmc hpc vpn status
```
> ```text
> True
> ```

**13. Remote Editing**
```bash
cmc hpc edit config.txt
```
> ```text
> Editing config.txt with emacs...
> ```

**14. Jupyter Notebooks**
```bash
cmc hpc jupyter --port 8888
```
> ```text
> Starting Jupyter on port 8888...
> Note: This requires an active VPN connection.
> Command: jupyter notebook --no-browser --port=8888
> Tunnel: ssh -L 8888:localhost:8888 hpc
> ```

**15. Tutorials and Support**
```bash
cmc hpc tutorial pod
```
> ```text
> Opening tutorial for pod: https://infomall.org/uva/docs/tutorial/pod
> ```

```bash
cmc hpc ticket
```
> ```text
> Opening support request form: https://www.rc.virginia.edu/form/support-request/
> ```

## Command Reference

| Command | Description | Options |
| :--- | :--- | :--- |
| `info` | Show current configuration and available partitions | `[host]` |
| `config` | Show hardware and queue configuration | |
| `shell` | Enter an interactive shell for executing CMC commands | |
| `ssh` | SSH into the HPC cluster (via login) | `<key>`, `--ui` |
| `run` | Execute a one-off command on the HPC | `"command"` |
| `login` | SSH into an interactive node | `<key>`, `--ui`, `--host`, `--sbatch` |
| `slurm template` | Generate a boilerplate .sbatch script | `<key>` |
| `slurm submit` | Upload and submit a Slurm job | `<file>`, `--key`, `--sbatch` |
| `slurm job-info` | Get detailed information about a job | `<id>` |
| `slurm status` | Get the current status of a job | `<id>` |
| `slurm list` | List all active jobs for the current user | |
| `slurm wait` | Block until a job completes with status updates | `<id>`, `--interval` |
| `slurm monitor` | Actively monitor a job's progress | `<id>` |
| `slurm logs` | Read or tail the output logs of a job | `<id>`, `--tail` |
| `slurm quota` | Check disk quota on the HPC | |
| `slurm nodes` | Check node status for a partition | `--partition` |
| `slurm info` | View Slurm directives for a partition key | `<key>`, `--host` |
| `slurm cancel` | Cancel a Slurm job | `<id>` |
| `set-default` | Set default host and partition | `--host`, `--partition` |
| `image build` | Build an Apptainer image from a definition file | `<file>` |
| `storage info` | Get cleaned-up storage size for a directory | `<dir>` |
| `edit` | Edit a remote file using a specified editor | `<file>`, `--editor` |
| `vpn on/off` | Connect or disconnect from the VPN | |
| `vpn info/status` | Show VPN connection details | |
| `jupyter` | Setup a Jupyter notebook on the cluster | `--port` |
| `tutorial` | Open HPC tutorials in the browser | `[keyword]` |
| `ticket` | Open the support request form | |

## Debugging

Most commands support a `--debug` flag. When enabled, the tool will print the exact SSH commands it intends to execute without actually running them.

Example:
```bash
cmc hpc slurm cancel 12345 --debug
```

---

## Appendix: UVA Partition Table

The following table lists the partition keys used by `cloudmesh-ai-hpc` for the UVA host and their corresponding Slurm directives.

| Key | Partition | Account | GRES / Constraint / Reservation |
| :--- | :--- | :--- | :--- |
| `parallel` | parallel | bii_dsc_community | nodes: 2, ntask-per-node: 4 |
| `v100` | bii-gpu | bii_dsc_community | gpu:v100:1 |
| `a100` | gpu | bii_dsc_community | gpu:a100:1 |
| `a100-80gb` | gpu | bii_dsc_community | gpu:a100:1, constraint: a100_80gb |
| `a100-dgx` | bii-gpu | bii_dsc_community | gpu:a100:1, reservation: bi_fox_dgx |
| `k80` | gpu | bii_dsc_community | gpu:k80:1 |
| `p100` | gpu | bii_dsc_community | gpu:p100:1 |
| `a6000` | gpu | bii_dsc_community | gpu:a6000:1 |
| `a100-pod` | gpu | bii_dsc_community | gpu:a100:1, constraint: gpupod |
| `rtx2080` | gpu | bii_dsc_community | gpu:rtx2080:1 |
| `rtx3090` | gpu | bii_dsc_community | gpu:rtx3090:1 |

### The CMC Shell Abstraction

The `cmc hpc` tool utilizes an internal shell abstraction to execute commands on the remote HPC cluster. This removes the need for users to manually manage SSH connections for simple queries or administrative tasks.

**Why it is useful:**
- **Host Abstraction**: You don't need to remember or type the remote hostname; the tool uses your configured default (e.g., `uva`).
- **Consistency**: All HPC operations (checking quotas, monitoring jobs, reading logs) use this same underlying mechanism, ensuring consistent behavior and error handling.
- **Transparency**: By using the `--debug` flag, you can see the exact shell command the tool is about to execute on the cluster.

**Example:**
Instead of manually running:
```bash
ssh uva 'df -h /scratch/your_user'
```
You can use:
```bash
cmc hpc run "df -h /scratch/your_user"
```

## Core Dependencies
This project depends on the following core components of the Cloudmesh AI ecosystem:
- [cloudmesh-ai-common](https://github.com/cloudmesh-ai/cloudmesh-ai-common)
- [cloudmesh-ai-cmc](https://github.com/cloudmesh-ai/cloudmesh-ai-cmc)
- [cloudmesh-ai-vpn](https://github.com/cloudmesh-ai/cloudmesh-ai-vpn)