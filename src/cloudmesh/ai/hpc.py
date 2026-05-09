import os
import sys
from cloudmesh.ai.common.io import console, load_yaml
from cloudmesh.ai.common.logging_utils import get_contextual_logger
from cloudmesh.ai.common.stopwatch import StopWatch
from cloudmesh.ai.common.Shell import Shell

logger = get_contextual_logger("hpc")


from typing import Dict, List, Tuple, Optional, Any

class Hpc:
    def __init__(self, host: str = "uva", debug: bool = False) -> None:
        """
        Initialize the Hpc class.
        """
        self.debug = debug
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

    def parse_sbatch_parameter(self, parameters: str) -> Dict[str, str]:
        """
        Parse the parameters string and convert it to a dictionary.
        Expected format: "key1:val1,key2:val2"
        Raises ValueError if the format is invalid.
        """
        result = {}
        if not parameters:
            return result

        data = parameters.split(",")
        for line in data:
            line = line.strip()
            if not line:
                continue
            if ":" not in line:
                raise ValueError(f"Invalid sbatch parameter format: '{line}'. Expected 'key:value'.")
            
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            
            if not key or not value:
                raise ValueError(f"Invalid sbatch parameter: '{line}'. Both key and value must be provided.")
            
            result[key] = value
        return result

    def create_slurm_directives(self, host: Optional[str] = None, key: Optional[str] = None) -> str:
        """Create Slurm directives based on the provided host and key."""
        host = host or self.host
        try:
            directives = self.directive[host][key]
        except KeyError:
            console.error(
                f"In directive searching for:\n  host {host}\n  key {key}\nNot found"
            )
            sys.exit(1)

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

    def get_partition_table_data(self, host: str) -> Tuple[Optional[str], Optional[List[Dict[str, str]]]]:
        """
        Prepare table-like data for interactive selection.
        Returns a tuple of (header_string, choices_list).
        """
        header_list, data_list = self.get_partition_data(host)
        if not header_list or not data_list:
            return None, None

        # Calculate column widths for alignment
        col_widths = {name: len(name) for name in header_list}
        for row in data_list:
            for i, val in enumerate(row):
                col_widths[header_list[i]] = max(col_widths[header_list[i]], len(val))

        # Create formatted header
        header = " | ".join([name.ljust(col_widths[name]) for name in header_list])

        # Create formatted rows as choices
        choices = []
        # We need the original keys to map back to values
        # The second column in data_list is the key
        for row in data_list:
            row_str = " | ".join([val.ljust(col_widths[header_list[i]]) for i, val in enumerate(row)])
            choices.append({"name": row_str, "value": row[1]})

        return header, choices

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
        # The config.csv is located in the package root (one level up from src/cloudmesh/ai/)
        # This is a more robust way to find it relative to this file
        return os.path.join(os.path.dirname(__file__), "..", "config.csv")

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

    def login(self, host: Optional[str], key: Optional[str], sbatch_params: Optional[Dict[str, str]] = None) -> str:
        """SSH on HPC by executing an interactive job command."""
        command = self.get_login_command(host, key, sbatch_params)
        if not command:
            # Handle the error case as before
            host = host or self.host
            available_keys = list(self.directive.get(host, {}).keys())
            console.error(
                f"Key {key} not found for host {host}. Available keys: {', '.join(available_keys)}"
            )
            return

        console.msg(command)
        if not self.debug:
            Shell.run(command)
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
        command = f"ssh {self.host} 'scancel {job_id}'"
        console.msg(f"Canceling job {job_id}...")
        if not self.debug:
            Shell.run(command)
        return ""

    def get_job_status(self, job_id: str) -> str:
        """Get the status of a specific Slurm job."""
        command = f"ssh {self.host} 'squeue -j {job_id}'"
        if self.debug:
            console.msg(f"Debug: {command}")
            return f"Job {job_id} status: Not executed (debug)"
        return Shell.run(command)

    def list_jobs(self) -> str:
        """List all active Slurm jobs for the current user."""
        command = f"ssh {self.host} 'squeue -u $USER'"
        if self.debug:
            console.msg(f"Debug: {command}")
            return "Active jobs: Not executed (debug)"
        return Shell.run(command)

    def storage(self, directory: str) -> str:
        """Get storage information for a directory."""
        command = f"ssh {self.host} 'du -sh {directory}'"
        if self.debug:
            console.msg(f"Debug: {command}")
            return f"Storage info for {directory}: Not executed (debug)"

        result = Shell.run(command)
        return result

    def edit(self, filename: str, editor: str = "emacs") -> str:
        """Edit a file on the remote host."""
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
                import yaml
                yaml.dump(config, f)
            console.msg(f"Default host set to {host}" + (f" and partition to {partition}" if partition else ""))
        except Exception as e:
            console.error(f"Failed to save local config: {e}")
