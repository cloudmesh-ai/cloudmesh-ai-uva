import click
import webbrowser
import csv
import os
import re
from rich.console import Console
from rich.table import Table
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
    click.echo(result)

# --- VPN Group ---
@uva_group.group(name="vpn")
def vpn_group():
    """VPN related commands."""
    pass

@vpn_group.command(name="on")
def vpn_on():
    """Switches the VPN on."""
    click.echo("Connecting to VPN... Not implemented")

@vpn_group.command(name="off")
def vpn_off():
    """Switches the VPN off."""
    click.echo("Disconnecting from VPN... Not implemented")

@vpn_group.command(name="info")
def vpn_info():
    """Prints information about the current connection to the internet."""
    click.echo("VPN Info: Not implemented")

@vpn_group.command(name="status")
def vpn_status():
    """Prints True if VPN is enabled, False if not."""
    click.echo("VPN Status: False (Not implemented)")

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
    click.echo(directives)

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
@uva_group.command(name="login")
@click.option("--sbatch", help="Sbatch parameter")
@click.option("--host", default="uva", help="Host to use")
@click.argument("key", required=False)
@click.option("--debug", is_flag=True, help="Enable debug mode")
def login_cmd(sbatch, host, key, debug):
    """Logs into an interactive node on UVA."""
    uva = Uva(host=host, debug=debug)
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
    click.echo(f"Opening tutorial for {keyword or 'general'}: {url}")
    webbrowser.open(url)

@uva_group.command(name="ticket")
def ticket_cmd():
    """Opens the support request form."""
    url = "https://www.rc.virginia.edu/form/support-request/"
    click.echo(f"Opening support ticket form: {url}")
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
        click.echo(f"Configuration file not found: {config_path}")
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
        console = Console()
        table = Table(title=title)
        
        # Process data for decimal alignment
        formatted_data = [row[:] for row in data]
        
        for i in range(len(header)):
            # Check if this column is numeric
            is_numeric = False
            if data and i < len(data[0]) and data[0][i]:
                if data[0][i][0].isdigit() or data[0][i].startswith('-'):
                    is_numeric = True
            
            if is_numeric:
                # Check if it's a float column and find max precision
                max_precision = -1
                for row in data:
                    if i < len(row) and row[i]:
                        try:
                            val = float(row[i])
                            if '.' in row[i]:
                                precision = len(row[i].split('.')[1])
                                max_precision = max(max_precision, precision)
                        except ValueError:
                            pass
                
                # Format float values to max_precision
                if max_precision != -1:
                    for row in formatted_data:
                        if i < len(row) and row[i]:
                            try:
                                val = float(row[i])
                                row[i] = f"{val:.{max_precision}f}"
                            except ValueError:
                                pass

            # Set alignment
            justify = "right" if is_numeric else "left"
            no_wrap = is_numeric
            table.add_column(header[i], justify=justify, no_wrap=no_wrap)
        
        for row in formatted_data:
            table.add_row(*row)
        
        console.print(table)
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
            print_table("Hardware Configuration", header, data, "https://www.rc.virginia.edu/userinfo/hpc/#hardware-configuration")

    if "Queues" in sections:
        q_lines = sections["Queues"]
        if q_lines:
            header = [re.sub(r'\s*/\s*', '\n/', h) for h in q_lines[0].split(',')]
            data = [line.split(',') for line in q_lines[1:]]
            print_table("Queues", header, data, "https://www.rc.virginia.edu/userinfo/hpc/#job-queues")

@uva_group.command(name="info")
def info_cmd():
    """Print hello world."""
    click.echo("hello world")

def register(cli):
    cli.add_command(uva_group, name="uva")