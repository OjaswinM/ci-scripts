#!/usr/bin/env python3
"""
NGCI HTML Dashboard Generator

Generates a standalone HTML dashboard from ngci test output directory.
Usage: ./generate_dashboard.py <test-output-dir> [output.html]
"""

import os
import sys
import re
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import html


class ANSIConverter:
    """Convert ANSI color codes to HTML spans"""
    
    ANSI_COLORS = {
        '30': 'black', '31': 'red', '32': 'green', '33': 'yellow',
        '34': 'blue', '35': 'magenta', '36': 'cyan', '37': 'white',
        '90': 'bright-black', '91': 'bright-red', '92': 'bright-green',
        '93': 'bright-yellow', '94': 'bright-blue', '95': 'bright-magenta',
        '96': 'bright-cyan', '97': 'bright-white'
    }
    
    @staticmethod
    def convert(text: str) -> str:
        """Convert ANSI escape codes to HTML spans with CSS classes"""
        # Escape HTML first
        text = html.escape(text)
        
        # Pattern for ANSI codes: \033[XXm or \x1b[XXm
        pattern = r'\x1b\[(\d+)m'
        
        def replace_ansi(match):
            code = match.group(1)
            if code == '0':  # Reset
                return '</span>'
            elif code in ANSIConverter.ANSI_COLORS:
                color = ANSIConverter.ANSI_COLORS[code]
                return f'<span class="ansi-{color}">'
            return ''
        
        result = re.sub(pattern, replace_ansi, text)
        
        # Close any unclosed spans
        open_spans = result.count('<span')
        close_spans = result.count('</span>')
        if open_spans > close_spans:
            result += '</span>' * (open_spans - close_spans)
        
        return result


class LogParser:
    """Parse various log formats"""
    
    @staticmethod
    def parse_main_log(log_path: Path) -> Dict:
        """Parse the main test log"""
        if not log_path.exists():
            return {
                'content': '',
                'status': 'unknown',
                'metadata': {}
            }
        
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        # Extract metadata
        metadata = {}
        
        # Source path
        src_match = re.search(r'src:\s+(.+)', content)
        if src_match:
            metadata['source'] = src_match.group(1).strip()
        
        # Git commit
        linux_match = re.search(r'linux:\s+(.+)', content)
        if linux_match:
            metadata['commit'] = linux_match.group(1).strip()
        
        # Output path
        output_match = re.search(r'output:\s+(.+)', content)
        if output_match:
            metadata['output'] = output_match.group(1).strip()
        
        # Parallelism factors
        jfactor_match = re.search(r'jfactor:\s+(\d+)', content)
        if jfactor_match:
            metadata['jfactor'] = int(jfactor_match.group(1))
        
        # Duration
        duration_match = re.search(r'Completed .+ in (\d+):(\d+):(\d+)\.(\d+)', content)
        if duration_match:
            hours = int(duration_match.group(1))
            minutes = int(duration_match.group(2))
            seconds = int(duration_match.group(3))
            metadata['duration'] = timedelta(hours=hours, minutes=minutes, seconds=seconds)
        
        # Status
        if 'OK' in content and '# OK' in content:
            status = 'success'
        elif 'Failed' in content or '! Failed' in content:
            status = 'failed'
        else:
            status = 'unknown'
        
        return {
            'content': content,
            'status': status,
            'metadata': metadata
        }
    
    @staticmethod
    def parse_build_log(log_path: Path) -> Dict:
        """Parse a build log"""
        if not log_path.exists():
            return {
                'content': '',
                'status': 'unknown',
                'metadata': {}
            }
        
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        metadata = {}
        
        # Extract version
        version_match = re.search(r'## VERSION\s+=\s+(.+)', content)
        if version_match:
            metadata['version'] = version_match.group(1).strip()
        
        # Extract architecture
        arch_match = re.search(r'## ARCH\s+=\s+(.+)', content)
        if arch_match:
            metadata['arch'] = arch_match.group(1).strip()
        
        # Extract compiler
        gcc_match = re.search(r'## gcc\s+=\s+(.+)', content)
        if gcc_match:
            metadata['compiler'] = gcc_match.group(1).strip()
        
        # Extract defconfig
        defconfig_match = re.search(r'## DEFCONFIG\s+=\s+(.+)', content)
        if defconfig_match:
            metadata['defconfig'] = defconfig_match.group(1).strip()
        
        # Status
        if '## Build completed OK' in content:
            status = 'success'
        elif 'error:' in content.lower() or 'failed' in content.lower():
            status = 'failed'
        else:
            status = 'unknown'
        
        return {
            'content': content,
            'status': status,
            'metadata': metadata
        }
    
    @staticmethod
    def parse_boot_log(log_path: Path) -> Dict:
        """Parse a boot log"""
        if not log_path.exists():
            return {
                'content': '',
                'status': 'unknown',
                'error': None
            }
        
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        # Check for errors
        error = None
        if 'Traceback' in content:
            # Extract traceback
            traceback_match = re.search(r'(Traceback.*?)(?=\n\n|\Z)', content, re.DOTALL)
            if traceback_match:
                error = traceback_match.group(1).strip()
        elif 'ExceptionPexpect' in content:
            # Extract exception message
            exception_match = re.search(r'(pexpect\.exceptions\..+)', content)
            if exception_match:
                error = exception_match.group(1).strip()
        
        status = 'failed' if error else 'success'
        
        return {
            'content': content,
            'status': status,
            'error': error
        }


class MetadataExtractor:
    """Extract metadata from directory structure and logs"""
    
    @staticmethod
    def extract_build_info(build_dir: Path) -> List[Dict]:
        """Extract build information from build directory"""
        builds = []
        
        if not build_dir.exists():
            return builds
        
        for config_dir in build_dir.iterdir():
            if not config_dir.is_dir():
                continue
            
            # Parse directory name: <config>@<arch>@<distro>
            parts = config_dir.name.split('@')
            if len(parts) >= 3:
                config_name = parts[0]
                arch = parts[1]
                distro = parts[2]
            else:
                config_name = config_dir.name
                arch = 'unknown'
                distro = 'unknown'
            
            log_path = config_dir / 'log.txt'
            log_data = LogParser.parse_build_log(log_path)
            
            builds.append({
                'config': config_name,
                'arch': arch,
                'distro': distro,
                'status': log_data['status'],
                'metadata': log_data['metadata'],
                'log_content': log_data['content'],
                'log_path': str(log_path.relative_to(build_dir.parent.parent))
            })
        
        return builds
    
    @staticmethod
    def extract_boot_info(boot_dir: Path) -> List[Dict]:
        """Extract boot information from boot directory"""
        boots = []
        
        if not boot_dir.exists():
            return boots
        
        for platform_dir in boot_dir.iterdir():
            if not platform_dir.is_dir():
                continue
            
            # Parse directory name: <platform>@<qemu-ver>@<config>@<distro>
            parts = platform_dir.name.split('@')
            if len(parts) >= 4:
                platform = parts[0]
                qemu_version = parts[1]
                config = parts[2]
                distro = parts[3]
            else:
                platform = platform_dir.name
                qemu_version = 'unknown'
                config = 'unknown'
                distro = 'unknown'
            
            log_path = platform_dir / 'log.txt'
            log_data = LogParser.parse_boot_log(log_path)
            
            boots.append({
                'platform': platform,
                'qemu_version': qemu_version,
                'config': config,
                'distro': distro,
                'status': log_data['status'],
                'error': log_data['error'],
                'log_content': log_data['content'],
                'log_path': str(log_path.relative_to(boot_dir.parent.parent))
            })
        
        return boots
    
    @staticmethod
    def extract_errors(test_data: Dict) -> List[Dict]:
        """Extract all errors from test data"""
        errors = []
        
        # Check main log
        main_log = test_data.get('main_log', {}).get('content', '')
        if 'Failed' in main_log or '! Failed' in main_log:
            errors.append({
                'source': 'main',
                'component': 'Test Run',
                'message': 'Test run failed',
                'details': None
            })
        
        # Check builds
        for build in test_data.get('builds', []):
            if build['status'] == 'failed':
                errors.append({
                    'source': 'build',
                    'component': f"{build['config']}@{build['arch']}@{build['distro']}",
                    'message': 'Build failed',
                    'details': None
                })
        
        # Check boots
        for boot in test_data.get('boots', []):
            if boot['status'] == 'failed':
                errors.append({
                    'source': 'boot',
                    'component': f"{boot['platform']}@{boot['qemu_version']}",
                    'message': boot.get('error', 'Boot failed'),
                    'details': boot.get('error')
                })
        
        return errors


class HTMLGenerator:
    """Generate the final HTML dashboard"""
    
    @staticmethod
    def generate_css() -> str:
        """Generate embedded CSS"""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }
        
        #dashboard {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        /* Header */
        .header {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        
        .header h1 {
            font-size: 2em;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .status-badge {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.5em;
            font-weight: bold;
            text-transform: uppercase;
        }
        
        .status-badge.success {
            background: #28a745;
            color: white;
        }
        
        .status-badge.failed {
            background: #dc3545;
            color: white;
        }
        
        .status-badge.unknown {
            background: #6c757d;
            color: white;
        }
        
        .header-meta {
            color: #666;
            font-size: 0.9em;
            margin-top: 10px;
        }
        
        .header-meta div {
            margin: 5px 0;
        }
        
        /* Summary Cards */
        .summary-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .card {
            background: white;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .card h3 {
            font-size: 0.9em;
            color: #666;
            text-transform: uppercase;
            margin-bottom: 10px;
        }
        
        .card .value {
            font-size: 2em;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .card .subtext {
            font-size: 0.85em;
            color: #666;
        }
        
        .card.success .value {
            color: #28a745;
        }
        
        .card.failed .value {
            color: #dc3545;
        }
        
        .card.warning .value {
            color: #ffc107;
        }
        
        /* Quick Navigation */
        .quick-nav {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        .quick-nav button {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            background: #007bff;
            color: white;
            cursor: pointer;
            font-size: 0.9em;
            transition: background 0.3s;
        }
        
        .quick-nav button:hover {
            background: #0056b3;
        }
        
        /* Section */
        .section {
            background: white;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        
        .section h2 {
            font-size: 1.5em;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #f0f0f0;
        }
        
        /* Result Item */
        .result-item {
            border: 1px solid #e0e0e0;
            border-radius: 5px;
            margin-bottom: 15px;
            overflow: hidden;
        }
        
        .result-header {
            padding: 15px;
            background: #f8f9fa;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 15px;
            transition: background 0.3s;
        }
        
        .result-header:hover {
            background: #e9ecef;
        }
        
        .result-icon {
            font-size: 1.5em;
            font-weight: bold;
        }
        
        .result-icon.success {
            color: #28a745;
        }
        
        .result-icon.failed {
            color: #dc3545;
        }
        
        .result-title {
            flex: 1;
            font-weight: 500;
        }
        
        .result-meta {
            font-size: 0.85em;
            color: #666;
        }
        
        .result-content {
            padding: 20px;
            background: #f8f9fa;
            border-top: 1px solid #e0e0e0;
            display: none;
        }
        
        .result-content.expanded {
            display: block;
        }
        
        .error-message {
            background: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 5px;
            padding: 15px;
            margin-bottom: 15px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        
        /* Log Viewer */
        .log-viewer {
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 20px;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            overflow-x: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
            max-height: 600px;
            overflow-y: auto;
        }
        
        /* ANSI Colors */
        .ansi-black { color: #000000; }
        .ansi-red { color: #cd3131; }
        .ansi-green { color: #0dbc79; }
        .ansi-yellow { color: #e5e510; }
        .ansi-blue { color: #2472c8; }
        .ansi-magenta { color: #bc3fbc; }
        .ansi-cyan { color: #11a8cd; }
        .ansi-white { color: #e5e5e5; }
        .ansi-bright-black { color: #666666; }
        .ansi-bright-red { color: #f14c4c; }
        .ansi-bright-green { color: #23d18b; }
        .ansi-bright-yellow { color: #f5f543; }
        .ansi-bright-blue { color: #3b8eea; }
        .ansi-bright-magenta { color: #d670d6; }
        .ansi-bright-cyan { color: #29b8db; }
        .ansi-bright-white { color: #ffffff; }
        
        /* Buttons */
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9em;
            transition: all 0.3s;
        }
        
        .btn-primary {
            background: #007bff;
            color: white;
        }
        
        .btn-primary:hover {
            background: #0056b3;
        }
        
        .btn-secondary {
            background: #6c757d;
            color: white;
        }
        
        .btn-secondary:hover {
            background: #545b62;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .summary-cards {
                grid-template-columns: 1fr;
            }
            
            .quick-nav {
                flex-direction: column;
            }
            
            .quick-nav button {
                width: 100%;
            }
        }
        
        /* Highlight animation */
        @keyframes highlight {
            0% { background: #fff3cd; }
            100% { background: transparent; }
        }
        
        .highlight-flash {
            animation: highlight 2s ease-out;
        }
        """
    
    @staticmethod
    def generate_javascript(test_data: Dict) -> str:
        """Generate embedded JavaScript"""
        return f"""
        // Dashboard data
        const dashboardData = {json.dumps(test_data, default=str, indent=2)};
        
        // Toggle log visibility
        function toggleLog(elementId) {{
            const content = document.getElementById(elementId);
            if (content) {{
                content.classList.toggle('expanded');
            }}
        }}
        
        // Jump to section
        function jumpToSection(sectionId) {{
            const section = document.getElementById(sectionId);
            if (section) {{
                section.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
            }}
        }}
        
        // Jump to first error
        function jumpToFirstError() {{
            const errorElements = document.querySelectorAll('.result-item.failed');
            if (errorElements.length > 0) {{
                errorElements[0].scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                errorElements[0].classList.add('highlight-flash');
                setTimeout(() => {{
                    errorElements[0].classList.remove('highlight-flash');
                }}, 2000);
            }}
        }}
        
        // Expand all logs
        function expandAll() {{
            document.querySelectorAll('.result-content').forEach(el => {{
                el.classList.add('expanded');
            }});
        }}
        
        // Collapse all logs
        function collapseAll() {{
            document.querySelectorAll('.result-content').forEach(el => {{
                el.classList.remove('expanded');
            }});
        }}
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {{
            console.log('NGCI Dashboard loaded');
            console.log('Test data:', dashboardData);
        }});
        """
    
    @staticmethod
    def generate_html(test_data: Dict) -> str:
        """Generate complete HTML dashboard"""
        test_name = test_data['name']
        status = test_data['status']
        main_log = test_data.get('main_log', {})
        metadata = main_log.get('metadata', {})
        builds = test_data.get('builds', [])
        boots = test_data.get('boots', [])
        errors = test_data.get('errors', [])
        
        # Calculate statistics
        builds_success = sum(1 for b in builds if b['status'] == 'success')
        builds_total = len(builds)
        boots_success = sum(1 for b in boots if b['status'] == 'success')
        boots_total = len(boots)
        
        duration_str = str(metadata.get('duration', 'Unknown'))
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NGCI Dashboard - {test_name}</title>
    <style>
        {HTMLGenerator.generate_css()}
    </style>
</head>
<body>
    <div id="dashboard">
        <!-- Header -->
        <div class="header">
            <h1>{test_name}</h1>
            <div class="header-meta">
                <div><strong>Source:</strong> {metadata.get('source', 'Unknown')}</div>
                <div><strong>Commit:</strong> {metadata.get('commit', 'Unknown')}</div>
                <div><strong>Duration:</strong> {duration_str}</div>
            </div>
        </div>
        
        <!-- Summary Cards -->
        <div class="summary-cards">
            <div class="card {'success' if builds_success == builds_total else 'failed' if builds_success == 0 else 'warning'}">
                <h3>Builds</h3>
                <div class="value">{builds_success}/{builds_total}</div>
                <div class="subtext">{'All passed' if builds_success == builds_total else f'{builds_total - builds_success} failed'}</div>
            </div>
            
            <div class="card {'success' if boots_success == boots_total else 'failed' if boots_success == 0 else 'warning'}">
                <h3>Boots</h3>
                <div class="value">{boots_success}/{boots_total}</div>
                <div class="subtext">{'All passed' if boots_success == boots_total else f'{boots_total - boots_success} failed'}</div>
            </div>
            
            <div class="card">
                <h3>Duration</h3>
                <div class="value">{duration_str}</div>
                <div class="subtext">Total test time</div>
            </div>
            
            <div class="card {'failed' if len(errors) > 0 else 'success'}">
                <h3>Errors</h3>
                <div class="value">{len(errors)}</div>
                <div class="subtext">{'Issues found' if len(errors) > 0 else 'No errors'}</div>
            </div>
        </div>
        
        <!-- Quick Navigation -->
        <div class="quick-nav">
            <button onclick="jumpToFirstError()">Jump to First Error</button>
            <button onclick="jumpToSection('builds-section')">Build Logs</button>
            <button onclick="jumpToSection('boots-section')">Boot Logs</button>
            <button onclick="jumpToSection('main-log-section')">Full Log</button>
            <button onclick="expandAll()">Expand All</button>
            <button onclick="collapseAll()">Collapse All</button>
        </div>
"""
        
        # Build Results Section
        if builds:
            html_content += """
        <!-- Build Results -->
        <div class="section" id="builds-section">
            <h2>Build Results</h2>
"""
            for i, build in enumerate(builds):
                icon = '✓' if build['status'] == 'success' else '✗'
                status_class = build['status']
                config_full = f"{build['config']}@{build['arch']}@{build['distro']}"
                
                html_content += f"""
            <div class="result-item {status_class}">
                <div class="result-header" onclick="toggleLog('build-log-{i}')">
                    <span class="result-icon {status_class}">{icon}</span>
                    <div class="result-title">{config_full}</div>
                    <div class="result-meta">
                        {build['metadata'].get('compiler', 'Unknown compiler')}
                    </div>
                </div>
                <div class="result-content" id="build-log-{i}">
                    <div class="log-viewer">{ANSIConverter.convert(build['log_content'])}</div>
                </div>
            </div>
"""
            html_content += """
        </div>
"""
        
        # Boot Results Section
        if boots:
            html_content += """
        <!-- Boot Results -->
        <div class="section" id="boots-section">
            <h2>Boot Results</h2>
"""
            for i, boot in enumerate(boots):
                icon = '✓' if boot['status'] == 'success' else '✗'
                status_class = boot['status']
                platform_full = f"{boot['platform']}@{boot['qemu_version']}"
                
                html_content += f"""
            <div class="result-item {status_class}">
                <div class="result-header" onclick="toggleLog('boot-log-{i}')">
                    <span class="result-icon {status_class}">{icon}</span>
                    <div class="result-title">{platform_full}</div>
                    <div class="result-meta">
                        Config: {boot['config']}@{boot['distro']}
                    </div>
                </div>
                <div class="result-content" id="boot-log-{i}">
"""
                if boot.get('error'):
                    html_content += f"""
                    <div class="error-message">{html.escape(boot['error'])}</div>
"""
                html_content += f"""
                    <div class="log-viewer">{ANSIConverter.convert(boot['log_content'])}</div>
                </div>
            </div>
"""
            html_content += """
        </div>
"""
        
        # Main Log Section
        html_content += f"""
        <!-- Main Test Log -->
        <div class="section" id="main-log-section">
            <h2>Full Test Log</h2>
            <div class="log-viewer">{ANSIConverter.convert(main_log.get('content', ''))}</div>
        </div>
    </div>
    
    <script>
        {HTMLGenerator.generate_javascript(test_data)}
    </script>
</body>
</html>
"""
        
        return html_content


class DashboardGenerator:
    """Main orchestrator"""
    
    def __init__(self, test_dir: Path):
        self.test_dir = test_dir
        self.test_name = test_dir.name
    
    def generate(self) -> Dict:
        """Generate dashboard data"""
        print(f"Analyzing test output: {self.test_dir}")
        
        # Parse main log
        main_log_path = self.test_dir / 'log'
        main_log = LogParser.parse_main_log(main_log_path)
        
        # Extract build information
        build_dir = self.test_dir / 'build'
        builds = MetadataExtractor.extract_build_info(build_dir)
        print(f"Found {len(builds)} builds")
        
        # Extract boot information
        boot_dir = self.test_dir / 'boot'
        boots = MetadataExtractor.extract_boot_info(boot_dir)
        print(f"Found {len(boots)} boots")
        
        # Compile test data
        test_data = {
            'name': self.test_name,
            'status': main_log['status'],
            'main_log': main_log,
            'builds': builds,
            'boots': boots
        }
        
        # Extract errors
        errors = MetadataExtractor.extract_errors(test_data)
        test_data['errors'] = errors
        print(f"Found {len(errors)} errors")
        
        return test_data
    
    def generate_html(self, output_path: Path) -> None:
        """Generate HTML dashboard file"""
        test_data = self.generate()
        
        print(f"Generating HTML dashboard...")
        html_content = HTMLGenerator.generate_html(test_data)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"Dashboard generated: {output_path}")
        print(f"File size: {output_path.stat().st_size / 1024:.2f} KB")


def main():
    if len(sys.argv) < 2:
        print("Usage: ./generate_dashboard.py <test-output-dir> [output.html]")
        print("\nExample:")
        print("  ./generate_dashboard.py minimal-qemu/ dashboard.html")
        sys.exit(1)
    
    test_dir = Path(sys.argv[1])
    if not test_dir.exists():
        print(f"Error: Directory not found: {test_dir}")
        sys.exit(1)
    
    if not test_dir.is_dir():
        print(f"Error: Not a directory: {test_dir}")
        sys.exit(1)
    
    # Determine output path
    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        output_path = test_dir / "dashboard.html"
    
    # Generate dashboard
    generator = DashboardGenerator(test_dir)
    generator.generate_html(output_path)
    
    print(f"\n✓ Success! Open the dashboard with:")
    print(f"  firefox {output_path}")


if __name__ == '__main__':
    main()
