import os
import sys
from cloudmesh.ai.common.io import console, load_yaml
from cloudmesh.ai.common.logging_utils import get_contextual_logger
from cloudmesh.ai.common.stopwatch import StopWatch
from cloudmesh.ai.common.Shell import Shell

logger = get_contextual_logger("uva")


class Uva:
    def __init__(self, host="uva", debug=False):
        """
        Initialize the Uva class.
        """
        self.debug = debug
        self.host = host

        try:
            # Load partitions from the file relative to this module
            path = os.path.join(os.path.dirname(__file__), "partitions.yaml")
            data = load_yaml(path)
            self.ai_config = data.get("cloudmesh", {}).get("ai", {})
            self.directive = self.ai_config.get("partition", {})
        except Exception as e:
            console.error(f"Failed to load partitions.yaml: {e}")
            self.ai_config = {}
            self.directive = {}

    def parse_sbatch_parameter(self, parameters):
        """Parse the parameters string and convert it to a dictionary."""
        result = {}
        data = parameters.split(",")
        for line in data:
            if ":" in line:
                key, value = line.split(":", 1)
                result[key] = value
        return result

    def create_slurm_directives(self, host=None, key=None):
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

    def get_partition_table_data(self, host):
        """
        Prepare table-like data for interactive selection.
        Returns a tuple of (header_string, choices_list).
        """
        partitions = self.directive.get(host, {})
        if not partitions:
            return None, None

        # Filter out the 'default' key from the table rows as it's a pointer
        display_partitions = {k: v for k, v in partitions.items() if k != "default"}
        if not display_partitions:
            return None, None

        # Get the default partition for this host to mark it in the table
        default_key = self.get_default_partition(host)

        # Identify all unique directive keys across all partitions
        all_directive_keys = set()
        for v in display_partitions.values():
            all_directive_keys.update(v.keys())
        sorted_keys = sorted(list(all_directive_keys))

        # Calculate column widths for alignment
        col_widths = {dk: len(dk) for dk in sorted_keys}
        col_widths["Key"] = 10  # Default width for Key
        col_widths["Default"] = 8
        for k, v in display_partitions.items():
            col_widths["Key"] = max(col_widths["Key"], len(k))
            for dk in sorted_keys:
                col_widths[dk] = max(col_widths[dk], len(str(v.get(dk, ""))))

        # Create formatted header - add "Default" at the beginning
        header = (
            f"{'Default'.ljust(col_widths['Default'])} | {'Key'.ljust(col_widths['Key'])} | "
            + " | ".join([dk.ljust(col_widths[dk]) for dk in sorted_keys])
        )

        # Create formatted rows as choices
        choices = []
        for k, v in display_partitions.items():
            is_default = "*" if k == default_key else " "
            row_str = (
                f"{is_default.ljust(col_widths['Default'])} | {k.ljust(col_widths['Key'])} | "
                + " | ".join(
                    [str(v.get(dk, "")).ljust(col_widths[dk]) for dk in sorted_keys]
                )
            )
            choices.append({"name": row_str, "value": k})

        return header, choices

    def get_default_partition(self, host):
        """Return the default partition for the host if it exists."""
        if host not in self.directive:
            return None

        host_partitions = self.directive.get(host, {})

        # 1. Check for host-specific default
        if "default" in host_partitions:
            # Return the actual partition name pointed to by 'default'
            return host_partitions["default"].get("partition")

        # 2. Check for global default (handling the 'dafault' typo in YAML)
        global_default = self.ai_config.get("dafault", {}).get("partition")
        if global_default:
            # Return only the short key (e.g., 'a100-dgx' from 'cloudmesh.ai.partition.uva.a100-dgx')
            return global_default.split(".")[-1]

        # 3. Fallback to the first available partition for the host
        # Filter out 'default' key if it exists
        keys = [k for k in host_partitions.keys() if k != "default"]
        return next(iter(keys)) if keys else None

    def get_login_command(self, host, key, sbatch_params=None):
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

    def login(self, host, key, sbatch_params=None):
        """SSH on UVA by executing an interactive job command."""
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
            os.system(command)
        return ""

    def create_apptainer_image(self, name):
        """Create an apptainer image on UVA."""
        try:
            cache = os.environ.get("APPTAINER_CACHEDIR", "/scratch/$USER/.apptainer/")
            console.banner("Cloudmesh UVA Apptainer Build")

            image = os.path.basename(name.replace(".def", ".sif"))
            logger.debug(f"Building image {image} from {name}")

            console.print(f"Image name       : {image}")
            console.print(f"Singularity cache: {cache}")
            console.print(f"Definition       : {name}")
            console.print()
            StopWatch.start("build image")
            os.system(f"apptainer build {image} {name}")
            StopWatch.stop("build image")

            # Use Shell.run to get size
            size_output = Shell.run(f"du -sh {image}")
            size = size_output.split()[0] if size_output else "unknown"
            timer = StopWatch.get("build image")
            console.print()
            console.print(f"Time to build {image}s ({size}) {timer}s")
            console.print()

        except Exception as e:
            console.error(e)

    def jupyter(self, port=8000):
        """Start a Jupyter notebook on UVA."""
        console.print(f"Starting Jupyter on port {port}...")
        console.print("Note: This requires an active VPN connection.")
        console.print(f"Command: jupyter notebook --no-browser --port={port}")
        console.print(f"Tunnel: ssh -L 8080:localhost:{port} uva")

    def cancel(self, job_id):
        """Cancel a Slurm job."""
        command = f"ssh {self.host} 'scancel {job_id}'"
        console.msg(f"Canceling job {job_id}...")
        if not self.debug:
            os.system(command)
        return ""

    def storage(self, directory):
        """Get storage information for a directory."""
        command = f"ssh {self.host} 'du -sh {directory}'"
        if self.debug:
            console.msg(f"Debug: {command}")
            return f"Storage info for {directory}: Not executed (debug)"

        result = Shell.run(command)
        return result

    def edit(self, filename, editor="emacs"):
        """Edit a file on the remote host."""
        command = f"ssh -t {self.host} '{editor} {filename}'"
        console.msg(f"Editing {filename} with {editor}...")
        if not self.debug:
            os.system(command)
        return ""
