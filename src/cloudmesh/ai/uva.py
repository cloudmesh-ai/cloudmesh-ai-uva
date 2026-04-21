import os
import yaml
import sys
from cloudmesh.common.console import Console
from cloudmesh.common.util import banner
from cloudmesh.common.StopWatch import StopWatch
from cloudmesh.common.Shell import Shell

class Uva:
    def __init__(self, host="uva", debug=False):
        """
        Initialize the Uva class.
        """
        self.debug = debug
        self.host = host
        
        try:
            # Load partitions from the file relative to this module
            path = os.path.join(os.path.dirname(__file__), 'partitions.yaml')
            with open(path, 'r') as f:
                self.directive = yaml.safe_load(f)
        except Exception as e:
            Console.error(f"Failed to load partitions.yaml: {e}")
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
            Console.error(f"In directive searching for:\n  host {host}\n  key {key}\nNot found")
            sys.exit(1)
        
        block = ""
        for k, v in directives.items():
            block += f"#SBATCH --{k}={v}\n"
        return block

    def login(self, host, key, sbatch_params=None):
        """SSH on UVA by executing an interactive job command."""
        host = host or self.host
        
        if not key:
            available_keys = list(self.directive.get(host, {}).keys())
            Console.error(f"No key provided for host {host}. Available keys: {', '.join(available_keys)}")
            return

        # Start with base directives from the config
        try:
            directives = self.directive[host][key].copy()
        except KeyError:
            available_keys = list(self.directive.get(host, {}).keys())
            Console.error(f"Key {key} not found for host {host}. Available keys: {', '.join(available_keys)}")
            return

        # Override with sbatch parameters if provided
        if sbatch_params:
            directives.update(sbatch_params)

        parameters = "".join([f" --{k}={v}" for k, v in directives.items()])
        command = f'ssh -tt {host} "/opt/rci/bin/ijob{parameters}"'

        Console.msg(command)
        if not self.debug:
            os.system(command)
        return ""

    def create_apptainer_image(self, name):
        """Create an apptainer image on UVA."""
        try:
            cache = os.environ.get("APPTAINER_CACHEDIR", "/scratch/$USER/.apptainer/")
            banner("Cloudmesh UVA Apptainer Build")

            image = os.path.basename(name.replace(".def", ".sif"))

            print("Image name       :", image)
            print("Singularity cache:", cache)
            print("Definition       :", name)
            print()
            StopWatch.start("build image")
            os.system(f"apptainer build {image} {name}")
            StopWatch.stop("build image")
            
            # Use Shell.run to get size
            size_output = Shell.run(f"du -sh {image}")
            size = size_output.split()[0] if size_output else "unknown"
            timer = StopWatch.get("build image")
            print()
            print(f"Time to build {image}s ({size}) {timer}s")
            print()

        except Exception as e:
            Console.error(e, traceflag=True)

    def jupyter(self, port=8000):
        """Start a Jupyter notebook on UVA."""
        print(f"Starting Jupyter on port {port}...")
        print("Note: This requires an active VPN connection.")
        print(f"Command: jupyter notebook --no-browser --port={port}")
        print(f"Tunnel: ssh -L 8080:localhost:{port} uva")

    def cancel(self, job_id):
        """Cancel a Slurm job."""
        command = f"ssh {self.host} 'scancel {job_id}'"
        Console.msg(f"Canceling job {job_id}...")
        if not self.debug:
            os.system(command)
        return ""

    def storage(self, directory):
        """Get storage information for a directory."""
        command = f"ssh {self.host} 'du -sh {directory}'"
        if self.debug:
            Console.msg(f"Debug: {command}")
            return f"Storage info for {directory}: Not executed (debug)"
        
        result = Shell.run(command)
        return result

    def edit(self, filename, editor="emacs"):
        """Edit a file on the remote host."""
        command = f"ssh -t {self.host} '{editor} {filename}'"
        Console.msg(f"Editing {filename} with {editor}...")
        if not self.debug:
            os.system(command)
        return ""
