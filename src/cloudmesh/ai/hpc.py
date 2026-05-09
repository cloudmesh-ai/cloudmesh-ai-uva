import os
import sys
import difflib
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
            console.error(msg)
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
            suggestion = self._suggest_match(key, available_keys) if key else None
            msg = f"Key {key} not found for host {host}. Available keys: {', '.join(available_keys)}"
            if suggestion:
                msg += f"\nDid you mean '{suggestion}'?"
            console.error(msg)
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
        if result:
            # du -sh returns "size directory", we only want the size
            return result.split()[0]
        return "unknown"

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
        remote_script = f"/tmp/job_{os.path.basename(script_path)}"
        
        # 3. Upload script
        # Using a simple ssh command to write the file to avoid scp dependency issues
        import base64
        encoded_content = base64.b64encode(full_script.encode()).decode()
        upload_cmd = f"ssh {host} 'echo {encoded_content} | base64 -d > {remote_script}'"
        
        if not self.debug:
            Shell.run(upload_cmd)
        else:
            console.msg(f"Debug: {upload_cmd}")

        # 4. Submit job
        submit_cmd = f"ssh {host} 'sbatch {remote_script}'"
        if not self.debug:
            result = Shell.run(submit_cmd)
            return result
        else:
            console.msg(f"Debug: {submit_cmd}")
            return "Submitted (debug)"

    def logs(self, job_id: str, tail: bool = False) -> str:
        """Read the Slurm output logs for a job."""
        # Slurm logs are typically slurm-<jobid>.out in the submission directory
        # We assume the user is in the correct directory or the log is in home
        cmd = f"ssh {self.host} 'tail -f slurm-{job_id}.out'" if tail else f"ssh {self.host} 'cat slurm-{job_id}.out'"
        
        if not self.debug:
            return Shell.run(cmd)
        else:
            console.msg(f"Debug: {cmd}")
            return "Log output (debug)"

    def job_info(self, job_id: str) -> str:
        """Get detailed information about a Slurm job."""
        cmd = f"ssh {self.host} 'scontrol show job {job_id}'"
        if not self.debug:
            return Shell.run(cmd)
        else:
            console.msg(f"Debug: {cmd}")
            return "Job info (debug)"

    def quota(self) -> str:
        """Check disk quota on the HPC."""
        cmd = f"ssh {self.host} 'quota -s'"
        if not self.debug:
            return Shell.run(cmd)
        else:
            console.msg(f"Debug: {cmd}")
            return "Quota info (debug)"

    def nodes(self, partition: Optional[str] = None) -> str:
        """Check node status for a partition."""
        host = self.host
        cmd = f"ssh {host} 'sinfo'"
        if partition:
            cmd = f"ssh {host} 'sinfo -p {partition}'"
        
        if not self.debug:
            return Shell.run(cmd)
        else:
            console.msg(f"Debug: {cmd}")
            return "Node info (debug)"

    def wait(self, job_id: str, interval: int = 30) -> bool:
        """Wait for a Slurm job to complete."""
        import time
        console.msg(f"Waiting for job {job_id} to complete...")
        while True:
            status = self.get_job_status(job_id)
            if not status or "R" not in status and "PD" not in status:
                console.msg(f"Job {job_id} has finished.")
                return True
            time.sleep(interval)

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
