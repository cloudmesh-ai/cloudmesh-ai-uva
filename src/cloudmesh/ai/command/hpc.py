import click
import webbrowser
import csv
import os
import re
import questionary
from typing import Optional, Any
from cloudmesh.ai.common.io import console
from cloudmesh.ai.vpn.vpn import Vpn
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Footer
from cloudmesh.ai.hpc import Hpc

@click.group()
def hpc_group():
    """
    HPC tool for Cloudmesh AI.
    This command simplifies access to HPC resources.
    """
    pass

# --- Storage Group ---
@hpc_group.group(name="storage")
def storage_group():
    """Storage related commands."""
    pass

@storage_group.command(name="info")
@click.argument("directory")
@click.option("--info", is_flag=True, help="Detailed information")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def storage_info(directory: str, info: bool, debug: bool) -> None:
    """Obtains information about the storage associated with a directory on HPC."""
    hpc = Hpc(debug=debug)
    result = hpc.storage(directory)
    console.print(result)

# --- VPN Group ---
@hpc_group.group(name="vpn")
def vpn_group():
    """VPN related commands."""
    pass

@vpn_group.command(name="on")
def vpn_on() -> None:
    """Switches the VPN on."""
    vpn = Vpn(service="hpc")
    vpn.connect()

@vpn_group.command(name="off")
def vpn_off() -> None:
    """Switches the VPN off."""
    vpn = Vpn(service="hpc")
    vpn.disconnect()

@vpn_group.command(name="info")
def vpn_info() -> None:
    """Prints information about the current connection to the internet."""
    vpn = Vpn(service="hpc")
    vpn.info()

@vpn_group.command(name="status")
def vpn_status() -> None:
    """Prints True if VPN is enabled, False if not."""
    vpn = Vpn(service="hpc")
    enabled = vpn.enabled()
    console.print(f"VPN Enabled: {enabled}")

# --- Slurm Group ---
@hpc_group.group(name="slurm")
def slurm_group():
    """Slurm related commands."""
    pass

@slurm_group.command(name="info")
@click.argument("key", required=False)
def slurm_info(key: Optional[str]) -> None:
    """Prints Slurm directive information for a partition key."""
    hpc = Hpc()
    if not key:
        console.error("Please provide a partition key.")
        return
    directives = hpc.create_slurm_directives(hpc.host, key)
    console.print(directives)

@slurm_group.command(name="job-info")
@click.argument("job_id")
def slurm_job_info(job_id: str) -> None:
    """Get detailed information about a Slurm job."""
    hpc = Hpc()
    result = hpc.job_info(job_id)
    console.print(result)

@slurm_group.command(name="submit")
@click.argument("script")
@click.option("--key", help="Partition key")
@click.option("--sbatch", help="Additional sbatch parameters (key:val,key:val)")
def slurm_submit(script: str, key: Optional[str], sbatch: Optional[str]) -> None:
    """Upload a script and submit it as a Slurm job."""
    hpc = Hpc()
    try:
        sbatch_params = hpc.parse_sbatch_parameter(sbatch) if sbatch else None
        result = hpc.submit(script, key=key, sbatch_params=sbatch_params)
        console.print(result)
    except Exception as e:
        console.error(e)

@slurm_group.command(name="logs")
@click.argument("job_id")
@click.option("--tail", is_flag=True, help="Tail the log file")
def slurm_logs(job_id: str, tail: bool) -> None:
    """Read the Slurm output logs for a job."""
    hpc = Hpc()
    result = hpc.logs(job_id, tail=tail)
    console.print(result)

@slurm_group.command(name="quota")
def slurm_quota() -> None:
    """Check disk quota on the HPC."""
    hpc = Hpc()
    result = hpc.quota()
    console.print(result)

@slurm_group.command(name="nodes")
@click.option("--partition", help="Partition to check")
def slurm_nodes(partition: Optional[str]) -> None:
    """Check node status for a partition."""
    hpc = Hpc()
    result = hpc.nodes(partition=partition)
    console.print(result)

@slurm_group.command(name="wait")
@click.argument("job_id")
@click.option("--interval", default=30, help="Polling interval in seconds")
def slurm_wait(job_id: str, interval: int) -> None:
    """Wait for a Slurm job to complete."""
    hpc = Hpc()
    hpc.wait(job_id, interval=interval)

@slurm_group.command(name="template")
@click.option("--key", help="Partition key for the template")
def slurm_template(key: Optional[str]) -> None:
    """Generate a boilerplate .sbatch script."""
    hpc = Hpc()
    result = hpc.template(key=key)
    console.print(result)

@slurm_group.command(name="run")
@click.option("--sbatch", help="Sbatch parameter")
@click.option("--host", default="hpc", help="Host to use")
@click.argument("key", required=False)
@click.option("--debug", is_flag=True, help="Enable debug mode")
def slurm_run(sbatch: Optional[str], host: str, key: Optional[str], debug: bool) -> None:
    """Runs a Slurm command."""
    hpc = Hpc(host=host, debug=debug)
    try:
        sbatch_params = hpc.parse_sbatch_parameter(sbatch) if sbatch else None
    except ValueError as e:
        console.error(str(e))
        return
    hpc.login(host, key, sbatch_params=sbatch_params)

@slurm_group.command(name="cancel")
@click.argument("job_id")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def slurm_cancel(job_id: str, debug: bool) -> None:
    """Cancels a Slurm job."""
    hpc = Hpc(debug=debug)
    hpc.cancel(job_id)

@slurm_group.command(name="status")
@click.argument("job_id")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def slurm_status(job_id: str, debug: bool) -> None:
    """Gets the status of a specific Slurm job."""
    hpc = Hpc(debug=debug)
    result = hpc.get_job_status(job_id)
    console.print(result)

@slurm_group.command(name="list")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def slurm_list(debug: bool) -> None:
    """Lists all active Slurm jobs for the current user."""
    hpc = Hpc(debug=debug)
    result = hpc.list_jobs()
    console.print(result)

# --- Image Group ---
@hpc_group.group(name="image")
def image_group():
    """Image related commands."""
    pass

@image_group.command(name="build")
@click.argument("deffile")
def image_build(deffile: str) -> None:
    """Builds an image from a definition file."""
    hpc = Hpc()
    hpc.create_apptainer_image(deffile)

# --- Other Commands ---
class PartitionSelectorApp(App):
    """A Textual app to select an HPC partition from a table."""
    CSS = """
    Screen {
        background: #f0f0f0;
        color: #333333;
    }
    DataTable {
        background: #ffffff;
        color: #333333;
    }
    DataTable > .dp-row {
        color: #333333;
    }
    DataTable > .dp-row:focus {
        background: #e0e0e0;
        color: #000000;
    }
    Footer {
        background: #dddddd;
        color: #333333;
    }
    """
    BINDINGS = [
        ("q", "quit", "Quit"), 
        ("enter", "select", "Select"),
        ("d", "select_default", "Default")
    ]

    def __init__(self, host, hpc_instance):
        super().__init__()
        self.host = host
        self.hpc = hpc_instance
        self.selected_key = None
        self.default_key = self.hpc.get_default_partition(host)

    def compose(self) -> ComposeResult:
        yield DataTable()
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        
        # Get data from Hpc instance
        header, choices = self.hpc.get_partition_table_data(self.host)
        if not header or not choices:
            self.exit(None)
            return

        # Setup columns
        columns = header.split(" | ")
        table.add_columns(*columns)

        # Populate rows
        for choice in choices:
            # The 'name' in choices is already a formatted string "Default | Key | val1 | val2..."
            # We split it back to get the individual cells
            row_data = choice["name"].split(" | ")
            table.add_row(*row_data)

    def on_data_table_row_selected(self, event) -> None:
        # Get the key from the second column of the selected row (index 1)
        table = self.query_one(DataTable)
        row_key = table.get_row(event.row_key)[1].strip()
        self.selected_key = row_key
        self.exit(self.selected_key)

    def action_select(self) -> None:
        table = self.query_one(DataTable)
        cursor_row = table.cursor_row
        if cursor_row is not None:
            # Get the key from the second column (index 1)
            row_key = table.get_row(cursor_row)[1].strip()
            self.selected_key = row_key
            self.exit(self.selected_key)

    def action_select_default(self) -> None:
        """Select the default partition."""
        if not self.default_key:
            return

        table = self.query_one(DataTable)
        for row_key in table.rows:
            row_data = table.get_row(row_key)
            # Key is in the second column (index 1)
            val = row_data[1].strip()
            if val == self.default_key:
                self.selected_key = self.default_key
                self.exit(self.selected_key)
                break

@hpc_group.command(name="login")
@click.option("--sbatch", help="Sbatch parameter")
@click.option("--host", default="hpc", help="Host to use")
@click.argument("key", required=False)
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.option("--ui", is_flag=True, help="Use interactive UI to select partition")
def login_cmd(sbatch: Optional[str], host: str, key: Optional[str], debug: bool, ui: bool) -> None:
    """Logs into an interactive node on HPC."""
    # Resolve host: if it's the default "hpc", use the Hpc class default (e.g., "uva")
    actual_host = host
    if host == "hpc":
        hpc_temp = Hpc()
        actual_host = hpc_temp.host
    
    hpc = Hpc(host=actual_host, debug=debug)
    
    if ui:
        try:
            # Use Textual app for partition selection
            app = PartitionSelectorApp(actual_host, hpc)
            selected_key = app.run()

            if not selected_key:
                console.warning("No partition selected. Exiting.")
                return

            # Construct the command that will be executed
            cmd_parts = ["cmc hpc login"]
            if host != "hpc":
                cmd_parts.append(f"--host {host}")
            if sbatch:
                cmd_parts.append(f'--sbatch "{sbatch}"')
            cmd_parts.append(selected_key)
            full_cmd = " ".join(cmd_parts)

            # Get the actual ijob command that will be run
            sbatch_params = hpc.parse_sbatch_parameter(sbatch) if sbatch else None
            ijob_cmd = hpc.get_login_command(host, selected_key, sbatch_params)

            # Present the command in a banner
            banner_content = f"# {full_cmd}\n{ijob_cmd}"
            console.banner("Interactive Job", banner_content)

            # Confirmation Step using questionary
            confirmed = questionary.confirm(
                f"Do you want to start the login process?",
                default=True
            ).ask()

            if not confirmed:
                console.msg("Login cancelled by user.")
                return

            key = selected_key

        except KeyboardInterrupt:
            console.msg("\nLogin cancelled by user (Ctrl+C).")
            return

    try:
        sbatch_params = hpc.parse_sbatch_parameter(sbatch) if sbatch else None
    except ValueError as e:
        console.error(str(e))
        return
    hpc.login(host, key, sbatch_params=sbatch_params)

@hpc_group.command(name="tutorial")
@click.argument("keyword", required=False)
def tutorial_cmd(keyword: Optional[str]) -> None:
    """Shows HPC tutorials based on keyword."""
    hpc = Hpc()
    url = hpc.get_tutorial_url(keyword)
    console.msg(f"Opening tutorial for {keyword or 'general'}: {url}")
    webbrowser.open(url)

@hpc_group.command(name="ticket")
def ticket_cmd() -> None:
    """Opens the support request form."""
    url = "https://www.rc.virginia.edu/form/support-request/"
    console.msg(f"Opening support ticket form: {url}")
    webbrowser.open(url)

@hpc_group.command(name="jupyter")
@click.option("--port", default=8000, help="Port for Jupyter")
def jupyter_cmd(port: int) -> None:
    """Starts a Jupyter notebook."""
    hpc = Hpc()
    hpc.jupyter(port)

@hpc_group.command(name="edit")
@click.argument("filename")
@click.option("--editor", default="emacs", help="Editor to use")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def edit_cmd(filename: str, editor: str, debug: bool) -> None:
    """Edits a file on HPC."""
    hpc = Hpc(debug=debug)
    hpc.edit(filename, editor)

@hpc_group.command(name="set-default")
@click.option("--host", required=True, help="Default host to use")
@click.option("--partition", help="Default partition key to use")
def set_default_cmd(host: str, partition: Optional[str]) -> None:
    """Set the default host and partition for future commands."""
    hpc = Hpc()
    hpc.set_default(host, partition)

@hpc_group.command(name="config")
def config_cmd() -> None:
    """Prints the hardware and queue configuration for HPC."""
    
    hpc = Hpc()
    config_path = hpc.get_config_path()
    
    if not os.path.exists(config_path):
        console.error(f"Configuration file not found: {config_path}")
        return

    with open(config_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    sections = {}
    current_section = None
    for line in lines:
        if line.startswith('[') and line.endswith(']'):
            current_section = line[1:-1]
            sections[current_section] = []
        elif current_section:
            sections[current_section].append(line)

    def print_table(title, header, data, link):
        # Use the simplified console.table for the main display
        console.table(header, data, title=title)
        console.print(f"[link={link}]Source: {link}[/link]\n")

    if "Hardware" in sections:
        hw_lines = sections["Hardware"]
        if hw_lines:
            header = []
            for h in hw_lines[0].split(','):
                # Split by slash
                h = re.sub(r'\s*/\s*', '\n/', h)
                # Specifically split "Specialty Hardware"
                if h == "Specialty Hardware":
                    h = "Specialty\nHardware"
                header.append(h)
            data = [line.split(',') for line in hw_lines[1:]]
            console.banner("HPC Hardware Configuration", "Detailed hardware specifications for the HPC cluster.")
            print_table("Hardware Configuration", header, data, "https://www.rc.virginia.edu/userinfo/hpc/#hardware-configuration")

    if "Queues" in sections:
        q_lines = sections["Queues"]
        if q_lines:
            header = [re.sub(r'\s*/\s*', '\n/', h) for h in q_lines[0].split(',')]
            data = [line.split(',') for line in q_lines[1:]]
            console.banner("HPC Queue Configuration", "Available Slurm queues and their constraints.")
            print_table("Queues", header, data, "https://www.rc.virginia.edu/userinfo/hpc/#job-queues")

@hpc_group.command(name="info")
@click.argument("key", required=False)
def info_cmd(key: Optional[str]) -> None:
    """Prints information about the current HPC configuration or a specific partition."""
    hpc = Hpc()
    
    # 1. If no key provided, show default host info
    if not key:
        host = hpc.host
        default_partition = hpc.get_default_partition(host)
        available_hosts = list(hpc.directive.keys())
        console.print("\n[bold]HPC Configuration Info[/bold]")
        console.print(f"Current Host      : {host}")
        console.print(f"Default Partition : {default_partition or 'Not set'}")
        console.print(f"Available Hosts   : {', '.join(available_hosts)}")
        
        header, data = hpc.get_partition_data(host)
        if header and data:
            console.table(header, data, title="Partitions")
        console.print()
        return

    # 2. Check if the key is a top-level host
    if key in hpc.directive:
        host = key
        default_partition = hpc.get_default_partition(host)
        available_hosts = list(hpc.directive.keys())
        console.print("\n[bold]HPC Host Info[/bold]")
        console.print(f"Host              : {host}")
        console.print(f"Default Partition : {default_partition or 'Not set'}")
        console.print(f"Available Hosts   : {', '.join(available_hosts)}")
        
        header, data = hpc.get_partition_data(host)
        if header and data:
            console.table(header, data, title="Partitions")
        console.print()
        return

    # 3. Check if the key is a partition key for any host
    for host, partitions in hpc.directive.items():
        if key in partitions:
            directives = partitions[key]
            console.print("\n[bold]HPC Partition Info[/bold]")
            console.print(f"Host       : {host}")
            console.print(f"Partition  : {key}")
            for k, v in directives.items():
                console.print(f"{k.ljust(12)} : {v}")
            console.print()
            return

    # 4. Not found
    console.error(f"Key '{key}' not found as a host or partition key.")
    # Fallback to default info
    host = hpc.host
    console.print(f"\nDefault Host: {host}")

def register(cli: Any) -> None:
    cli.add_command(hpc_group, name="hpc")
