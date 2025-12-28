#!/usr/bin/env python3
"""
Module 1: Basic MCP Server - Starter Code
TODO: Implement tools for analyzing git changes and suggesting PR templates
"""

import json
from re import sub
import subprocess
import logging
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Initialize the FastMCP server and let's see
mcp = FastMCP("pr-agent")

logging.basicConfig(
    level = logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# PR template directory (shared across all modules)
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"

@mcp.tool()
async def analyze_file_changes(base_branch: str = "main", include_diff: bool = True, max_diff_lines: int = 500) -> str:
    """Get the full diff and list of changed files in the current git repository.
    
    Args:
        base_branch: Base branch to compare against (default: main)
        include_diff: Include the full diff content (default: true)
        max_diff_lines: Manimum diff lines to include (default: 500)
    """

    try:
        working_dir = None
        try: 
            context = mcp.get_context()
            roots_result = await context.session.list_roots()
            working_dir = roots_result.roots[0].uri.path
        except Exception as e:
            logger.warning(f'Unable to use MCP context: {e}')
            working_dir = os.getcwd()

        files_result = subprocess.run(
            ["git", "diff", "--name-status", f"{base_branch}...HEAD"],
            capture_output=True,
            text=True,
            cwd=working_dir
        )

        diff_details_result = subprocess.run(
            ["git", "diff", f"{base_branch}...HEAD"],
            capture_output=True,
            text=True,
            cwd=working_dir
        )

        diff_output = diff_details_result.stdout
        diff_lines = diff_output.split("\n")

        if len(diff_lines) > max_diff_lines:
            truncated_diff = "\n".join(diff_lines[:max_diff_lines])
            truncated_diff += f"\n\n... Output truncated. Showing {max_diff_lines} of {len(diff_lines)} lines..."
            diff_output = truncated_diff

        stats_result = subprocess.run(
            ["git", "diff", "--stat", f"{base_branch}...HEAD"],
            capture_output=True,
            text=True
        )
        
        return json.dumps({
            "base_branch": base_branch,
            "stats": stats_result.stdout,
            "total_diff_lines": len(diff_lines),
            "files_changed": files_result.stdout,
            "diff": diff_output if include_diff else "Use include_diff=true to see diff"
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_pr_templates() -> str:
    """List available PR templates with their content."""
    try:
        if not TEMPLATES_DIR.exists():
            return json.dumps({
                "error": f"Templates directory not fund: {TEMPLATES_DIR}",
                "templates": []
            })

        templates = []

        for template_file in TEMPLATES_DIR.glob("*.md"):
            try:
                content = template_file.read_text(encoding="utf-8")
                template_type = template_file.stem
                
                templates.append({
                    "filename": template_file.name,
                    "type": template_type,
                    "content": content
                })
            except Exception as e:
                templates.append({
                    "filename": template_file.name,
                    "type": template_file.stem,
                    "error": f"Coult not read template: {str(e)}"
                })

        if not templates:
            return json.dumps({
                "errors": f"No templates found in {TEMPLATES_DIR}",
                "templates": []
            })
        
        return json.dumps(templates, indent=2)
    
    except Exception as e:
        return json.dumps({"errors": str(e), "templates": []})


@mcp.tool()
async def suggest_template(changes_summary: str, change_type: str) -> str:
    """Let Claude analyze the changes and suggest the most appropriate PR template.
    
    Args:
        changes_summary: Your analysis of what the changes do
        change_type: The type of change you've identified (bug, feature, docs, refactor, test, etc.)
    """
    

    try:
        change_type_lower = change_type.lower()
        template_filename = change_type_lower + ".md"
        template_path = TEMPLATES_DIR / template_filename

        if not template_path.exists():
            template_path = TEMPLATES_DIR / "feature.md"

        template_content = template_path.read_text(encoding="utf-8")
        template_type = template_path.stem

        suggestion = {
            "recommended_template": {
                "filename": template_path.name,
                "type": template_type
            },
            "reasoning": f"Based on analysis: {changes_summary}, this appears to be a {change_type} change",
            "template_content": template_content
        }

        return json.dumps(suggestion, indent=2)
            
    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    mcp.run()
