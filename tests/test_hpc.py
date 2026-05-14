import unittest
from unittest.mock import patch, MagicMock
import os
from cloudmesh.ai.hpc import Hpc

class TestHpc(unittest.TestCase):
    def setUp(self):
        # Mock load_yaml to provide a consistent base configuration
        self.mock_base_config = {
            "cloudmesh": {
                "ai": {
                    "default": {"partition": "cloudmesh.ai.partition.uva.a100-dgx"},
                    "partition": {
                        "uva": {
                            "default": {"partition": "a100-dgx"},
                            "a100-dgx": {"partition": "a100", "account": "ai"},
                            "cpu": {"partition": "cpu", "account": "ai"}
                        }
                    }
                }
            }
        }
        self.patcher_load_yaml = patch("cloudmesh.ai.hpc.load_yaml", return_value=self.mock_base_config)
        self.mock_load_yaml = self.patcher_load_yaml.start()
        
        # Mock os.path.exists to avoid looking for real local config by default
        self.patcher_exists = patch("os.path.exists", return_value=False)
        self.mock_exists = self.patcher_exists.start()

        # Mock Shell.run to avoid actual SSH calls
        self.patcher_shell = patch("cloudmesh.ai.hpc.Shell.run")
        self.mock_shell = self.patcher_shell.start()

    def tearDown(self):
        self.patcher_load_yaml.stop()
        self.patcher_exists.stop()
        self.patcher_shell.stop()

    def test_parse_sbatch_parameter_valid(self):
        hpc = Hpc()
        params = "nodes:1,cpus-per-task:4"
        expected = {"nodes": "1", "cpus-per-task": "4"}
        self.assertEqual(hpc.parse_sbatch_parameter(params), expected)

    def test_parse_sbatch_parameter_invalid_format(self):
        hpc = Hpc()
        with self.assertRaisesRegex(ValueError, "Invalid sbatch parameter format"):
            hpc.parse_sbatch_parameter("nodes1")

    def test_parse_sbatch_parameter_empty_values(self):
        hpc = Hpc()
        with self.assertRaisesRegex(ValueError, "Both key and value must be provided"):
            hpc.parse_sbatch_parameter("nodes:")

    def test_create_slurm_directives_valid(self):
        hpc = Hpc()
        directives = hpc.create_slurm_directives(host="uva", key="a100-dgx")
        self.assertIn("#SBATCH --partition=a100", directives)
        self.assertIn("#SBATCH --account=ai", directives)

    def test_create_slurm_directives_invalid(self):
        hpc = Hpc()
        with self.assertRaises(SystemExit):
            hpc.create_slurm_directives(host="uva", key="nonexistent")

    def test_get_default_partition_host_specific(self):
        hpc = Hpc()
        # uva has a 'default' key pointing to 'a100-dgx'
        self.assertEqual(hpc.get_default_partition("uva"), "a100-dgx")

    def test_get_default_partition_global(self):
        # Remove host-specific default to test global fallback
        self.mock_base_config["cloudmesh"]["ai"]["partition"]["uva"]["default"] = {}
        hpc = Hpc()
        self.assertEqual(hpc.get_default_partition("uva"), "a100-dgx")

    def test_get_login_command(self):
        hpc = Hpc()
        cmd = hpc.get_login_command(host="uva", key="a100-dgx")
        self.assertIn('ssh -tt uva "/opt/rci/bin/ijob --partition=a100 --account=ai"', cmd)

    def test_get_login_command_with_sbatch(self):
        hpc = Hpc()
        sbatch = {"nodes": "2"}
        cmd = hpc.get_login_command(host="uva", key="a100-dgx", sbatch_params=sbatch)
        self.assertIn("--nodes=2", cmd)

    def test_get_job_status_command(self):
        hpc = Hpc(host="uva")
        hpc.get_job_status("12345")
        self.mock_shell.assert_called_with("ssh uva 'squeue -j 12345'")

    def test_list_jobs_command(self):
        hpc = Hpc(host="uva")
        hpc.list_jobs()
        self.mock_shell.assert_called_with("ssh uva 'squeue -u $USER'")

    def test_local_config_override(self):
        # Mock local config existence and content
        self.mock_exists.side_effect = lambda path: "hpc.yaml" in path
        local_config = {
            "cloudmesh": {
                "ai": {
                    "default": {"partition": "cloudmesh.ai.partition.uva.cpu"},
                    "partition": {
                        "uva": {
                            "default": {"partition": "cpu"},
                            "custom-gpu": {"partition": "gpu-custom", "account": "my-acc"}
                        }
                    }
                }
            }
        }
        # We need to patch load_yaml to return base config first, then local config
        self.mock_load_yaml.side_effect = [self.mock_base_config, local_config]
        
        hpc = Hpc()
        
        # Verify host-specific default override (which takes precedence over global)
        self.assertEqual(hpc.get_default_partition("uva"), "cpu")
        
        # Verify custom partition addition
        directives = hpc.create_slurm_directives(host="uva", key="custom-gpu")
        self.assertIn("#SBATCH --partition=gpu-custom", directives)
        self.assertIn("#SBATCH --account=my-acc", directives)
        
        # Verify base partitions still exist
        self.assertIn("a100-dgx", hpc.directive["uva"])

    def test_parse_sbatch_aliases(self):
        hpc = Hpc()
        hpc.ai_config["aliases"] = {"gpu-heavy": "nodes:2,gres:gpu:a100:2"}
        params = "gpu-heavy,time:24:00:00"
        expected = {"nodes": "2", "gres:gpu:a100": "2", "time": "24:00:00"}
        self.assertEqual(hpc.parse_sbatch_parameter(params), expected)

    def test_submit_job(self):
        hpc = Hpc(host="uva")
        with patch("builtins.open", unittest.mock.mock_open(read_data="echo hello")):
            result = hpc.submit("script.sh", key="a100-dgx")
            self.mock_shell.assert_any_call(unittest.mock.ANY) # Upload
            self.mock_shell.assert_called_with("ssh uva 'sbatch /tmp/job_script.sh'")

    def test_logs_command(self):
        hpc = Hpc(host="uva")
        hpc.logs("12345", tail=False)
        self.mock_shell.assert_called_with("ssh uva 'cat slurm-12345.out'")
        
        hpc.logs("12345", tail=True)
        self.mock_shell.assert_called_with("ssh uva 'tail -f slurm-12345.out'")

    def test_job_info_command(self):
        hpc = Hpc(host="uva")
        hpc.job_info("12345")
        self.mock_shell.assert_called_with("ssh uva 'scontrol show job 12345'")

    def test_quota_command(self):
        hpc = Hpc(host="uva")
        hpc.quota()
        self.mock_shell.assert_called_with("ssh uva 'quota -s'")

    def test_nodes_command(self):
        hpc = Hpc(host="uva")
        hpc.nodes()
        self.mock_shell.assert_called_with("ssh uva 'sinfo'")
        
        hpc.nodes(partition="gpu")
        self.mock_shell.assert_called_with("ssh uva 'sinfo -p gpu'")

    def test_wait_job(self):
        hpc = Hpc(host="uva")
        # Mock get_job_status to return 'R' then 'COMPLETED'
        hpc.get_job_status = unittest.mock.MagicMock(side_effect=["R", "COMPLETED"])
        with patch("time.sleep"): # Don't actually sleep
            result = hpc.wait("12345", interval=1)
            self.assertTrue(result)

    def test_template_generation(self):
        hpc = Hpc(host="uva")
        template = hpc.template(key="a100-dgx")
        self.assertIn("#SBATCH --partition=a100", template)
        self.assertIn("#SBATCH --account=ai", template)
        self.assertIn("#!/bin/bash", template)

    def test_sinfo_native_success(self):
        hpc = Hpc(host="uva")
        mock_json = [{"partition": "a100", "node": "node01", "gres": "gpu:1", "state": "idle"}]
        
        with patch("cloudmesh.ai.slurm.Slurm._run_remote") as mock_run:
            mock_run.return_value = MagicMock(stdout=json.dumps(mock_json))
            result = hpc.sinfo(json_support=True)
            self.assertEqual(result, mock_json)
            mock_run.assert_called_with("uva", "sinfo --json")

    def test_sinfo_native_fallback(self):
        hpc = Hpc(host="uva")
        # First call (native json) fails, second call (fallback parsing) succeeds
        tabular_output = "a100 node01 gpu:1 idle"
        expected = [{"partition": "a100", "node": "node01", "gres": "gpu:1", "state": "idle"}]
        
        with patch("cloudmesh.ai.slurm.Slurm._run_remote") as mock_run:
            mock_run.side_effect = [
                Exception("Command not found"), # Native failure
                MagicMock(stdout=tabular_output) # Fallback success
            ]
            result = hpc.sinfo(json_support=True)
            self.assertEqual(result, expected)

    def test_sinfo_parsing_success(self):
        hpc = Hpc(host="uva")
        tabular_output = "a100 node01 gpu:1 idle\ncpu node02 none alloc"
        expected = [
            {"partition": "a100", "node": "node01", "gres": "gpu:1", "state": "idle"},
            {"partition": "cpu", "node": "node02", "gres": "none", "state": "alloc"}
        ]
        
        with patch("cloudmesh.ai.slurm.Slurm._run_remote") as mock_run:
            mock_run.return_value = MagicMock(stdout=tabular_output)
            result = hpc.sinfo(json_support=False)
            self.assertEqual(result, expected)
            mock_run.assert_called_with("uva", "sinfo -N -o \"%P %N %G %t\"")

    def test_sinfo_partition_filter(self):
        hpc = Hpc(host="uva")
        with patch("cloudmesh.ai.slurm.Slurm._run_remote") as mock_run:
            mock_run.return_value = MagicMock(stdout="")
            hpc.sinfo(partition="gpu", json_support=False)
            mock_run.assert_called_with("uva", "sinfo -p gpu -N -o \"%P %N %G %t\"")

    def test_sinfo_empty_output(self):
        hpc = Hpc(host="uva")
        with patch("cloudmesh.ai.slurm.Slurm._run_remote") as mock_run:
            mock_run.return_value = MagicMock(stdout="")
            result = hpc.sinfo()
            self.assertEqual(result, [])

if __name__ == "__main__":
    unittest.main()
