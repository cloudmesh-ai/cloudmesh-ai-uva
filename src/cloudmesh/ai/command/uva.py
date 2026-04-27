import click
import webbrowser
import csv
import os
import re
import questionary
from cloudmesh.ai.common.io import console
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Footer
from cloudmesh.ai.uva import Uva

@click.group()
def uva_group():
    """
    UVA tool for Cloudmesh AI.
    This command simplifies access to UVA resources.
    """
    pass

# --- Storage Group ---
@uva_group.group(name="storage")
def storage_group():
    """Storage related commands."""
    pass

@storage_group.command(name="info")
@click.argument("directory")
@click.option("--info", is_flag=True, help="Detailed information")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def storage_info(directory, info, debug):
    """Obtains information about the storage associated with a directory on UVA."""
    uva = Uva(debug=debug)
    result = uva.storage(directory)
    console.print(result)

# --- VPN Group ---
@uva_group.group(name="vpn")
def vpn_group():
    """VPN related commands."""
    pass

@vpn_group.command(name="on")
def vpn_on():
    """Switches the VPN on."""
    console.warning("Connecting to VPN... Not implemented")

@vpn_group.command(name="off")
def vpn_off():
    """Switches the VPN off."""
    console.warning("Disconnecting from VPN... Not implemented")

@vpn_group.command(name="info")
def vpn_info():
    """Prints information about the current connection to the internet."""
    console.warning("VPN Info: Not implemented")

@vpn_group.command(name="status")
def vpn_status():
    """Prints True if VPN is enabled, False if not."""
    console.warning("VPN Status: False (Not implemented)")

# --- Slurm Group ---
@uva_group.group(name="slurm")
def slurm_group():
    """Slurm related commands."""
    pass

@slurm_group.command(name="info")
@click.option("--host", default="uva", help="Host to use")
@click.argument("key")
def slurm_info(host, key):
    """Prints Slurm directive information."""
    uva = Uva()
    directives = uva.create_slurm_directives(host, key)
    console.print(directives)

@slurm_group.command(name="run")
@click.option("--sbatch", help="Sbatch parameter")
@click.option("--host", default="uva", help="Host to use")
@click.argument("key", required=False)
@click.option("--debug", is_flag=True, help="Enable debug mode")
def slurm_run(sbatch, host, key, debug):
    """Runs a Slurm command."""
    uva = Uva(host=host, debug=debug)
    sbatch_params = uva.parse_sbatch_parameter(sbatch) if sbatch else None
    uva.login(host, key, sbatch_params=sbatch_params)

@slurm_group.command(name="cancel")
@click.argument("job_id")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def slurm_cancel(job_id, debug):
    """Cancels a Slurm job."""
    uva = Uva(debug=debug)
    uva.cancel(job_id)

# --- Image Group ---
@uva_group.group(name="image")
def image_group():
    """Image related commands."""
    pass

@image_group.command(name="build")
@click.argument("deffile")
def image_build(deffile):
    """Builds an image from a definition file."""
    uva = Uva()
    uva.create_apptainer_image(deffile)

# --- Other Commands ---
class PartitionSelectorApp(App):
    """A Textual app to select a UVA partition from a table."""
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

    def __init__(self, host, uva_instance):
        super().__init__()
        self.host = host
        self.uva = uva_instance
        self.selected_key = None
        self.default_key = self.uva.get_default_partition(host)

    def compose(self) -> ComposeResult:
        yield DataTable()
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        
        # Get data from Uva instance
        header, choices = self.uva.get_partition_table_data(self.host)
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

@uva_group.command(name="login")
@click.option("--sbatch", help="Sbatch parameter")
@click.option("--host", default="uva", help="Host to use")
@click.argument("key", required=False)
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.option("--ui", is_flag=True, help="Use interactive UI to select partition")
def login_cmd(sbatch, host, key, debug, ui):
    """Logs into an interactive node on UVA."""
    uva = Uva(host=host, debug=debug)
    
    if ui:
        try:
            # Use Textual app for partition selection
            app = PartitionSelectorApp(host, uva)
            selected_key = app.run()

            if not selected_key:
                console.warning("No partition selected. Exiting.")
                return

            # Construct the command that will be executed
            cmd_parts = ["cmc uva login"]
            if host != "uva":
                cmd_parts.append(f"--host {host}")
            if sbatch:
                cmd_parts.append(f'--sbatch "{sbatch}"')
            cmd_parts.append(selected_key)
            full_cmd = " ".join(cmd_parts)

            # Get the actual ijob command that will be run
            sbatch_params = uva.parse_sbatch_parameter(sbatch) if sbatch else None
            ijob_cmd = uva.get_login_command(host, selected_key, sbatch_params)

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

    sbatch_params = uva.parse_sbatch_parameter(sbatch) if sbatch else None
    uva.login(host, key, sbatch_params=sbatch_params)

@uva_group.command(name="tutorial")
@click.argument("keyword", required=False)
def tutorial_cmd(keyword):
    """Shows UVA tutorials based on keyword."""
    urls = {
        "pod": "https://infomall.org/uva/docs/tutorial/rivanna-superpod/",
        "rclone": "https://infomall.org/uva/docs/tutorial/rclone/",
        "globus": "https://infomall.org/uva/docs/tutorial/globus/",
        "apptainer": "https://www.rc.virginia.edu/userinfo/rivanna/software/apptainer/",
        "training": "https://infomall.org/uva/docs/tutorial/cybertraining/",
        "hpc": "https://infomall.org/uva/docs/tutorial/rivanna/",
        "system": "https://infomall.org/uva/docs/tutorial/rivanna/",
    }
    url = urls.get(keyword, "https://infomall.org/uva/docs/tutorial/")
    console.msg(f"Opening tutorial for {keyword or 'general'}: {url}")
    webbrowser.open(url)

@uva_group.command(name="ticket")
def ticket_cmd():
    """Opens the support request form."""
    url = "https://www.rc.virginia.edu/form/support-request/"
    console.msg(f"Opening support ticket form: {url}")
    webbrowser.open(url)

@uva_group.command(name="jupyter")
@click.option("--port", default=8000, help="Port for Jupyter")
def jupyter_cmd(port):
    """Starts a Jupyter notebook."""
    uva = Uva()
    uva.jupyter(port)

@uva_group.command(name="edit")
@click.argument("filename")
@click.option("--editor", default="emacs", help="Editor to use")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def edit_cmd(filename, editor, debug):
    """Edits a file on UVA."""
    uva = Uva(debug=debug)
    uva.edit(filename, editor)

@uva_group.command(name="config")
def config_cmd():
    """Prints the hardware and queue configuration for UVA."""
    
    # Path to config.csv relative to this file
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.csv')
    
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
            console.banner("UVA Hardware Configuration", "Detailed hardware specifications for the UVA cluster.")
            print_table("Hardware Configuration", header, data, "https://www.rc.virginia.edu/userinfo/hpc/#hardware-configuration")

    if "Queues" in sections:
        q_lines = sections["Queues"]
        if q_lines:
            header = [re.sub(r'\s*/\s*', '\n/', h) for h in q_lines[0].split(',')]
            data = [line.split(',') for line in q_lines[1:]]
            console.banner("UVA Queue Configuration", "Available Slurm queues and their constraints.")
            print_table("Queues", header, data, "https://www.rc.virginia.edu/userinfo/hpc/#job-queues")

@uva_group.command(name="info")
def info_cmd():
    """Print hello world."""
    console.print("hello world")

def register(cli):
    cli.add_command(uva_group, name="uva")