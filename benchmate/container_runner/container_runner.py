import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Union


class ContainerError(Exception):
    """Base exception for Container-related errors."""
    pass


class ContainerSubprocessError(ContainerError):
    """Exception raised when an Container subprocess fails."""

    def __init__(self, returncode: int, stderr: str):
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"Container subprocess failed with return code {returncode}: {stderr}")


class ContainerSlurmError(ContainerError):
    """Exception raised for SLURM job-related errors."""
    pass


class ContainerRunner:
    """A class to run Container containers with various configuration options."""

    def __init__(self, container_path, running_command="singularity"):
        """
        Initialize the Container runner.

        Args:
            container_path: Path to the Singularity container image (.sif file)

        Raises:
            ContainerError: If the container path does not exist
        """
        self.container_path = str(Path(container_path).resolve())
        if not os.path.exists(self.container_path):
            raise ContainerError(f"Container path does not exist: {self.container_path}")
        self.bind_mounts: Dict[str, str] = {}
        self.use_gpu: bool = False
        self.Container_cmd = running_command

    def add_bind_mount(self, host_paths, container_path) -> None:
        """
        Add a bind mount to the container configuration.

        Args:
            host_path: Path on the host system
            container_path: Path inside the container

        Raises:
            ContainerError: If the host path does not exist
        """
        host_paths = [str(Path(host_path).resolve()) for host_path in host_paths]
        for host_path in host_paths:
            if not os.path.exists(host_path):
                raise ContainerError(f"Host path does not exist: {host_path}")
        self.bind_mounts[host_paths] = container_path

    def enable_gpu(self) -> None:
        """Enable NVIDIA GPU support for the container."""
        self.use_gpu = True

    def _build_Container_command(self, command: Union[str, List[str]]) -> List[str]:
        """
        Build the Container command with all configured options.

        Args:
            command: Command to run inside the container (string or list)

        Returns:
            List of command components
        """
        cmd = [self.Container_cmd, "run"]

        if self.use_gpu:
            cmd.append("--nv")

        for host_path, container_path in self.bind_mounts.items():
            cmd.append(f"--bind={host_path}:{container_path}")

        cmd.append(self.container_path)

        if isinstance(command, str):
            cmd.extend(command.split())
        else:
            cmd.extend(command)

        return cmd

    def run(self, command, **subprocess_kwargs):
        """
        Run a command in the Singularity container.

        Args:
            command: Command to run (string or list)
            **subprocess_kwargs: Additional arguments for subprocess.run

        Returns:
            CompletedProcess object

        Raises:
            ContainerSubprocessError: If the subprocess fails
        """
        cmd = self._build_Container_command(command)
        try:
            result = subprocess.run(cmd, **subprocess_kwargs, capture_output=True, text=True)
            if result.returncode != 0:
                raise ContainerSubprocessError(result.returncode, result.stderr)
            return result
        except subprocess.SubprocessError as e:
            raise ContainerError(f"Subprocess error: {str(e)}")

    def run_slurm(
            self,
            command: Union[str, List[str]],
            job_name: str = "Container_job",
            partition: str = "default",
            nodes: int = 1,
            ntasks: int = 1,
            time: str = "01:00:00",
            mem: str = "4G",
            gpus: Optional[int] = None,
            output_file: str = "slurm-%j.out",
            additional_sbatch: Optional[Dict[str, str]] = None
    ):
        """
        Submit a command to run in the singularity container as a SLURM job.

        Args:
            command: Command to run (string or list)
            job_name: Name of the SLURM job
            partition: SLURM partition to use
            nodes: Number of nodes
            ntasks: Number of tasks
            time: Time limit (format: HH:MM:SS)
            mem: Memory per node
            gpus: Number of GPUs to request (if any)
            output_file: SLURM output file pattern
            additional_sbatch: Additional SBATCH directives

        Returns:
            Job ID from sbatch submission

        Raises:
            ContainerSlurmError: If SLURM job submission fails
        """
        Container_cmd = " ".join(self._build_Container_command(command))

        sbatch_script = f"""#!/bin/bash
    #SBATCH --job-name={job_name}
    #SBATCH --partition={partition}
    #SBATCH --nodes={nodes}
    #SBATCH --ntasks={ntasks}
    #SBATCH --time={time}
    #SBATCH --mem={mem}
    #SBATCH --output={output_file}
    """

        if gpus is not None and self.use_gpu:
            sbatch_script += f"#SBATCH --gpus={gpus}\n"

        if additional_sbatch:
            for key, value in additional_sbatch.items():
                sbatch_script += f"#SBATCH --{key}={value}\n"

        sbatch_script += """
    # Load Container/Singularity module
    module load singularity

    # Run the Container command
    {0}
    """.format(Container_cmd)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write(sbatch_script)
            script_path = f.name

        try:
            result = subprocess.run(
                ["sbatch", script_path],
                capture_output=True,
                text=True,
                check=True
            )
            job_id = result.stdout.strip().split()[-1]
            return job_id
        except subprocess.SubprocessError as e:
            raise ContainerSlurmError(f"SLURM submission failed: {str(e)}")
        finally:
            os.unlink(script_path)

    def check_slurm_job_status(self, job_id: str) -> str:
        """
        Check the status of a SLURM job.

        Args:
            job_id: SLURM job ID

        Returns:
            Job status (e.g., PENDING, RUNNING, COMPLETED, FAILED)

        Raises:
            ContainerSlurmError: If job status check fails
        """
        try:
            result = subprocess.run(
                ["squeue", "-j", job_id, "-h", "-o", "%t"],
                capture_output=True,
                text=True,
                check=True
            )
            status = result.stdout.strip()
            if not status:
                # Check if job is completed or failed
                result = subprocess.run(
                    ["sacct", "-j", job_id, "--format=State", "-P", "-n"],
                    capture_output=True,
                    text=True
                )
                status_lines = result.stdout.strip().split('\n')
                if status_lines and status_lines[0]:
                    return status_lines[0]
                return "COMPLETED"  # Assume completed if not found
            return status
        except subprocess.SubprocessError as e:
            raise ContainerSlurmError(f"Failed to check SLURM job status: {str(e)}")

    def get_slurm_job_info(self, job_id: str) -> Dict[str, str]:
        """
        Get detailed information about a SLURM job.

        Args:
            job_id: SLURM job ID

        Returns:
            Dictionary containing job information

        Raises:
            ContainerSlurmError: If job info retrieval fails
        """
        try:
            result = subprocess.run(
                ["scontrol", "show", "job", job_id],
                capture_output=True,
                text=True,
                check=True
            )
            job_info = {}
            for line in result.stdout.split('\n'):
                for item in line.strip().split():
                    if '=' in item:
                        key, value = item.split('=', 1)
                        job_info[key] = value
            return job_info
        except subprocess.SubprocessError as e:
            raise ContainerSlurmError(f"Failed to get SLURM job info: {str(e)}")
