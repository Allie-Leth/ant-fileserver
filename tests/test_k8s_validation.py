"""Kubernetes validation test wrappers for pytest integration."""

import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.k8s
@pytest.mark.slow
class TestKubernetesValidation:
    """Test suite for Kubernetes manifest validation."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Ensure we're in the correct directory."""
        self.root_dir = Path(__file__).parent.parent
        os.chdir(self.root_dir)

    def run_script(self, script_name: str) -> subprocess.CompletedProcess:
        """Run a validation script and return the result."""
        script_path = self.root_dir / "scripts" / "k8s" / script_name

        # Make sure script is executable
        script_path.chmod(0o755)

        result = subprocess.run(
            [str(script_path)], check=False, capture_output=True, text=True
        )
        return result

    def test_base_deployment(self):
        """Test base deployment manifests."""
        result = self.run_script("test-base-deployment.sh")

        # Print output for debugging if test fails
        if result.returncode != 0:
            print(f"\nSTDOUT:\n{result.stdout}")
            print(f"\nSTDERR:\n{result.stderr}")

        assert result.returncode == 0, "Base deployment tests failed"
        assert "Tests Passed:" in result.stdout

    def test_phase2_network(self):
        """Test Phase 2: Network security features."""
        result = self.run_script("test-phase2-network.sh")

        if result.returncode != 0:
            print(f"\nSTDOUT:\n{result.stdout}")
            print(f"\nSTDERR:\n{result.stderr}")

        assert result.returncode == 0, "Phase 2 network tests failed"
        assert "Tests Passed:" in result.stdout

    def test_phase3_production(self):
        """Test Phase 3: Production readiness features."""
        result = self.run_script("test-phase3-production.sh")

        if result.returncode != 0:
            print(f"\nSTDOUT:\n{result.stdout}")
            print(f"\nSTDERR:\n{result.stderr}")

        assert result.returncode == 0, "Phase 3 production tests failed"
        assert "Tests Passed: 33" in result.stdout

    def test_integration(self):
        """Test integration across all phases."""
        result = self.run_script("test-integration.sh")

        if result.returncode != 0:
            print(f"\nSTDOUT:\n{result.stdout}")
            print(f"\nSTDERR:\n{result.stderr}")

        assert result.returncode == 0, "Integration tests failed"
        assert "Tests Passed: 60" in result.stdout

    def test_security_context(self):
        """Test security context configuration."""
        result = self.run_script("test-security-context.sh")

        if result.returncode != 0:
            print(f"\nSTDOUT:\n{result.stdout}")
            print(f"\nSTDERR:\n{result.stderr}")

        assert result.returncode == 0, "Security context tests failed"
        assert "Tests Passed:" in result.stdout

    def test_all_validation(self):
        """Run complete validation suite."""
        result = self.run_script("validate-all.sh")

        if result.returncode != 0:
            print(f"\nSTDOUT:\n{result.stdout}")
            print(f"\nSTDERR:\n{result.stderr}")

        assert result.returncode == 0, "Complete validation failed"
        assert "Total Tests Passed:" in result.stdout


@pytest.mark.k8s
class TestKubernetesManifests:
    """Test individual Kubernetes manifest generation."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Ensure we're in the correct directory."""
        self.root_dir = Path(__file__).parent.parent
        os.chdir(self.root_dir)

    def test_local_overlay_builds(self):
        """Test that local overlay builds successfully."""
        result = subprocess.run(
            ["kubectl", "kustomize", "k8s/app/overlays/local"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Local overlay build failed: {result.stderr}"
        assert "kind: Deployment" in result.stdout
        assert "kind: Service" in result.stdout

    def test_dev_overlay_builds(self):
        """Test that dev overlay builds successfully."""
        result = subprocess.run(
            ["kubectl", "kustomize", "k8s/app/overlays/dev"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Dev overlay build failed: {result.stderr}"
        assert "kind: Deployment" in result.stdout
        assert "kind: Ingress" in result.stdout

    def test_staging_overlay_builds(self):
        """Test that staging overlay builds successfully."""
        result = subprocess.run(
            ["kubectl", "kustomize", "k8s/app/overlays/staging"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Staging overlay build failed: {result.stderr}"
        assert "kind: HorizontalPodAutoscaler" in result.stdout
        assert "kind: PodDisruptionBudget" in result.stdout
        assert "kind: ServiceMonitor" in result.stdout

    def test_prod_overlay_builds(self):
        """Test that production overlay builds successfully."""
        result = subprocess.run(
            ["kubectl", "kustomize", "k8s/app/overlays/prod"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Prod overlay build failed: {result.stderr}"
        assert "kind: HorizontalPodAutoscaler" in result.stdout
        assert "kind: PodDisruptionBudget" in result.stdout
        assert "requiredDuringSchedulingIgnoredDuringExecution" in result.stdout


@pytest.mark.k8s
class TestKubernetesDeploymentScripts:
    """Test deployment and operational scripts."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Ensure we're in the correct directory."""
        self.root_dir = Path(__file__).parent.parent
        os.chdir(self.root_dir)

    @pytest.mark.skip(reason="Requires actual cluster - run manually")
    def test_deployment_script(self):
        """Test staging deployment script (skipped by default)."""
        result = subprocess.run(
            ["./scripts/k8s/deploy-phase3-staging.sh"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_quick_validation(self):
        """Test quick Phase 3 validation script."""
        script_path = self.root_dir / "scripts" / "k8s" / "test-phase3-quick.sh"
        script_path.chmod(0o755)

        result = subprocess.run(
            [str(script_path)], check=False, capture_output=True, text=True
        )

        if result.returncode != 0:
            print(f"\nSTDOUT:\n{result.stdout}")
            print(f"\nSTDERR:\n{result.stderr}")

        assert result.returncode == 0, "Quick validation failed"
        assert "Phase 3 Feature Summary" in result.stdout


# Mark K8s tests to allow easy filtering
pytest.mark.k8s = pytest.mark.k8s
