import json
import re
import csv
import io
from typing import List, Dict, Optional, Any, Union
from cloudmesh.ai.common.io import console
from cloudmesh.ai.common.ssh.base import SSHBase

class Slurm(SSHBase):
    def __init__(self, host: str = "uva", debug: bool = False) -> None:
        """
        Initialize the Slurm class.
        """
        super().__init__(debug=debug)
        self.host = host
        self.nodes: List[Dict[str, Any]] = []

    def get_summary(self, partition: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch the partition summary (Nodes and CPUs A/I/O/T).
        """
        host = self.host
        cmd = "sinfo"
        if partition:
            cmd = f"sinfo -p {partition}"
        
        result = self._run_remote(host, cmd)
        output = result.stdout
        if not output:
            return {}

        lines = output.strip().split("\n")
        if len(lines) < 2:
            return {}

        # The second line contains the data
        data_line = lines[1].split()
        if len(data_line) < 3:
            return {}

        # data_line[0] is partition name
        # data_line[1] is NODES(A/I/O/T) e.g. "1/0/0/1"
        # data_line[2] is CPUS(A/I/O/T) e.g. "41/55/0/96"
        
        def parse_aiot(s):
            parts = s.strip("()").split("/")
            if len(parts) == 4:
                return {
                    "available": parts[0],
                    "idle": parts[1],
                    "offline": parts[2],
                    "total": parts[3]
                }
            return {}

        nodes = parse_aiot(data_line[1])
        cpus = parse_aiot(data_line[2])

        return {
            "NODES_AVAILABLE": nodes.get("available"),
            "NODES_IDLE": nodes.get("idle"),
            "NODES_OFFLINE": nodes.get("offline"),
            "NODES_TOTAL": nodes.get("total"),
            "CPUS_AVAILABLE": cpus.get("available"),
            "CPUS_IDLE": cpus.get("idle"),
            "CPUS_OFFLINE": cpus.get("offline"),
            "CPUS_TOTAL": cpus.get("total"),
        }

    def refresh(self, partition: Optional[str] = None) -> None:
        """
        Refresh the cached node data by calling sinfo.
        """
        self.nodes = self.sinfo(partition=partition)

    def search(self, regexp: str) -> Dict[str, Any]:
        """
        Search the cached node data for a regular expression:
        
        Args:
            regexp: The regular expression to search for in node values.
            
        Returns:
            A dictionary of matching nodes, keyed by hostname.
        """
        matches = {}
        pattern = re.compile(regexp)
        
        for node in self.nodes:
            # Check if any value in the node dictionary matches the regex
            if any(pattern.search(str(v)) for v in node.values()):
                # Use HOSTNAME or NODE_ADDR as the key
                hostname = node.get("HOSTNAME") or node.get("NODE_ADDR") or "Unknown"
                matches[hostname] = node
                
        return matches

    def sreport(self, entity: str = "user", filter_val: Optional[str] = None, 
                start: Optional[str] = None, end: Optional[str] = None, 
                stat: bool = False) -> List[Dict[str, Any]]:
        """
        Get usage report using sreport for a specific entity.
        
        Args:
            entity: The entity to report on ('user', 'account', 'partition', 'node', 'job').
            filter_val: The value to filter by (e.g., username, account name).
            start: Start date (YYYY-MM-DD).
            end: End date (YYYY-MM-DD).
            stat: If True, use a summary format if available.
            
        Returns:
            A list of dictionaries containing the usage report.
        """
        # Map requested entity to actual Slurm report type and report name
        # Based on 'sreport --help'
        report_mapping = {
            "user": ("user", "TopUsage"),
            "account": ("cluster", "AccountUtilizationByUser"),
            "partition": ("cluster", "Utilization"),
            "node": ("cluster", "Utilization"),
            "job": ("job", "SizesByAccount"),
        }
        
        # Map entity to the filter key used by sreport
        # For 'account', we use 'Users' because AccountUtilizationByUser is filtered by users
        filter_map = {
            "user": "Users",
            "account": "Users",
            "partition": "Partitions",
            "node": "Nodes",
            "job": "Jobs"
        }
        
        if entity not in report_mapping:
            console.error(f"Unsupported sreport entity: {entity}")
            return []
            
        report_type, report_name = report_mapping[entity]
        filter_key = filter_map.get(entity, "Users")
        
        # Base command: sreport -P <report_type> <report_name>
        cmd = f"sreport -P {report_type} {report_name}"
        
        # Add filter if provided
        if filter_val:
            cmd += f" {filter_key}={filter_val}"
        
        # Add time range
        if start:
            cmd += f" Start={start}"
        if end:
            cmd += f" End={end}"
            
        if stat:
            # sreport doesn't have a simple --stat, but we can try to use a different 
            # report type or just mark it for the caller. 
            # For now, we'll keep the command as is but the caller can handle 'stat' logic.
            pass

        console.msg(f"Executing: {cmd}")
        try:
            result = self._run_remote(self.host, cmd)
            output = result.stdout
        except Exception as e:
            console.error(f"Failed to get report for {entity}: {e}")
            return []
        
        if not output:
            return []

        lines = [line.strip() for line in output.strip().split("\n") if line.strip()]
        if len(lines) < 2:
            return []

        # sreport output with -P is pipe-separated.
        # We need to find the header line.
        header_line = ""
        data_start_idx = 0
        
        for i, line in enumerate(lines):
            if "|" in line and any(k in line for k in ["Cluster", "Login", "Account", "Partition", "Node"]):
                header_line = line
                data_start_idx = i + 1
                break
        
        if not header_line:
            return []

        # Split header by pipe
        headers = [h.strip() for h in header_line.split("|")]
        
        results = []
        for line in lines[data_start_idx:]:
            if line.startswith("---") or not line or "|" not in line:
                continue
            
            # Split data by pipe
            values = [v.strip() for v in line.split("|")]
            
            if len(values) >= len(headers):
                row = {headers[i]: values[i] for i in range(len(headers))}
                results.append(row)
        
        return results

    def sinfo(self, partition: Optional[str] = None, json_support: bool = False, format: str = "%all") -> Union[List[Dict[str, Any]], str]:
        """
        Return sinfo output as a JSON object (list of dictionaries).
        
        Args:
            partition: Optional partition to filter by.
            json_support: If True, attempts to use sinfo's native --json flag.
            format: The sinfo format string or a named format. 
                    Named formats: 'summarize', 'long', 'Node', 'long_node', 'list_reasons', 'long_list_reasons'.
                    Defaults to "%all" (which uses "%P %N %G %t").
        """
        host = self.host
        
        if json_support:
            try:
                cmd = "sinfo --json"
                if partition:
                    cmd = f"sinfo -p {partition} --json"
                
                result = self._run_remote(host, cmd)
                if result.stdout:
                    return json.loads(result.stdout)
            except Exception as e:
                console.warn(f"Native sinfo --json failed, falling back to parsing: {e}")

        # Fallback: Parse tabular output
        try:
            named_formats = {
                "summarize": "%#P %.5a %.10l %.16F %N",
                "long": "%#P %.5a %.10l %.10s %.4r %.8h %.10g %.6D %.11T %.11i %N",
                "Node": "%#N %.6D %#P %6t",
                "long_node": "%#N %.6D %#P %.11T %.4c %.8z %.6m %.8d %.6w %.8f %20E",
                "list_reasons": "%20E %9u %19H %N",
                "long_list_reasons": "%20E %12U %19H %6t %N",
            }
            
            if format in ["%all", "all"]:
                cmd = "sinfo -N --format=\"%all\""
                if partition:
                    cmd = f"sinfo -p {partition} -N --format=\"%all\""
            elif format in named_formats:
                fmt = named_formats[format]
                cmd = f"sinfo -N -o \"{fmt}\""
                if partition:
                    cmd = f"sinfo -p {partition} -N -o \"{fmt}\""
            else:
                fmt = format
                cmd = f"sinfo -N -o \"{fmt}\""
                if partition:
                    cmd = f"sinfo -p {partition} -N -o \"{fmt}\""
            
            console.msg(f"Executing: {cmd}")
            result = self._run_remote(host, cmd)
            output = result.stdout
            
            if not output:
                return []

            lines = output.strip().split("\n")
            if not lines:
                return []

            if format in ["%all", "all"]:
                # Parse pipe-separated output with header
                header_line = lines[0]
                headers = [h.strip() for h in header_line.split("|")]
                
                nodes_list = []
                for line in lines[1:]:
                    if not line:
                        continue
                    values = [v.strip() for v in line.split("|")]
                    # Create a dictionary mapping header to value
                    node_data = {}
                    for i in range(min(len(headers), len(values))):
                        node_data[headers[i]] = values[i]
                    nodes_list.append(node_data)
            else:
                nodes_list = []
                for line in lines:
                    if not line:
                        continue
                    nodes_list.append({"raw": line})
            
            # Parse node-specific summary metrics
            def parse_aiot(s):
                if not s:
                    return {}
                parts = s.strip("()").split("/")
                res = {}
                if len(parts) >= 1:
                    res["available"] = parts[0]
                if len(parts) >= 2:
                    res["idle"] = parts[1]
                if len(parts) >= 3:
                    res["offline"] = parts[2]
                if len(parts) >= 4:
                    res["total"] = parts[3]
                return res

            # Reorder and expand summary metrics
            summary = self.get_summary(partition)
            
            # Define the strict order requested by the user
            ORDERED_KEYS = [
                "AVAIL", "ACTIVE_FEATURES", "CPUS", "TMP_DISK", "FREE_MEM",
                "AVAIL_FEATURES", "GROUPS", "OVERSUBSCRIBE", "RESERVATION",
                "TIMELIMIT", "MEMORY", "HOSTNAMES", "NODE_ADDR", "PRIO_TIER",
                "ROOT", "JOB_SIZE", "STATE", "USER", "VERSION", "WEIGHT",
                "S:C:T", "NODES", "NODES(A/I)", "NODES(A/I/O/T)",
                "NODES_AVAILABLE", "NODES_IDLE", "NODES_OFFLINE", "NODES_TOTAL",
                "MAX_CPUS_PER_NODE", "CPUS(A/I/O/T)",
                "CPUS_AVAILABLE", "CPUS_IDLE", "CPUS_OFFLINE", "CPUS_TOTAL",
                "GRES", "GRES_SOCKET", "GRES_GPU",
                "TIMESTAMP", "PRIO_JOB_FACTOR", "DEFAULTTIME", "PREEMPT_MODE",
                "REASON", "NODELIST", "CPU_LOAD", "PARTITION", "ALLOCNODES",
                "CLUSTER", "SOCKETS", "CORES", "THREADS"
            ]
            
            new_nodes_list = []
            for node in nodes_list:
                # 1. Pre-calculate all expanded values
                expanded_data = {}
                
                # Parse NODES and CPUS
                for key, value in node.items():
                    if key in ["NODES(A/I/O/T)", "NODES(A/I)"]:
                        parsed = parse_aiot(value)
                        for k, v in parsed.items():
                            expanded_data[f"NODES_{k.upper()}"] = v
                    elif key in ["CPUS(A/I/O/T)", "CPUS(A/I)"]:
                        parsed = parse_aiot(value)
                        for k, v in parsed.items():
                            expanded_data[f"CPUS_{k.upper()}"] = v
                    elif key == "GRES" and value:
                        if "(" in value and ")" in value:
                            gpu_part, socket_part = value.split("(", 1)
                            socket_val = socket_part.replace("S:", "").rstrip(")")
                            expanded_data["GRES_GPU"] = gpu_part
                            expanded_data["GRES_SOCKET"] = socket_val

                # Merge with partition summary
                full_data = node.copy()
                full_data.update(expanded_data)
                for k, v in summary.items():
                    if k not in full_data or full_data[k] is None:
                        full_data[k] = v
                
                # 2. Build reordered dictionary
                reordered_node = {}
                for key in ORDERED_KEYS:
                    if key in full_data:
                        reordered_node[key] = full_data[key]
                
                # 3. Add any remaining attributes at the end
                for key, value in full_data.items():
                    if key not in reordered_node:
                        reordered_node[key] = value
                
                new_nodes_list.append(reordered_node)
            
            nodes_list = new_nodes_list
            
            if format == "csv":
                if not nodes_list:
                    return ""
                
                output = io.StringIO()
                # Use the keys of the first node as the header
                writer = csv.DictWriter(output, fieldnames=nodes_list[0].keys())
                writer.writeheader()
                writer.writerows(nodes_list)
                return output.getvalue()
                
            return nodes_list
        except Exception as e:
            console.error(f"Failed to parse sinfo output: {e}")
            return []

    def scode(self, state: str) -> str:
        """
        Return the description for a Slurm node state code.
        
        Args:
            state: The node state code (e.g., 'idle', 'mi*', 'down').
        """
        # Mapping of 2-letter abbreviations to full state names
        short_codes = {
            "AL": "ALLOCATED",
            "BL": "BLOCKED",
            "CO": "COMPLETING",
            "DO": "DOWN",
            "DR": "DRAINED",
            "FA": "FAIL",
            "FU": "FUTURE",
            "ID": "IDLE",
            "IN": "INVAL",
            "MA": "MAINT",
            "MI": "MIXED",
            "PE": "PERFCTRS",
            "PL": "PLANNED",
            "PO": "POWER_DOWN",
            "RS": "RESERVED",
            "UN": "UNKNOWN",
        }

        # Mapping of full state names to descriptions
        codes = {
            "*": "The node is presently not responding and will not be allocated any new work.",
            "~": "The node is presently in powered off.",
            "#": "The node is presently being powered up or configured.",
            "!": "The node is pending power down.",
            "%": "The node is presently being powered down.",
            "$": "The node is currently in a reservation with a flag value of 'maintenance'.",
            "@": "The node is pending reboot.",
            "^": "The node reboot was issued.",
            "-": "The node is planned by the backfill scheduler for a higher priority job.",
            "ALLOCATED": "The node has been allocated to one or more jobs.",
            "ALLOCATED+": "The node is allocated to one or more active jobs plus one or more jobs are in the process of COMPLETING.",
            "BLOCKED": "The node has been blocked by exclusive topo job.",
            "COMPLETING": "All jobs associated with this node are in the process of COMPLETING.",
            "DOWN": "The node is unavailable for use.",
            "DRAINED": "The node is unavailable for use per system administrator request.",
            "DRAINING": "The node is currently allocated a job, but will not be allocated additional jobs.",
            "FAIL": "The node is expected to fail soon and is unavailable for use per system administrator request.",
            "FAILING": "The node is currently executing a job, but is expected to fail soon and is unavailable for use per system administrator request.",
            "FUTURE": "The node is currently not fully configured, but expected to be available at some point in the indefinite future for use.",
            "IDLE": "The node is not allocated to any jobs and is available for use.",
            "INVAL": "The node did not register correctly with the controller.",
            "MAINT": "The node is currently in a reservation with a flag value of 'maintenance'.",
            "REBOOT_ISSUED": "A reboot request has been sent to the agent configured to handle this request.",
            "REBOOT_REQUESTED": "A request to reboot this node has been made, but hasn't been handled yet.",
            "MIXED": "The node has some of its CPUs ALLOCATED while others are IDLE. Or the node has a suspended job allocated to some of its TRES (e.g. memory).",
            "PERFCTRS": "Network Performance Counters associated with this node are in use, rendering this node as not usable for any other jobs",
            "PLANNED": "The node is planned by the backfill scheduler for a higher priority job.",
            "POWER_DOWN": "The node is pending power down.",
            "POWERED_DOWN": "The node is currently powered down and not capable of running any jobs.",
            "POWERING_DOWN": "The node is in the process of powering down and not capable of running any jobs.",
            "POWERING_UP": "The node is in the process of being powered up.",
            "RESERVED": "The node is in an advanced reservation and not generally available.",
            "UNKNOWN": "The Slurm controller has just started and the node's state has not yet been determined.",
        }

        state_upper = state.upper()
        
        # Handle 2-letter abbreviations (without suffixes)
        if len(state_upper) == 2 and state_upper in short_codes:
            state_upper = short_codes[state_upper]
        
        # Check for exact match first
        if state_upper in codes:
            return codes[state_upper]
        
        # Check for state + suffix (e.g., "IDLE*", "ID*")
        for code, desc in codes.items():
            if len(code) == 1 and state_upper.endswith(code):
                # Extract base state
                base_state = state_upper[:-1]
                
                # If base state is 2 letters, resolve it
                if len(base_state) == 2 and base_state in short_codes:
                    base_state = short_codes[base_state]
                
                base_desc = codes.get(base_state, "Unknown state")
                return f"{base_desc} Suffix {code}: {desc}"
        
        return "Unknown node state code."