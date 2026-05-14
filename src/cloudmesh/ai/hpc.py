import os
import sys
import difflib
import re
import yaml
import tempfile
import time
from cloudmesh.ai.common.io import console, load_yaml
from cloudmesh.ai.slurm import Slurm
from cloudmesh.ai.common.logging_utils import get_contextual_logger
from cloudmesh.ai.common.stopwatch import StopWatch
from cloudmesh.ai.common.Shell import Shell
from cloudmesh.ai.common.ssh.base import SSHBase

logger = get_contextual_logger("hpc")


from typing import Dict, List, Tuple, Optional, Any

class Hpc(SSHBase):
    def __init__(self, host: str = "uva", debug: bool = False) -> None:
        """
        Initialize the Hpc class.
        """
        super().__init__(debug=debug)
        self.host = host

        # 1. Load base partitions from the package
        try:
            path = os.path.join(os.path.dirname(__file__), "partitions.yaml")
            data = load_yaml(path)
            self.ai_config: Dict[str, Any] = data.get("cloudmesh", {}).get("ai", {})
            self.directive: Dict[str, Any] = self.ai_config.get("partition", {})
        except (FileNotFoundError, RuntimeError) as e:
            console.error(f"Failed to load base partitions.yaml: {e}")
            self.ai_config = {}
            self.directive = {}

        # 2. Load local overrides from ~/.cloudmesh/hpc.yaml
        local_path = os.path.expanduser("~/.cloudmesh/hpc.yaml")
        if os.path.exists(local_path):
            try:
                local_data = load_yaml(local_path)
                # Local data can be the full structure or just the 'ai' part
                ai_overrides = local_data.get("cloudmesh", {}).get("ai", local_data)
                
                # Merge global ai_config (e.g., default host/partition)
                self.ai_config.update(ai_overrides)
                
                # Merge partitions
                local_partitions = ai_overrides.get("partition", {})
                for h, p in local_partitions.items():
                    if h not in self.directive:
                        self.directive[h] = {}
                    self.directive[h].update(p)
                
                # Update the directive reference in ai_config to match the merged one
                self.ai_config["partition"] = self.directive
                
            except Exception as e:
                console.error(f"Failed to load local config {local_path}: {e}")

    def _suggest_match(self, word: str, possibilities: List[str]) -> Optional[str]:
        """Suggest the closest match from a list of possibilities."""
        matches = difflib.get_close_matches(word, possibilities, n=1, cutoff=0.6)
        return matches[0] if matches else None

    def parse_sbatch_parameter(self, parameters: str) -> Dict[str, str]:
        """
        Parse the parameters string and convert it to a dictionary.
        Expected format: "key1:val1,key2:val2"
        Supports aliases defined in local config.
        Raises ValueError if the format is invalid.
        """
        # Common valid Slurm parameters for basic validation
        valid_params = {
            "nodes", "ntasks", "cpus-per-task", "time", "partition", 
            "mem", "gres", "job-name", "output", "error", "mail-type", "mail-user"
        }
        
        result = {}
        if not parameters:
            return result

        # Handle aliases from local config
        aliases = self.ai_config.get("aliases", {})
        
        data = parameters.split(",")
        for line in data:
            line = line.strip()
            if not line:
                continue
            
            # Check if the line is an alias
            if line in aliases:
                alias_val = aliases[line]
                # Recursively parse the alias value
                result.update(self.parse_sbatch_parameter(alias_val))
                continue

            if ":" not in line:
                raise ValueError(f"Invalid sbatch parameter format: '{line}'. Expected 'key:value' or a defined alias.")
            
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            
            if not key or not value:
                raise ValueError(f"Invalid sbatch parameter: '{line}'. Both key and value must be provided.")
            
            if key not in valid_params:
                console.warn(f"Unknown sbatch parameter: '{key}'. It may be ignored by Slurm.")
            
            result[key] = value
        return result

    def create_slurm_directives(self, host: Optional[str] = None, key: Optional[str] = None) -> str:
        """Create Slurm directives based on the provided host and key."""
        host = host or self.host
        try:
            directives = self.directive[host][key]
        except KeyError:
            suggestion = self._suggest_match(key, list(self.directive.get(host, {}).keys()))
            msg = f"In directive searching for:\n  host {host}\n  key {key}\nNot found"
            if suggestion:
                msg += f"\nDid you mean '{suggestion}'?"
            raise ValueError(msg)

        block = ""
        for k, v in directives.items():
            block += f"#SBATCH --{k}={v}\n"
        return block

    def get_partition_data(self, host: str) -> Tuple[Optional[List[str]], Optional[List[List[str]]]]:
        """
        Return raw partition data for table display.
        Returns a tuple of (header_list, data_list).
        """
        partitions = self.directive.get(host, {})
        if not partitions:
            return None, None

        display_partitions = {k: v for k, v in partitions.items() if k != "default"}
        if not display_partitions:
            return None, None

        default_key = self.get_default_partition(host)

        all_directive_keys = set()
        for v in display_partitions.values():
            all_directive_keys.update(v.keys())
        sorted_keys = sorted(list(all_directive_keys))

        header = ["Default", "Key"] + sorted_keys
        
        data = []
        for k, v in display_partitions.items():
            is_default = "*" if k == default_key else " "
            row = [is_default, k] + [str(v.get(dk, "")) for dk in sorted_keys]
            data.append(row)

        return header, data

    def get_partition_static_data(self, host: str) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """
        Prepare basic partition data for interactive selection.
        Returns a tuple of (header_string, choices_list).
        """
        header_list, data_list = self.get_partition_data(host)
        if not header_list or not data_list:
            return None, None

        # Add resource columns to header (initially empty)
        header_list = header_list + ["Idle Nodes", "GPU Usage (Avail/Used/Total)"]
        
        # Update data rows with placeholders for resource counts
        updated_data = []
        for row in data_list:
            updated_row = row + ["...", "..."]
            updated_data.append(updated_row)

        # Calculate column widths for alignment
        col_widths = {name: len(name) for name in header_list}
        for row in updated_data:
            for i, val in enumerate(row):
                col_widths[header_list[i]] = max(col_widths[header_list[i]], len(val))

        # Create formatted header
        header = " | ".join([name.ljust(col_widths[name]) for name in header_list])

        # Create formatted rows as choices
        choices = []
        for row in updated_data:
            row_str = " | ".join([val.ljust(col_widths[header_list[i]]) for i, val in enumerate(row)])
            choices.append({"name": row_str, "value": row[1]})

        return header, choices

    def get_partition_realtime_data(self, host: str) -> Dict[str, Dict[str, Any]]:
        """
        Fetch real-time resource availability for all partitions on the host.
        Returns a map of partition_name -> resource_stats.
        """
        resource_map = {}
        try:
            # 1. Get all node states and GRES
            sinfo_cmd = "sinfo -N -o \"%P %N %G %t\""
            sinfo_output = self._run_remote(host, sinfo_cmd).stdout
            
            if not sinfo_output:
                return resource_map

            mix_nodes = []
            node_data = []
            for line in sinfo_output.strip().split("\n"):
                parts = line.split()
                if len(parts) < 4: continue
                partitions, node, gres, state = parts[0].split(","), parts[1], parts[2], parts[3]
                node_data.append((partitions, node, gres, state))
                if state == "mix":
                    mix_nodes.append(node)

            node_allocations = {}
            if mix_nodes:
                nodes_list = ",".join(mix_nodes)
                sctrl_cmd = f"scontrol show node {nodes_list}"
                sctrl_output = self._run_remote(host, sctrl_cmd).stdout
                
                if sctrl_output:
                    node_blocks = sctrl_output.split("NodeName=")[1:]
                    for block in node_blocks:
                        node_name = block.split()[0]
                        alloc_match = re.search(r'AllocTRES=[^=]*gres/gpu=([^,\s]+)', block)
                        if alloc_match:
                            val = alloc_match.group(1)
                            num_match = re.search(r'(\d+)$', val)
                            node_allocations[node_name] = int(num_match.group(1)) if num_match else 1
                        else:
                            node_allocations[node_name] = 0

            for partitions, node, gres, state in node_data:
                if state in ["idle", "mix"]:
                    total_gpus = 0
                    if "gpu" in gres:
                        # Match gpu:X or gpu:type:X
                        match = re.search(r'gpu:([^:]*:)?(\d+)$', gres)
                        total_gpus = int(match.group(2)) if match else 1
                    
                    if state == "idle":
                        available_gpus, is_idle_node = total_gpus, True
                    else: # state == "mix"
                        used_gpus = node_allocations.get(node, 0)
                        available_gpus, is_idle_node = max(0, total_gpus - used_gpus), False
                    
                    for p in partitions:
                        if p not in resource_map:
                            resource_map[p] = {"nodes": 0, "gpus": 0, "used_gpus": 0, "total_nodes": 0, "total_gpus": 0}
                        if is_idle_node:
                            resource_map[p]["nodes"] += 1
                        resource_map[p]["gpus"] += available_gpus
                        resource_map[p]["used_gpus"] += (total_gpus - available_gpus)
                        resource_map[p]["total_nodes"] += 1
                        resource_map[p]["total_gpus"] += total_gpus
        except Exception as e:
            console.error(f"Failed to fetch real-time resources: {e}")

        return resource_map


    def get_default_partition(self, host: str) -> Optional[str]:
        """Return the default partition for the host if it exists."""
        if host not in self.directive:
            return None

        host_partitions = self.directive.get(host, {})

        # 1. Check for host-specific default
        if "default" in host_partitions:
            # Return the actual partition name pointed to by 'default'
            default_val = host_partitions["default"].get("partition")
            if default_val:
                return default_val

        # 2. Check for global default
        global_default = self.ai_config.get("default", {}).get("partition")
        if global_default:
            # Return only the short key (e.g., 'a100-dgx' from 'cloudmesh.ai.partition.uva.a100-dgx')
            return global_default.split(".")[-1]

        # 3. Fallback to the first available partition for the host
        # Filter out 'default' key if it exists
        keys = [k for k in host_partitions.keys() if k != "default"]
        return next(iter(keys)) if keys else None

    def get_tutorial_url(self, keyword: Optional[str] = None) -> str:
        """Return the tutorial URL for the given keyword."""
        tutorials = self.ai_config.get("tutorials", {})
        return tutorials.get(keyword, tutorials.get("default", "https://infomall.org/uva/docs/tutorial/"))

    def get_config_path(self) -> str:
        """Return the path to the config.csv file."""
        # The config.csv is located in the same directory as this file
        return os.path.join(os.path.dirname(__file__), "config.csv")

    def get_login_command(self, host: Optional[str], key: Optional[str], sbatch_params: Optional[Dict[str, str]] = None) -> Optional[str]:
        """Construct the SSH ijob command without executing it."""
        host = host or self.host
        if not key:
            key = "default"

        try:
            directives = self.directive[host][key].copy()
        except KeyError:
            return None

        if sbatch_params:
            directives.update(sbatch_params)

        parameters = "".join([f" --{k}={v}" for k, v in directives.items()])
        return f'ssh -tt {host} "/opt/rci/bin/ijob{parameters}"'

    def get_node_gpu_usage(self, node_name: str) -> Dict[str, Any]:
        """
        Get the GPU usage for a specific node.
        Returns a dictionary with total, used, and available GPUs.
        """
        cmd = f"scontrol show node {node_name}"
        output = self.run_command(cmd)
        
        if not output:
            return {"error": f"No output received for node {node_name}"}
        
        try:
            # Parse CfgTRES for total GPUs
            cfg_match = re.search(r'CfgTRES=[^=]*gres/gpu=([^,\s]+)', output)
            total_gpus = 0
            if cfg_match:
                val = cfg_match.group(1)
                num_match = re.search(r'(\d+)$', val)
                total_gpus = int(num_match.group(1)) if num_match else 1
            
            # Parse AllocTRES for used GPUs
            alloc_match = re.search(r'AllocTRES=[^=]*gres/gpu=([^,\s]+)', output)
            used_gpus = 0
            if alloc_match:
                val = alloc_match.group(1)
                num_match = re.search(r'(\d+)$', val)
                used_gpus = int(num_match.group(1)) if num_match else 1
            
            return {
                "node": node_name,
                "total": total_gpus,
                "used": used_gpus,
                "available": max(0, total_gpus - used_gpus)
            }
        except Exception as e:
            return {"error": f"Failed to parse GPU usage: {e}"}

    def get_cluster_gpu_usage(self) -> List[Dict[str, Any]]:
        """
        Get GPU usage for all nodes across all partitions on the host.
        Returns a list of nodes sorted by available GPUs (descending).
        """
        all_nodes_usage = []
        resource_map = self.get_partition_realtime_data(self.host)
        
        # We need to get the actual node data. 
        # get_partition_realtime_data already does the sinfo and scontrol calls.
        # However, it aggregates by partition. We want a node-centric view.
        
        try:
            # Re-run the sinfo command to get the raw node list
            sinfo_cmd = "sinfo -N -o \"%P %N %G %t\""
            sinfo_output = self._run_remote(self.host, sinfo_cmd).stdout
            if not sinfo_output:
                return []

            # Get all mix nodes for scontrol lookup
            mix_nodes = []
            node_data = []
            for line in sinfo_output.strip().split("\n"):
                parts = line.split()
                if len(parts) < 4: continue
                partitions, node, gres, state = parts[0].split(","), parts[1], parts[2], parts[3]
                node_data.append((partitions, node, gres, state))
                if state == "mix":
                    mix_nodes.append(node)

            node_allocations = {}
            if mix_nodes:
                nodes_list = ",".join(mix_nodes)
                sctrl_output = self._run_remote(self.host, f"scontrol show node {nodes_list}").stdout
                if sctrl_output:
                    node_blocks = sctrl_output.split("NodeName=")[1:]
                    for block in node_blocks:
                        node_name = block.split()[0]
                        alloc_match = re.search(r'AllocTRES=[^=]*gres/gpu=([^,\s]+)', block)
                        if alloc_match:
                            val = alloc_match.group(1)
                            num_match = re.search(r'(\d+)$', val)
                            node_allocations[node_name] = int(num_match.group(1)) if num_match else 1
                        else:
                            node_allocations[node_name] = 0

            for partitions, node, gres, state in node_data:
                total_gpus = 0
                if "gpu" in gres:
                    match = re.search(r'gpu:([^:]*:)?(\d+)$', gres)
                    total_gpus = int(match.group(2)) if match else 1
                
                if state == "idle":
                    available_gpus = total_gpus
                elif state == "mix":
                    used_gpus = node_allocations.get(node, 0)
                    available_gpus = max(0, total_gpus - used_gpus)
                else:
                    available_gpus = 0
                
                all_nodes_usage.append({
                    "node": node,
                    "partition": partitions[0], # Primary partition
                    "total": total_gpus,
                    "used": total_gpus - available_gpus,
                    "available": available_gpus,
                    "state": state
                })
        except Exception as e:
            logger.error(f"Failed to get cluster GPU usage: {e}")

        # Sort by available GPUs descending
        return sorted(all_nodes_usage, key=lambda x: x["available"], reverse=True)

    def get_reservation_gpu_usage(self, reservation_name: str) -> Dict[str, Any]:
        """
        Get the aggregate GPU usage for a Slurm reservation.
        """
        cmd = f"scontrol show reservation {reservation_name}"
        output = self.run_command(cmd)
        
        if not output or "Invalid reservation" in output:
            return {"error": f"Reservation {reservation_name} not found or no output received."}
        
        try:
            # Find the Nodes=... part of the reservation output
            nodes_match = re.search(r'Nodes=([^,\s]+)', output)
            if not nodes_match:
                return {"error": f"No nodes found for reservation {reservation_name}"}
            
            nodes_str = nodes_match.group(1)
            # Slurm node lists can be complex (e.g., node[01-04,06])
            # We use scontrol show node to expand them or just query the list
            # A simpler way to get the expanded list is to use scontrol show node with the list
            nodes_output = self.run_command(f"scontrol show node {nodes_str}")
            
            total_gpus = 0
            used_gpus = 0
            
            # Split by NodeName= to process each node in the reservation
            node_blocks = nodes_output.split("NodeName=")[1:]
            for block in node_blocks:
                # Total GPUs
                cfg_match = re.search(r'CfgTRES=[^=]*gres/gpu=([^,\s]+)', block)
                if cfg_match:
                    val = cfg_match.group(1)
                    num_match = re.search(r'(\d+)$', val)
                    total_gpus += int(num_match.group(1)) if num_match else 1
                
                # Used GPUs
                alloc_match = re.search(r'AllocTRES=[^=]*gres/gpu=([^,\s]+)', block)
                if alloc_match:
                    val = alloc_match.group(1)
                    num_match = re.search(r'(\d+)$', val)
                    used_gpus += int(num_match.group(1)) if num_match else 1
            
            return {
                "reservation": reservation_name,
                "total": total_gpus,
                "used": used_gpus,
                "available": max(0, total_gpus - used_gpus)
            }
        except Exception as e:
            return {"error": f"Failed to parse reservation GPU usage: {e}"}

    def run_command(self, command: str, host: Optional[str] = None) -> str:
        """Execute an arbitrary command on the HPC."""
        target_host = host or self.host
        try:
            result = self._run_remote(target_host, command)
            return result.stdout
        except Exception as e:
            console.error(f"Failed to execute command on {target_host}: {e}")
            return ""

    def login(self, host: Optional[str], key: Optional[str], sbatch_params: Optional[Dict[str, str]] = None) -> str:
        """SSH on HPC by executing an interactive job command."""
        command = self.get_login_command(host, key, sbatch_params)
        if not command:
            # Handle the error case as before
            target_host = host or self.host
            available_keys = list(self.directive.get(target_host, {}).keys())
            suggestion = self._suggest_match(key, available_keys) if key else None
            msg = f"Key {key} not found for host {target_host}. Available keys: {', '.join(available_keys)}"
            if suggestion:
                msg += f"\nDid you mean '{suggestion}'?"
            console.error(msg)
            return

        console.msg(command)
        if not self.debug:
            try:
                # Use os.system for interactive sessions to ensure the terminal 
                # is connected directly to the process. Shell.run captures output,
                # which causes interactive shells to hang.
                os.system(command)
            except Exception as e:
                console.error(f"Login failed: {e}")
        return ""

    def create_apptainer_image(self, name: str) -> None:
        """Create an apptainer image on HPC."""
        try:
            cache = os.environ.get("APPTAINER_CACHEDIR", "/scratch/$USER/.apptainer/")
            console.banner("Cloudmesh HPC Apptainer Build")

            image = os.path.basename(name.replace(".def", ".sif"))
            logger.debug(f"Building image {image} from {name}")

            console.print(f"Image name       : {image}")
            console.print(f"Singularity cache: {cache}")
            console.print(f"Definition       : {name}")
            console.print()
            StopWatch.start("build image")
            Shell.run(f"apptainer build {image} {name}")
            StopWatch.stop("build image")

            # Use Shell.run to get size
            size_output = Shell.run(f"du -sh {image}")
            size = size_output.split()[0] if size_output else "unknown"
            timer = StopWatch.get("build image")
            console.print()
            console.print(f"Time to build {image}s ({size}) {timer}s")
            console.print()

        except (RuntimeError, OSError) as e:
            console.error(f"Apptainer build failed: {e}")

    def jupyter(self, port: int = 8000) -> None:
        """Start a Jupyter notebook on HPC."""
        console.print(f"Starting Jupyter on port {port}...")
        console.print("Note: This requires an active VPN connection.")
        console.print(f"Command: jupyter notebook --no-browser --port={port}")
        console.print(f"Tunnel: ssh -L 8080:localhost:{port} hpc")

    def cancel(self, job_id: str) -> str:
        """Cancel a Slurm job."""
        console.msg(f"Canceling job {job_id}...")
        try:
            result = self._run_remote(self.host, f"scancel {job_id}")
            return result.stdout
        except Exception as e:
            console.error(f"Failed to cancel job {job_id}: {e}")
            return ""

    def get_job_status(self, job_id: str) -> str:
        """Get the status of a specific Slurm job."""
        try:
            result = self._run_remote(self.host, f"squeue -j {job_id}")
            return result.stdout
        except Exception as e:
            console.error(f"Failed to get status for job {job_id}: {e}")
            return ""

    def list_jobs(self) -> str:
        """List all active Slurm jobs for the current user."""
        try:
            result = self._run_remote(self.host, "squeue -u $USER")
            return result.stdout
        except Exception as e:
            console.error(f"Failed to list jobs: {e}")
            return ""

    def search_jobs_by_node(self, node_regex: str) -> List[Dict[str, str]]:
        """
        Find jobs running on nodes that match the given regex.
        
        Args:
            node_regex: Regex to match node names.
            
        Returns:
            A list of dictionaries containing detailed job information.
        """
        # Comprehensive format: User|JobID|Name|State|TimeUsed|TimeLeft|Node|CPUs|Memory|QOS|Partition
        fmt = "%u|%i|%j|%T|%M|%L|%N|%C|%m|%q|%P"
        cmd = f"squeue -o \"{fmt}\""
        try:
            result = self._run_remote(self.host, cmd)
            output = result.stdout
            if not output:
                return []

            matches = []
            pattern = re.compile(node_regex)
            
            lines = output.strip().split("\n")
            # Skip header
            for line in lines[1:]:
                if not line.strip():
                    continue
                parts = line.split("|")
                if len(parts) < 11:
                    continue
                
                # The node list is at index 6
                node = parts[6]
                if pattern.search(node):
                    matches.append({
                        "User": parts[0],
                        "JobID": parts[1],
                        "Name": parts[2],
                        "State": parts[3],
                        "TimeUsed": parts[4],
                        "TimeLeft": parts[5],
                        "Node": node,
                        "CPUs": parts[7],
                        "Memory": parts[8],
                        "QOS": parts[9],
                        "Partition": parts[10]
                    })
            return matches
        except Exception as e:
            console.error(f"Failed to search jobs by node: {e}")
            return []

    def storage(self, directory: str) -> str:
        """Get storage information for a directory."""
        try:
            result = self._run_remote(self.host, f"du -sh {directory}")
            if result.stdout:
                # du -sh returns "size directory", we only want the size
                return result.stdout.split()[0]
        except Exception as e:
            console.error(f"Failed to get storage info for {directory}: {e}")
        return "unknown"

    def edit(self, filename: str, editor: str = "emacs") -> str:
        """Edit a file on the remote host."""
        # For interactive editing, we still use Shell.run with -t to ensure a TTY
        command = f"ssh -t {self.host} '{editor} {filename}'"
        console.msg(f"Editing {filename} with {editor}...")
        if not self.debug:
            Shell.run(command)
        return ""

    def set_default(self, host: str, partition: Optional[str] = None) -> None:
        """Set the default host and partition in the local config file."""
        local_path = os.path.expanduser("~/.cloudmesh/hpc.yaml")
        
        # Load existing config or start fresh
        config = {}
        if os.path.exists(local_path):
            try:
                config = load_yaml(local_path)
            except Exception:
                config = {}

        # Ensure structure: cloudmesh -> ai
        if "cloudmesh" not in config:
            config["cloudmesh"] = {}
        if "ai" not in config["cloudmesh"]:
            config["cloudmesh"]["ai"] = {}
        
        ai_config = config["cloudmesh"]["ai"]
        
        # Set default host/partition
        if "default" not in ai_config:
            ai_config["default"] = {}
        
        ai_config["default"]["host"] = host
        if partition:
            # Store as full path to match expected format if needed, 
            # but the Hpc class handles short keys too.
            ai_config["default"]["partition"] = f"cloudmesh.ai.partition.{host}.{partition}"

        # Save back to file
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "w") as f:
                yaml.dump(config, f)
            console.msg(f"Default host set to {host}" + (f" and partition to {partition}" if partition else ""))
        except Exception as e:
            console.error(f"Failed to save local config: {e}")

    def submit(self, script_path: str, key: Optional[str] = None, sbatch_params: Optional[Dict[str, str]] = None) -> str:
        """Upload a script and submit it as a Slurm job."""
        host = self.host
        key = key or self.get_default_partition(host)
        if not key:
            raise ValueError(f"No partition key provided and no default found for host {host}")

        # 1. Generate directives
        directives = self.create_slurm_directives(host, key)
        if sbatch_params:
            for k, v in sbatch_params.items():
                directives += f"#SBATCH --{k}={v}\n"

        # 2. Read script and prepend directives
        with open(script_path, "r") as f:
            script_content = f.read()
        
        full_script = directives + script_content
        
        # Create a temporary local file to upload
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write(full_script)
            tmp_path = tmp.name

        remote_script = f"/tmp/job_{os.path.basename(script_path)}"
        
        try:
            # 3. Upload script using Fabric put
            self.put(tmp_path, remote_script, host)
            
            # 4. Submit job
            result = self._run_remote(host, f"sbatch {remote_script}")
            return result.stdout
        except Exception as e:
            console.error(f"Failed to submit job: {e}")
            return ""
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def logs(self, job_id: str, tail: bool = False, follow: bool = False) -> str:
        """Read the Slurm output logs for a job."""
        # Try to find the actual StdOut and StdErr paths from scontrol
        stdout_path = f"slurm-{job_id}.out"
        stderr_path = f"slurm-{job_id}.err"
        
        info = self.job_info(job_id)
        if info:
            # Look for StdOut=/path/to/log
            out_match = re.search(r'StdOut=([^\s]+)', info)
            if out_match:
                stdout_path = out_match.group(1)
            
            # Look for StdErr=/path/to/log
            err_match = re.search(r'StdErr=([^\s]+)', info)
            if err_match:
                stderr_path = err_match.group(1)

        if follow:
            # Streaming mode: use tail -f
            cmd = f"ssh -t {self.host} 'tail -f {stdout_path} {stderr_path}'"
            if not self.debug:
                console.banner(f"Streaming logs for job {job_id} (Out: {stdout_path}, Err: {stderr_path})")
                os.system(cmd)
                return ""
            else:
                console.msg(f"Debug: {cmd}")
                return "Log output (debug)"
        elif tail:
            # Snapshot mode: use tail -n 20
            for label, path in [("STDOUT", stdout_path), ("STDERR", stderr_path)]:
                try:
                    res = self._run_remote(self.host, f"tail -n 20 {path}")
                    if res.stdout:
                        console.banner(f"{label} (Last 20 lines)", path)
                        console.print(res.stdout)
                except Exception as e:
                    console.error(f"Error reading {label} from {path}: {e}")
            return ""
        else:
            # Full read mode: use cat
            for label, path in [("STDOUT", stdout_path), ("STDERR", stderr_path)]:
                try:
                    res = self._run_remote(self.host, f"cat {path}")
                    if res.stdout:
                        console.banner(label, path)
                        console.print(res.stdout)
                except Exception as e:
                    console.error(f"Error reading {label} from {path}: {e}")
            
            return ""

    def job_info(self, job_id: str) -> str:
        """Get detailed information about a Slurm job."""
        try:
            result = self._run_remote(self.host, f"scontrol show job {job_id}")
            return result.stdout
        except Exception as e:
            console.error(f"Failed to get job info for {job_id}: {e}")
            return ""

    def quota(self) -> str:
        """Check disk quota on the HPC."""
        try:
            # Use hdquota as 'quota -s' fails on some HPC clusters (e.g., UVA)
            result = self._run_remote(self.host, "hdquota")
            return result.stdout
        except Exception as e:
            console.error(f"Failed to get quota: {e}")
            return ""

    def get_billing_usage(self, username: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get billing and core-hour usage using sreport.
        """
        # Use sreport for 'user' entity to get usage statistics
        # We use the current user if none provided
        user = username or os.environ.get("USER")
        if not user:
            return []
        
        try:
            # sreport for user usage
            return self.sreport(entity="user", filter_val=user)
        except Exception as e:
            logger.error(f"Failed to get billing usage for {user}: {e}")
            return []

    def nodes(self, partition: Optional[str] = None) -> str:
        """Check node status for a partition."""
        cmd = "sinfo"
        if partition:
            cmd = f"sinfo -p {partition}"
        
        try:
            result = self._run_remote(self.host, cmd)
            return result.stdout
        except Exception as e:
            console.error(f"Failed to get node status: {e}")
            return ""

    def sinfo(self, partition: Optional[str] = None, json_support: bool = False, format: str = "%all") -> List[Dict[str, Any]]:
        """
        Return sinfo output as a list of dictionaries, with summary metrics merged into each node.
        Delegates to the Slurm class.
        """
        slurm = Slurm(host=self.host, debug=self.debug)
        return slurm.sinfo(partition=partition, json_support=json_support, format=format)

    def sreport(self, entity: str = "user", filter_val: Optional[str] = None, 
                start: Optional[str] = None, end: Optional[str] = None, 
                stat: bool = False) -> List[Dict[str, Any]]:
        """
        Get usage report using sreport for a specific entity.
        Delegates to the Slurm class.
        """
        slurm = Slurm(host=self.host, debug=self.debug)
        return slurm.sreport(entity=entity, filter_val=filter_val, start=start, end=end, stat=stat)

    def check_resource_availability(self, key: str) -> Dict[str, Any]:
        """
        Check if resources are available for the given partition key.
        Returns with availability details.
        """
        host = self.host
        try:
            # Get the actual Slurm partition name from the key
            partition_name = self.directive[host][key].get("partition")
            if not partition_name:
                return {"error": "Partition name not found for key"}

            # Run sinfo to get node status, GRES, and state
            # %N: Node list, %G: Generic Resources (GRES), %t: State
            cmd = f"sinfo -p {partition_name} -N -o \"%N %G %t\""
            result = self._run_remote(host, cmd)
            output = result.stdout
            
            if not output:
                return {"error": "No nodes found in partition"}

            lines = output.strip().split("\n")
            idle_nodes = []
            all_nodes = []
            
            for line in lines:
                parts = line.split()
                if len(parts) < 3:
                    continue
                
                node, gres, state = parts[0], parts[1], parts[2]
                node_info = {"node": node, "gres": gres, "state": state}
                all_nodes.append(node_info)
                
                # 'idle' means completely free, 'mix' means partially used
                if state == "idle":
                    idle_nodes.append(node_info)

            return {
                "partition": partition_name,
                "total_nodes": len(all_nodes),
                "idle_nodes": len(idle_nodes),
                "idle_details": idle_nodes,
                "all_details": all_nodes
            }
        except Exception as e:
            return {"error": str(e)}

    def wait(self, job_id: str, interval: int = 30) -> bool:
        """Wait for a Slurm job to complete with detailed status updates."""
        console.msg(f"Waiting for job {job_id} to complete...")
        while True:
            status = self.get_job_status(job_id)
            if not status:
                console.msg(f"Job {job_id} is no longer in the queue (finished or failed).")
                return True
            
            if "R" in status:
                console.msg(f"Job {job_id} is currently RUNNING...")
            elif "PD" in status:
                console.msg(f"Job {job_id} is PENDING...")
            else:
                console.msg(f"Job {job_id} has finished (Status: {status.strip()}).")
                return True
            
            time.sleep(interval)

    def monitor_job(self, job_id: str, interval: int = 10) -> None:
        """Actively monitor a job and print status updates."""
        console.banner(f"Monitoring Job {job_id}")
        try:
            self.wait(job_id, interval)
        except KeyboardInterrupt:
            console.msg("Monitoring stopped by user.")

    def check(self) -> None:
        """Perform a health check of the HPC environment."""
        from cloudmesh.ai.vpn.vpn import Vpn
        
        console.banner("HPC Health Check")
        
        # 1. VPN Check
        try:
            vpn = Vpn(service="hpc")
            vpn_ok = vpn.enabled()
            status_vpn = "[green]✓[/green]" if vpn_ok else "[red]✗[/red]"
            console.print(f"{status_vpn} VPN Connected")
        except Exception as e:
            console.print(f"[red]✗[/red] VPN Check Failed: {e}")

        # 2. SSH Check
        try:
            res = self._run_remote(self.host, "hostname")
            if res.stdout:
                console.print(f"[green]✓[/green] SSH Access Verified ({res.stdout.strip()})")
            else:
                console.print(f"[red]✗[/red] SSH Access: No response from host")
        except Exception as e:
            console.print(f"[red]✗[/red] SSH Access Failed: {e}")

        # 3. Quota Check
        try:
            q = self.quota()
            if q:
                console.print(f"[green]✓[/green] Disk Quota Accessible")
            else:
                console.print(f"[yellow]⚠[/yellow] Disk Quota: No data returned")
        except Exception as e:
            console.print(f"[red]✗[/red] Disk Quota Check Failed: {e}")
        
        console.print()

    def template(self, key: Optional[str] = None) -> str:
        """Generate a boilerplate .sbatch script."""
        key = key or self.get_default_partition(self.host)
        if not key:
            return "# No default partition found. Please specify a key."
        
        directives = self.create_slurm_directives(self.host, key)
        template = (
            f"{directives}"
            f"#SBATCH --output=slurm-%j.out\n"
            f"#SBATCH --error=slurm-%j.err\n\n"
            f"#!/bin/bash\n"
            f"# Your commands here\n"
            f"echo 'Hello from Slurm job on {self.host} partition {key}'\n"
            f"hostname\n"
        )
        return template
