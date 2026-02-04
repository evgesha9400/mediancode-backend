#!/usr/bin/env python3
# deploy/railway/deploy.py
"""
Railway deployment script for Median Code Backend.

Reads secrets from .env.{environment} and syncs them to Railway automatically.

Deployment order:
1. Validate prerequisites and load .env file
2. Sync environment variables to Railway
3. Ensure PostgreSQL database is provisioned
4. Run database migrations
5. Deploy the backend service
6. Verify deployment health

Usage:
    python deploy/railway/deploy.py --env production
    python deploy/railway/deploy.py --env development
    python deploy/railway/deploy.py --env production --dry-run
"""

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn


class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    END = "\033[0m"


def log_info(msg: str) -> None:
    print(f"{Colors.BLUE}ℹ{Colors.END}  {msg}")


def log_success(msg: str) -> None:
    print(f"{Colors.GREEN}✓{Colors.END}  {msg}")


def log_warning(msg: str) -> None:
    print(f"{Colors.YELLOW}⚠{Colors.END}  {msg}")


def log_error(msg: str) -> None:
    print(f"{Colors.RED}✗{Colors.END}  {msg}")


def log_step(step: int, total: int, msg: str) -> None:
    print(f"\n{Colors.BOLD}[{step}/{total}]{Colors.END} {Colors.CYAN}{msg}{Colors.END}")


def log_dim(msg: str) -> None:
    print(f"   {Colors.DIM}{msg}{Colors.END}")


def run_command(
    cmd: list[str],
    capture: bool = False,
    check: bool = True,
    env: dict | None = None,
) -> subprocess.CompletedProcess:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    try:
        return subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            check=check,
            env=full_env,
        )
    except subprocess.CalledProcessError as e:
        if capture:
            log_error(f"Command failed: {' '.join(cmd)}")
            if e.stdout:
                print(f"stdout: {e.stdout}")
            if e.stderr:
                print(f"stderr: {e.stderr}")
        raise


def fatal(msg: str) -> NoReturn:
    log_error(msg)
    sys.exit(1)


def parse_env_file(env_file: Path) -> dict[str, str]:
    """Parse a .env file into a dictionary."""
    if not env_file.exists():
        return {}

    variables = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Remove quotes if present
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                if key and not key.startswith("#"):
                    variables[key] = value

    return variables


@dataclass
class RailwayProject:
    project_id: str
    project_name: str
    environment: str
    service_url: str | None = None


class RailwayDeployer:
    """Handles Railway deployment operations."""

    # Variables to sync from .env file to Railway
    # DATABASE_URL is excluded - Railway manages it automatically
    SYNC_VARIABLES = [
        "CLERK_FRONTEND_API_URL",
        "CLERK_JWT_AUDIENCE",
        "GLOBAL_NAMESPACE_ID",
        "FRONTEND_URL",
    ]

    REQUIRED_VARIABLES = [
        "CLERK_FRONTEND_API_URL",
        "FRONTEND_URL",
    ]

    def __init__(self, environment: str, dry_run: bool = False):
        self.environment = environment
        self.dry_run = dry_run
        self.project: RailwayProject | None = None
        self.project_root = self._find_project_root()
        self.env_file = self.project_root / f".env.{environment}"
        self.env_vars: dict[str, str] = {}

    def _find_project_root(self) -> Path:
        """Find the project root directory."""
        current = Path(__file__).resolve().parent
        while current != current.parent:
            if (current / "pyproject.toml").exists():
                return current
            current = current.parent
        return Path.cwd()

    def check_prerequisites(self) -> None:
        """Verify Railway CLI is installed and configured."""
        log_step(1, 7, "Checking prerequisites")

        # Check Railway CLI
        try:
            result = run_command(["railway", "version"], capture=True)
            version = result.stdout.strip()
            log_success(f"Railway CLI: {version}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            fatal(
                "Railway CLI not found. Install with:\n"
                "  brew install railway\n"
                "  # or: npm install -g @railway/cli"
            )

        # Check if logged in
        try:
            result = run_command(["railway", "whoami"], capture=True)
            user = result.stdout.strip()
            log_success(f"Logged in as: {user}")
        except subprocess.CalledProcessError:
            fatal("Not logged into Railway. Run: railway login")

        # Check if linked to a project
        try:
            result = run_command(["railway", "status"], capture=True, check=False)
            if "No project linked" in result.stdout or result.returncode != 0:
                fatal("No Railway project linked. Run: railway link")
            log_success("Project linked")
        except subprocess.CalledProcessError:
            fatal("Failed to check Railway project status")

    def load_env_file(self) -> None:
        """Load environment variables from .env.{environment} file."""
        log_step(2, 7, f"Loading {self.env_file.name}")

        if not self.env_file.exists():
            example_file = self.project_root / f".env.{self.environment}.example"
            fatal(
                f"Environment file not found: {self.env_file}\n"
                f"Create it from the example:\n"
                f"  cp {example_file.name} {self.env_file.name}"
            )

        self.env_vars = parse_env_file(self.env_file)

        # Check required variables
        missing = []
        for var in self.REQUIRED_VARIABLES:
            if var in self.env_vars and self.env_vars[var]:
                # Truncate for display
                val = self.env_vars[var]
                display = val[:40] + "..." if len(val) > 40 else val
                log_success(f"{var} = {display}")
            else:
                missing.append(var)
                log_error(f"{var} is missing or empty")

        if missing:
            fatal(f"Missing required variables in {self.env_file.name}: {', '.join(missing)}")

        # Show optional variables
        for var in self.SYNC_VARIABLES:
            if var not in self.REQUIRED_VARIABLES:
                if var in self.env_vars and self.env_vars[var]:
                    log_dim(f"{var} = {self.env_vars[var]}")
                else:
                    log_dim(f"{var} (not set, using default)")

    def get_project_info(self) -> RailwayProject:
        """Get current Railway project information."""
        log_step(3, 7, "Getting project information")

        try:
            result = run_command(["railway", "status", "--json"], capture=True)
            status = json.loads(result.stdout)

            project = RailwayProject(
                project_id=status.get("projectId", "unknown"),
                project_name=status.get("projectName", "unknown"),
                environment=status.get("environmentName", self.environment),
            )

            log_success(f"Project: {project.project_name}")
            log_success(f"Railway environment: {project.environment}")

            self.project = project
            return project

        except (subprocess.CalledProcessError, json.JSONDecodeError):
            log_warning("Could not parse project info, continuing...")
            self.project = RailwayProject(
                project_id="unknown",
                project_name="unknown",
                environment=self.environment,
            )
            return self.project

    def sync_variables(self) -> None:
        """Sync environment variables from .env file to Railway."""
        log_step(4, 7, "Syncing environment variables to Railway")

        if self.dry_run:
            log_info("[DRY RUN] Would sync these variables:")
            for var in self.SYNC_VARIABLES:
                if var in self.env_vars and self.env_vars[var]:
                    val = self.env_vars[var]
                    display = val[:40] + "..." if len(val) > 40 else val
                    log_dim(f"  {var}={display}")
            return

        # Get current Railway variables
        try:
            result = run_command(["railway", "variables", "--json"], capture=True, check=False)
            current_vars = json.loads(result.stdout) if result.stdout.strip() else {}
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            current_vars = {}

        # Sync each variable
        synced = 0
        for var in self.SYNC_VARIABLES:
            if var not in self.env_vars or not self.env_vars[var]:
                continue

            new_value = self.env_vars[var]
            current_value = current_vars.get(var, "")

            if current_value == new_value:
                log_dim(f"{var} (unchanged)")
                continue

            try:
                run_command(["railway", "variables", "set", f"{var}={new_value}"], capture=True)
                if current_value:
                    log_success(f"{var} updated")
                else:
                    log_success(f"{var} set")
                synced += 1
            except subprocess.CalledProcessError:
                log_error(f"Failed to set {var}")

        if synced == 0:
            log_info("All variables already in sync")
        else:
            log_success(f"Synced {synced} variable(s)")

    def ensure_database(self) -> None:
        """Ensure PostgreSQL database is provisioned."""
        log_step(5, 7, "Checking database")

        try:
            result = run_command(["railway", "variables", "--json"], capture=True, check=False)
            if result.returncode == 0:
                variables = json.loads(result.stdout) if result.stdout.strip() else {}

                if "DATABASE_URL" in variables or "PGHOST" in variables or "POSTGRES_URL" in variables:
                    log_success("PostgreSQL database configured")
                    return

        except (subprocess.CalledProcessError, json.JSONDecodeError):
            pass

        log_warning("PostgreSQL database not detected")

        if self.dry_run:
            log_info("[DRY RUN] Would prompt to add PostgreSQL")
            return

        print(f"\n{Colors.YELLOW}Add PostgreSQL:{Colors.END} railway add -d postgres\n")

        response = input("Add PostgreSQL now? [y/N] ")
        if response.lower() == "y":
            try:
                run_command(["railway", "add", "-d", "postgres"])
                log_success("PostgreSQL added")
                log_info("Waiting for database to provision...")
                time.sleep(10)
            except subprocess.CalledProcessError:
                fatal("Failed to add PostgreSQL")
        else:
            fatal("Database required for deployment")

    def run_migrations(self) -> None:
        """Run database migrations via Railway."""
        log_step(6, 7, "Running database migrations")

        if self.dry_run:
            log_info("[DRY RUN] Would run: railway run alembic upgrade head")
            return

        log_info("Running Alembic migrations...")
        try:
            run_command(["railway", "run", "alembic", "upgrade", "head"])
            log_success("Migrations completed")
        except subprocess.CalledProcessError:
            fatal("Migration failed. Run manually: railway run alembic upgrade head")

    def deploy(self) -> None:
        """Deploy the application to Railway."""
        log_step(7, 7, "Deploying application")

        if self.dry_run:
            log_info("[DRY RUN] Would run: railway up --detach")
            return

        log_info("Starting deployment...")
        try:
            run_command(["railway", "up", "--detach"])
            log_success("Deployment initiated")
        except subprocess.CalledProcessError:
            fatal("Deployment failed")

    def wait_for_health(self, timeout: int = 120) -> None:
        """Wait for the deployment to become healthy."""
        if self.dry_run:
            log_info("[DRY RUN] Would wait for health check")
            return

        log_info(f"Waiting for health check (timeout: {timeout}s)...")

        try:
            result = run_command(["railway", "domain"], capture=True, check=False)
            if result.returncode == 0 and result.stdout.strip():
                domain = result.stdout.strip()
                if not domain.startswith("http"):
                    domain = f"https://{domain}"
                health_url = f"{domain}/health"
                log_info(f"Health URL: {health_url}")

                import urllib.error
                import urllib.request

                start_time = time.time()
                while time.time() - start_time < timeout:
                    try:
                        req = urllib.request.Request(health_url, method="GET")
                        with urllib.request.urlopen(req, timeout=10) as response:
                            if response.status == 200:
                                log_success("Deployment is healthy!")
                                self.project.service_url = domain
                                return
                    except (urllib.error.URLError, urllib.error.HTTPError):
                        pass

                    log_dim("Waiting for service...")
                    time.sleep(5)

                log_warning(f"Health check timed out after {timeout}s")
                log_info("Check logs: railway logs")
            else:
                log_warning("No domain configured. Add one: railway domain")

        except subprocess.CalledProcessError:
            log_warning("Could not get service domain")

    def print_summary(self) -> None:
        """Print deployment summary."""
        print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}Deployment Complete!{Colors.END}")
        print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")

        print(f"{Colors.CYAN}Environment:{Colors.END} {self.environment}")
        print(f"{Colors.CYAN}Env file:{Colors.END} {self.env_file.name}")

        if self.project and self.project.service_url:
            print(f"{Colors.CYAN}Service URL:{Colors.END} {self.project.service_url}")
            print(f"{Colors.CYAN}Health:{Colors.END} {self.project.service_url}/health")
            print(f"{Colors.CYAN}API Docs:{Colors.END} {self.project.service_url}/docs")

        print(f"\n{Colors.BOLD}Vercel Frontend Config:{Colors.END}")
        url = self.project.service_url if self.project and self.project.service_url else "https://your-app.up.railway.app"
        print(f"  NEXT_PUBLIC_API_URL={url}")

        print(f"\n{Colors.BOLD}Commands:{Colors.END}")
        print("  railway logs        - View logs")
        print("  railway open        - Open dashboard")
        print("  railway variables   - View variables")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deploy Median Code Backend to Railway",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python deploy/railway/deploy.py --env production     # Deploy to production
  python deploy/railway/deploy.py --env development    # Deploy to development
  python deploy/railway/deploy.py --env production --dry-run
        """,
    )
    parser.add_argument(
        "--env",
        choices=["production", "development"],
        required=True,
        help="Target environment (reads from .env.{environment})",
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Skip database migrations",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without making changes",
    )

    args = parser.parse_args()

    print(f"\n{Colors.BOLD}Median Code Backend - Railway Deployment{Colors.END}")
    print(f"{'='*45}")
    print(f"Environment: {Colors.CYAN}{args.env}{Colors.END}\n")

    if args.dry_run:
        log_warning("DRY RUN MODE - No changes will be made\n")

    deployer = RailwayDeployer(environment=args.env, dry_run=args.dry_run)

    try:
        deployer.check_prerequisites()
        deployer.load_env_file()
        deployer.get_project_info()
        deployer.sync_variables()
        deployer.ensure_database()

        if args.skip_migrations:
            log_info("Skipping migrations (--skip-migrations)")
        else:
            deployer.run_migrations()

        deployer.deploy()

        if not args.dry_run:
            deployer.wait_for_health()

        deployer.print_summary()

    except KeyboardInterrupt:
        print("\n")
        log_warning("Cancelled")
        sys.exit(1)


if __name__ == "__main__":
    main()
