import os
import hcl2
import logging
import subprocess
import argparse
from typing import List, Set, Dict, Any
from dataclasses import dataclass
import requests
from urllib.parse import urlparse

# Configure logging with a file handler
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('terraform_validator.log'),
        logging.StreamHandler()
    ]
)

def setup_argument_parser() -> argparse.ArgumentParser:
    """Setup command line argument parser"""
    parser = argparse.ArgumentParser(
        description='Terraform Project Validator',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--path',
        type=str,
        required=True,
        help='Path to the Terraform project directory'
    )
    parser.add_argument(
        '--log-file',
        type=str,
        default='terraform_validator.log',
        help='Path to the log file'
    )
    return parser

@dataclass
class ValidationResult:
    """Class to store validation results"""
    file_path: str
    issues: List[str]
    is_valid: bool

class TerraformValidator:
    def __init__(self, directory: str):
        if not os.path.exists(directory):
            raise ValueError(f"Directory does not exist: {directory}")
        if not os.path.isdir(directory):
            raise ValueError(f"Path is not a directory: {directory}")
        self.directory = directory
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initializing validator for directory: {directory}")

    def run_terraform_fmt(self) -> bool:
        """Run terraform fmt command to check formatting."""
        try:
            self.logger.info("Running terraform fmt check...")
            result = subprocess.run(
                ['terraform', 'fmt', '-check', self.directory],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                self.logger.info("Terraform formatting check passed")
                return True
            else:
                self.logger.warning(f"Terraform formatting issues found:\n{result.stdout}")
                return False
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error running terraform fmt: {str(e)}")
            return False
        except FileNotFoundError:
            self.logger.error("Terraform command not found. Please ensure terraform is installed and in your PATH")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error running terraform fmt: {str(e)}")
            return False

    def run_terraform_init(self) -> bool:
        """Run terraform init command to initialize the directory."""
        try:
            self.logger.info("Running terraform init...")
            result = subprocess.run(
                ['terraform', 'init', self.directory],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                self.logger.info("Terraform init completed successfully")
                return True
            else:
                self.logger.warning(f"Terraform init issues found:\n{result.stderr}")
                return False
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error running terraform init: {str(e)}")
            return False
        except FileNotFoundError:
            self.logger.error("Terraform command not found. Please ensure terraform is installed and in your PATH")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error running terraform init: {str(e)}")
            return False

    def run_terraform_plan(self) -> bool:
        """Run terraform plan command to create an execution plan."""
        try:
            self.logger.info("Running terraform plan...")
            result = subprocess.run(
                ['terraform', 'plan', self.directory],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                self.logger.info("Terraform plan completed successfully")
                return True
            else:
                self.logger.warning(f"Terraform plan issues found:\n{result.stderr}")
                return False
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error running terraform plan: {str(e)}")
            return False
        except FileNotFoundError:
            self.logger.error("Terraform command not found. Please ensure terraform is installed and in your PATH")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error running terraform plan: {str(e)}")
            return False

    def run_terraform_validate(self) -> bool:
        """Run terraform validate command to check syntax and configuration errors."""
        try:
            self.logger.info("Running terraform validate...")
            result = subprocess.run(
                ['terraform', 'validate', self.directory],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                self.logger.info("Terraform validation passed")
                return True
            else:
                self.logger.warning(f"Terraform validation issues found:\n{result.stdout}")
                return False
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error running terraform validate: {str(e)}")
            return False
        except FileNotFoundError:
            self.logger.error("Terraform command not found. Please ensure terraform is installed and in your PATH")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error running terraform validate: {str(e)}")
            return False

    def validate_directory(self) -> List[ValidationResult]:
        """Validate all Terraform files in the directory."""
        results = []
        # Check if directory contains .tf files
        tf_files = [f for f in os.listdir(self.directory) if f.endswith('.tf')]
        if not tf_files:
            self.logger.warning(f"No Terraform files found in {self.directory}")
            return results

        # Run terraform commands
        if not self.run_terraform_fmt():
            self.logger.warning("Terraform formatting check failed")
        if not self.run_terraform_init():
            self.logger.warning("Terraform init failed")
        if not self.run_terraform_validate():
            self.logger.warning("Terraform syntax validation failed")
        if not self.run_terraform_plan():
            self.logger.warning("Terraform plan failed")

        # Validate each .tf file
        for root, _, files in os.walk(self.directory):
            for file in files:
                if file.endswith('.tf'):
                    file_path = os.path.join(root, file)
                    results.append(self.validate_file(file_path))
        return results

    def validate_file(self, file_path: str) -> ValidationResult:
        """Validate a single Terraform file."""
        self.logger.info(f"Validating file: {file_path}")
        issues = []
        try:
            parser_data = self.parse_terraform_file(file_path)

            # Check module source reachability
            invalid_sources = self.check_module_sources(parser_data)
            if invalid_sources:
                issues.append(f"Invalid or unreachable module sources found: {invalid_sources}")

            # Check URL reachability
            unreachable_urls = self.check_url_reachability(parser_data)
            if unreachable_urls:
                issues.append(f"Unreachable URLs found: {unreachable_urls}")

            return ValidationResult(
                file_path=file_path,
                issues=issues,
                is_valid=len(issues) == 0
            )
        except Exception as e:
            self.logger.error(f"Error validating file {file_path}: {str(e)}")
            return ValidationResult(
                file_path=file_path,
                issues=[f"Error during validation: {str(e)}"],
                is_valid=False
            )

    def check_module_sources(self, parser_data: Dict[str, Any]) -> List[str]:
        """Check if module sources are valid and reachable."""
        modules = parser_data.get('module', {})
        invalid_sources = []
        for module_name, config in modules.items():
            source = config.get('source')
            if source:
                parsed_url = urlparse(source)
                if parsed_url.scheme in ['http', 'https']:
                    # Check if URL is reachable
                    try:
                        response = requests.head(source, allow_redirects=True, timeout=5)
                        if response.status_code >= 400:
                            invalid_sources.append(f"Module {module_name}: Unreachable source URL {source}")
                    except requests.RequestException as e:
                        self.logger.warning(f"Error reaching module source URL {source}: {str(e)}")
                        invalid_sources.append(f"Module {module_name}: Unreachable source URL {source}")
                elif parsed_url.scheme == '':
                    # Check if local path exists
                    local_path = os.path.join(self.directory, source)
                    if not os.path.exists(local_path):
                        invalid_sources.append(f"Module {module_name}: Local source path does not exist {source}")
        return invalid_sources

    def check_url_reachability(self, parser_data: Dict[str, Any]) -> List[str]:
        """Check if URLs in the Terraform configuration are reachable."""
        urls = self.extract_urls(parser_data)
        unreachable_urls = []
        for url in urls:
            try:
                response = requests.head(url, allow_redirects=True, timeout=5)
                if response.status_code >= 400:
                    unreachable_urls.append(url)
            except requests.RequestException as e:
                self.logger.warning(f"Error reaching URL {url}: {str(e)}")
                unreachable_urls.append(url)
        return unreachable_urls

    def extract_urls(self, parser_data: Dict[str, Any]) -> List[str]:
        """Extract URLs from the Terraform configuration."""
        urls = []
        # Implement logic to extract URLs from the configuration data
        # This will depend on how URLs are stored in your Terraform files
        # You might need to recursively search through the data structure
        return urls

    def parse_terraform_file(self, file_path: str) -> Dict[str, Any]:
        """Parse a Terraform file and return its contents as a dictionary."""
        try:
            with open(file_path, 'r') as f:
                return hcl2.load(f)
        except Exception as e:
            self.logger.error(f"Error parsing file {file_path}: {str(e)}")
            raise

def main():
    # Parse command line arguments
    parser = setup_argument_parser()
    args = parser.parse_args()
    try:
        # Update logging configuration with user-specified log file
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(args.log_file),
                logging.StreamHandler()
            ]
        )
        # Create validator instance with provided path
        validator = TerraformValidator(args.path)
        # Run validation
        results = validator.validate_directory()
        # Track overall validation status
        has_errors = False
        # Print results
        print("\nValidation Results:")
        print("==================")
        for result in results:
            if not result.is_valid:
                has_errors = True
                logging.error(f"\nFile: {result.file_path}")
                for issue in result.issues:
                    logging.error(f"  - {issue}")
            else:
                logging.info(f"File {result.file_path} passed validation")
        # Print summary
        print("\nValidation Summary:")
        print("==================")
        print(f"Total files checked: {len(results)}")
        print(f"Files with issues: {sum(1 for r in results if not r.is_valid)}")
        print(f"Status: {'❌ FAILED' if has_errors else '✅ PASSED'}")
    except Exception as e:
        logging.error(f"Validation failed: {str(e)}")
        raise

if __name__ == "__main__":
    main()
