"""Project generation service for managing project lifecycle."""

import json
import logging
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from src.models.project import (
    Project,
    ProjectConfig,
    ProjectMetadata,
    ProjectStatus,
    ProjectTemplate,
    ProjectType,
)
from src.services.template_service import TemplateService
from src.services.storage_service import StorageService
from src.services.validation_service import ValidationService
from src.utils.exceptions import (
    ProjectCreationError,
    ProjectNotFoundError,
    ProjectValidationError,
    StorageError,
    TemplateError,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ProjectService:
    """Service for managing project generation and lifecycle operations."""

    def __init__(
        self,
        template_service: TemplateService,
        storage_service: StorageService,
        validation_service: ValidationService,
        projects_dir: Optional[Path] = None,
    ) -> None:
        """Initialize project service with required dependencies.

        Args:
            template_service: Service for template management
            storage_service: Service for project storage
            validation_service: Service for project validation
            projects_dir: Optional custom projects directory path

        Raises:
            ValueError: If required services are None
        """
        if not all([template_service, storage_service, validation_service]):
            raise ValueError("All services must be provided")

        self._template_service = template_service
        self._storage_service = storage_service
        self._validation_service = validation_service
        self._projects_dir = projects_dir or Path.cwd() / "projects"
        self._projects_dir.mkdir(parents=True, exist_ok=True)
        self._active_projects: Dict[str, Project] = {}

    def create_project(
        self,
        name: str,
        project_type: ProjectType,
        config: Optional[ProjectConfig] = None,
        template_name: Optional[str] = None,
        metadata: Optional[ProjectMetadata] = None,
    ) -> Project:
        """Create a new project with specified configuration.

        Args:
            name: Project name
            project_type: Type of project to create
            config: Optional project configuration
            template_name: Optional template name to use
            metadata: Optional project metadata

        Returns:
            Created Project instance

        Raises:
            ProjectValidationError: If project parameters are invalid
            TemplateError: If template processing fails
            ProjectCreationError: If project creation fails
        """
        try:
            # Validate project parameters
            self._validate_project_params(name, project_type)

            # Generate unique project ID
            project_id = str(uuid4())

            # Create project metadata
            project_metadata = metadata or ProjectMetadata(
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                version="1.0.0",
                author=os.environ.get("USER", "unknown"),
            )

            # Create project configuration
            project_config = config or ProjectConfig(
                project_type=project_type,
                settings={},
                dependencies=[],
                build_config={},
            )

            # Create project directory
            project_path = self._projects_dir / project_id
            project_path.mkdir(parents=True, exist_ok=True)

            # Create project instance
            project = Project(
                id=project_id,
                name=name,
                project_type=project_type,
                status=ProjectStatus.CREATING,
                config=project_config,
                metadata=project_metadata,
                path=project_path,
                template_name=template_name,
            )

            # Apply template if specified
            if template_name:
                self._apply_template(project, template_name)

            # Generate project structure
            self._generate_project_structure(project)

            # Save project configuration
            self._save_project_config(project)

            # Update project status
            project.status = ProjectStatus.READY
            project.metadata.updated_at = datetime.utcnow()

            # Store in active projects
            self._active_projects[project_id] = project

            # Persist to storage
            self._storage_service.save_project(project)

            logger.info(
                "Project created successfully",
                extra={
                    "project_id": project_id,
                    "name": name,
                    "type": project_type.value,
                },
            )

            return project

        except (ProjectValidationError, TemplateError) as exc:
            logger.error(
                "Project creation validation failed",
                extra={"name": name, "error": str(exc)},
            )
            raise
        except Exception as exc:
            logger.error(
                "Project creation failed",
                extra={"name": name, "error": str(exc)},
            )
            raise ProjectCreationError(f"Failed to create project: {exc}") from exc

    def get_project(self, project_id: str) -> Project:
        """Retrieve project by ID.

        Args:
            project_id: Unique project identifier

        Returns:
            Project instance

        Raises:
            ProjectNotFoundError: If project not found
        """
        # Check active projects first
        if project_id in self._active_projects:
            return self._active_projects[project_id]

        # Try to load from storage
        try:
            project = self._storage_service.load_project(project_id)
            self._active_projects[project_id] = project
            return project
        except StorageError as exc:
            raise ProjectNotFoundError(
                f"Project {project_id} not found"
            ) from exc

    def update_project(
        self,
        project_id: str,
        config: Optional[ProjectConfig] = None,
        metadata: Optional[ProjectMetadata] = None,
    ) -> Project:
        """Update existing project configuration.

        Args:
            project_id: Project identifier
            config: Optional new configuration
            metadata: Optional new metadata

        Returns:
            Updated Project instance

        Raises:
            ProjectNotFoundError: If project not found
            ProjectValidationError: If update parameters are invalid
        """
        project = self.get_project(project_id)

        try:
            if config:
                self._validate_project_config(config)
                project.config = config

            if metadata:
                project.metadata = metadata

            project.metadata.updated_at = datetime.utcnow()

            # Persist updates
            self._save_project_config(project)
            self._storage_service.save_project(project)

            logger.info(
                "Project updated successfully",
                extra={"project_id": project_id},
            )

            return project

        except ProjectValidationError:
            raise
        except Exception as exc:
            logger.error(
                "Project update failed",
                extra={"project_id": project_id, "error": str(exc)},
            )
            raise ProjectCreationError(f"Failed to update project: {exc}") from exc

    def delete_project(self, project_id: str) -> bool:
        """Delete project and its resources.

        Args:
            project_id: Project identifier

        Returns:
            True if deletion successful

        Raises:
            ProjectNotFoundError: If project not found
        """
        project = self.get_project(project_id)

        try:
            # Remove from active projects
            self._active_projects.pop(project_id, None)

            # Delete project directory
            if project.path.exists():
                shutil.rmtree(project.path)

            # Remove from storage
            self._storage_service.delete_project(project_id)

            logger.info(
                "Project deleted successfully",
                extra={"project_id": project_id},
            )

            return True

        except Exception as exc:
            logger.error(
                "Project deletion failed",
                extra={"project_id": project_id, "error": str(exc)},
            )
            raise ProjectCreationError(f"Failed to delete project: {exc}") from exc

    def list_projects(
        self,
        status: Optional[ProjectStatus] = None,
        project_type: Optional[ProjectType] = None,
    ) -> List[Project]:
        """List projects with optional filtering.

        Args:
            status: Optional status filter
            project_type: Optional project type filter

        Returns:
            List of matching Project instances
        """
        try:
            projects = self._storage_service.list_projects()

            if status:
                projects = [p for p in projects if p.status == status]

            if project_type:
                projects = [p for p in projects if p.project_type == project_type]

            return projects

        except Exception as exc:
            logger.error(
                "Failed to list projects",
                extra={"error": str(exc)},
            )
            return []

    def generate_project_files(self, project_id: str) -> Dict[str, Path]:
        """Generate all project files from template.

        Args:
            project_id: Project identifier

        Returns:
            Dictionary of generated file paths

        Raises:
            ProjectNotFoundError: If project not found
            TemplateError: If file generation fails
        """
        project = self.get_project(project_id)

        try:
            if project.template_name:
                generated_files = self._template_service.generate_files(
                    template_name=project.template_name,
                    output_dir=project.path,
                    context=self._build_template_context(project),
                )
            else:
                generated_files = self._generate_default_files(project)

            project.metadata.updated_at = datetime.utcnow()
            self._storage_service.save_project(project)

            logger.info(
                "Project files generated",
                extra={
                    "project_id": project_id,
                    "file_count": len(generated_files),
                },
            )

            return generated_files

        except TemplateError:
            raise
        except Exception as exc:
            logger.error(
                "File generation failed",
                extra={"project_id": project_id, "error": str(exc)},
            )
            raise TemplateError(f"Failed to generate files: {exc}") from exc

    def validate_project(self, project_id: str) -> Tuple[bool, List[str]]:
        """Validate project configuration and structure.

        Args:
            project_id: Project identifier

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        try:
            project = self.get_project(project_id)
            return self._validation_service.validate_project(project)
        except ProjectNotFoundError:
            return False, ["Project not found"]
        except Exception as exc:
            logger.error(
                "Project validation failed",
                extra={"project_id": project_id, "error": str(exc)},
            )
            return False, [str(exc)]

    def export_project(
        self, project_id: str, export_path: Optional[Path] = None
    ) -> Path:
        """Export project to specified path.

        Args:
            project_id: Project identifier
            export_path: Optional export destination path

        Returns:
            Path to exported project

        Raises:
            ProjectNotFoundError: If project not found
            ProjectCreationError: If export fails
        """
        project = self.get_project(project_id)

        try:
            export_path = export_path or (
                self._projects_dir / f"{project.name}_export"
            )

            if export_path.exists():
                shutil.rmtree(export_path)

            shutil.copytree(project.path, export_path)

            logger.info(
                "Project exported successfully",
                extra={
                    "project_id": project_id,
                    "export_path": str(export_path),
                },
            )

            return export_path

        except Exception as exc:
            logger.error(
                "Project export failed",
                extra={"project_id": project_id, "error": str(exc)},
            )
            raise ProjectCreationError(f"Failed to export project: {exc}") from exc

    def _validate_project_params(
        self, name: str, project_type: ProjectType
    ) -> None:
        """Validate project creation parameters.

        Args:
            name: Project name
            project_type: Project type

        Raises:
            ProjectValidationError: If parameters are invalid
        """
        errors: List[str] = []

        if not name or not name.strip():
            errors.append("Project name cannot be empty")

        if len(name) > 255:
            errors.append("Project name exceeds maximum length of 255 characters")

        if not project_type:
            errors.append("Project type must be specified")

        if errors:
            raise ProjectValidationError(
                "Invalid project parameters",
                details={"errors": errors},
            )

    def _validate_project_config(self, config: ProjectConfig) -> None:
        """Validate project configuration.

        Args:
            config: Project configuration to validate

        Raises:
            ProjectValidationError: If configuration is invalid
        """
        if not config.project_type:
            raise ProjectValidationError("Project type must be specified in config")

    def _apply_template(self, project: Project, template_name: str) -> None:
        """Apply template to project.

        Args:
            project: Project instance
            template_name: Template name to apply

        Raises:
            TemplateError: If template application fails
        """
        try:
            template = self._template_service.get_template(template_name)
            project.template_name = template_name

            # Generate template files
            self._template_service.apply_template(
                template=template,
                output_dir=project.path,
                context=self._build_template_context(project),
            )

        except Exception as exc:
            raise TemplateError(
                f"Failed to apply template '{template_name}': {exc}"
            ) from exc

    def _generate_project_structure(self, project: Project) -> None:
        """Generate default project directory structure.

        Args:
            project: Project instance
        """
        directories = [
            project.path / "src",
            project.path / "tests",
            project.path / "docs",
            project.path / "config",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

        # Create .gitkeep files to preserve empty directories
        for directory in directories:
            gitkeep = directory / ".gitkeep"
            if not gitkeep.exists():
                gitkeep.touch()

    def _generate_default_files(self, project: Project) -> Dict[str, Path]:
        """Generate default project files when no template is specified.

        Args:
            project: Project instance

        Returns:
            Dictionary of generated file paths
        """
        generated_files: Dict[str, Path] = {}

        # Generate README
        readme_path = project.path / "README.md"
        readme_content = self._generate_readme_content(project)
        readme_path.write_text(readme_content)
        generated_files["README"] = readme_path

        # Generate .gitignore
        gitignore_path = project.path / ".gitignore"
        gitignore_content = self._generate_gitignore_content(project)
        gitignore_path.write_text(gitignore_content)
        generated_files[".gitignore"] = gitignore_path

        # Generate main module
        main_path = project.path / "src" / "main.py"
        main_content = self._generate_main_content(project)
        main_path.write_text(main_content)
        generated_files["main"] = main_path

        return generated_files

    def _generate_readme_content(self, project: Project) -> str:
        """Generate README.md content for project.

        Args:
            project: Project instance

        Returns:
            README content string
        """
        return f"""# {project.name}

## Description
{project.metadata.description or "No description provided."}

## Project Type
{project.project_type.value}

## Setup
```bash
pip install -r requirements.txt
```

## Usage
```python
from src.main import main
main()
```

## Testing
```bash
pytest tests/
```

## License
{project.metadata.license or "MIT"}
"""

    def _generate_gitignore_content(self, project: Project) -> str:
        """Generate .gitignore content for project.

        Args:
            project: Project instance

        Returns:
            .gitignore content string
        """
        return """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.env

# IDE
.vscode/
.idea/
*.swp
*.swo

# Project
dist/
build/
*.egg-info/
*.egg
.eggs/

# Testing
.coverage
htmlcov/
.pytest_cache/

# OS
.DS_Store
Thumbs.db
"""

    def _generate_main_content(self, project: Project) -> str:
        """Generate main.py content for project.

        Args:
            project: Project instance

        Returns:
            Main module content string
        """
        return f'''"""Main module for {project.name}."""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def main() -> None:
    """Main entry point for the application."""
    logger.info("Starting {project.name}")
    # TODO: Implement main functionality


if __name__ == "__main__":
    main()
'''

    def _build_template_context(self, project: Project) -> Dict[str, Any]:
        """Build context dictionary for template rendering.

        Args:
            project: Project instance

        Returns:
            Template context dictionary
        """
        return {
            "project_name": project.name,
            "project_id": project.id,
            "project_type": project.project_type.value,
            "project_description": project.metadata.description or "",
            "author": project.metadata.author,
            "version": project.metadata.version,
            "created_at": project.metadata.created_at.isoformat(),
            "config": project.config.settings,
            "dependencies": project.config.dependencies,
        }

    def _save_project_config(self, project: Project) -> None:
        """Save project configuration to disk.

        Args:
            project: Project instance

        Raises:
            ProjectCreationError: If configuration save fails
        """
        try:
            config_path = project.path / "project_config.json"
            config_data = {
                "id": project.id,
                "name": project.name,
                "type": project.project_type.value,
                "status": project.status.value,
                "config": project.config.dict(),
                "metadata": project.metadata.dict(),
                "template_name": project.template_name,
            }

            with open(config_path, "w") as config_file:
                json.dump(config_data, config_file, indent=2, default=str)

        except Exception as exc:
            raise ProjectCreationError(
                f"Failed to save project configuration: {exc}"
            ) from exc

    def cleanup_inactive_projects(self, max_age_hours: int = 24) -> int:
        """Clean up inactive projects older than specified age.

        Args:
            max_age_hours: Maximum age in hours before cleanup

        Returns:
            Number of cleaned up projects
        """
        cleanup_count = 0
        current_time = datetime.utcnow()

        try:
            projects = self.list_projects(status=ProjectStatus.READY)

            for project in projects:
                age_hours = (
                    current_time - project.metadata.updated_at
                ).total_seconds() / 3600

                if age_hours > max_age_hours:
                    self.delete_project(project.id)
                    cleanup_count += 1

            logger.info(
                "Cleanup completed",
                extra={"cleaned_projects": cleanup_count},
            )

        except Exception as exc:
            logger.error(
                "Cleanup failed",
                extra={"error": str(exc)},
            )

        return cleanup_count

    def __enter__(self) -> "ProjectService":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Optional[object],
    ) -> None:
        """Context manager exit with cleanup."""
        self._active_projects.clear()