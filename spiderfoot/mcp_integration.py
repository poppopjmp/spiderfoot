"""SpiderFoot MCP Server Integration.

This module provides integration with Model Context Protocol (MCP) servers
for CTI report generation and analysis.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

import httpx

from spiderfoot.workspace import SpiderFootWorkspace


class SpiderFootMCPClient:
    """Client for communicating with MCP servers for CTI analysis."""
    
    def __init__(self, config: dict):
        """Initialize MCP client.
        
        Args:
            config: SpiderFoot configuration including MCP settings
        """
        self.config = config
        self.log = logging.getLogger("spiderfoot.mcp")
        
        # MCP server configuration
        self.mcp_config = config.get('mcp', {})
        self.server_url = self.mcp_config.get('server_url', 'http://localhost:8000')
        self.api_key = self.mcp_config.get('api_key', '')
        self.timeout = self.mcp_config.get('timeout', 300)
        
        # CTI report templates
        self.report_templates = self._load_report_templates()
        
    def _load_report_templates(self) -> Dict[str, dict]:
        """Load CTI report templates."""
        return {
            'threat_assessment': {
                'name': 'Threat Assessment Report',
                'description': 'Comprehensive threat assessment based on OSINT findings',
                'sections': [
                    'executive_summary',
                    'threat_landscape',
                    'indicators_of_compromise',
                    'risk_assessment',
                    'recommendations'
                ]
            },
            'infrastructure_analysis': {
                'name': 'Infrastructure Analysis Report',
                'description': 'Analysis of target infrastructure and security posture',
                'sections': [
                    'infrastructure_overview',
                    'exposed_services',
                    'vulnerabilities',
                    'misconfigurations',
                    'recommendations'
                ]
            },
            'attack_surface': {
                'name': 'Attack Surface Report',
                'description': 'Complete attack surface mapping and analysis',
                'sections': [
                    'attack_surface_overview',
                    'external_exposure',
                    'data_leakage',
                    'third_party_risks',
                    'mitigation_strategies'
                ]
            }
        }
    
    async def generate_cti_report(
        self, 
        workspace: SpiderFootWorkspace,
        report_type: str = 'threat_assessment',
        custom_prompt: str = None
    ) -> Dict[str, Any]:
        """Generate CTI report using MCP server.
        
        Args:
            workspace: SpiderFoot workspace containing scan data
            report_type: Type of report to generate
            custom_prompt: Custom prompt for report generation
            
        Returns:
            Generated CTI report
        """
        try:
            self.log.info(f"Generating CTI report for workspace {workspace.workspace_id}")
            
            # Prepare workspace data for analysis
            workspace_data = await self._prepare_workspace_data(workspace)
            
            # Get report template
            template = self.report_templates.get(report_type, self.report_templates['threat_assessment'])
            
            # Prepare MCP request
            mcp_request = await self._prepare_mcp_request(
                workspace_data, template, custom_prompt
            )
            
            # Send request to MCP server
            response = await self._send_mcp_request(mcp_request)
            
            # Process and structure the response
            cti_report = await self._process_mcp_response(
                response, workspace, template, report_type
            )
            
            # Save report to workspace
            await self._save_report_to_workspace(workspace, cti_report)
            
            self.log.info(f"CTI report generated successfully for workspace {workspace.workspace_id}")
            return cti_report
            
        except Exception as e:
            self.log.error(f"Failed to generate CTI report: {e}")
            raise
    
    async def _prepare_workspace_data(self, workspace: SpiderFootWorkspace) -> Dict[str, Any]:
        """Prepare workspace data for MCP analysis.
        
        Args:
            workspace: SpiderFoot workspace
            
        Returns:
            Structured workspace data
        """
        # Export full workspace data
        workspace_export = workspace.export_data()
        
        # Analyze and categorize findings
        categorized_data = {
            'workspace_info': workspace_export['workspace_info'],
            'targets': workspace_export['targets'],
            'scans_summary': [],
            'threat_indicators': [],
            'infrastructure_data': [],
            'vulnerabilities': [],
            'exposed_services': [],
            'data_leakage': [],
            'correlations': workspace.metadata.get('correlations', [])
        }
        
        # Process each scan's results
        for scan_id, results in workspace_export['scan_results'].items():
            scan_summary = {
                'scan_id': scan_id,
                'event_count': len(results),
                'event_types': {},
                'high_risk_events': [],
                'medium_risk_events': [],
                'threat_events': []
            }
            
            # Categorize events
            for event in results:
                event_type = event['type']
                risk_level = event.get('risk', 0)
                
                # Count event types
                if event_type not in scan_summary['event_types']:
                    scan_summary['event_types'][event_type] = 0
                scan_summary['event_types'][event_type] += 1
                
                # Categorize by risk and type
                if risk_level >= 8:
                    scan_summary['high_risk_events'].append(event)
                elif risk_level >= 5:
                    scan_summary['medium_risk_events'].append(event)
                
                # Categorize specific event types
                if self._is_threat_indicator(event_type):
                    categorized_data['threat_indicators'].append(event)
                elif self._is_infrastructure_data(event_type):
                    categorized_data['infrastructure_data'].append(event)
                elif self._is_vulnerability(event_type):
                    categorized_data['vulnerabilities'].append(event)
                elif self._is_exposed_service(event_type):
                    categorized_data['exposed_services'].append(event)
                elif self._is_data_leakage(event_type):
                    categorized_data['data_leakage'].append(event)
            
            categorized_data['scans_summary'].append(scan_summary)
        
        return categorized_data
    
    def _is_threat_indicator(self, event_type: str) -> bool:
        """Check if event type is a threat indicator."""
        threat_types = [
            'MALICIOUS_IPADDR', 'MALICIOUS_INTERNET_NAME', 'BLACKLISTED_IPADDR',
            'MALICIOUS_AFFILIATE', 'THREAT_INTELLIGENCE', 'VULNERABILITY_CVE_HIGH',
            'VULNERABILITY_CVE_CRITICAL'
        ]
        return event_type in threat_types
    
    def _is_infrastructure_data(self, event_type: str) -> bool:
        """Check if event type is infrastructure data."""
        infra_types = [
            'IP_ADDRESS', 'DOMAIN_NAME', 'INTERNET_NAME', 'NETBLOCK_OWNER',
            'WEBSERVER_TECHNOLOGY', 'OPERATING_SYSTEM', 'SSL_CERTIFICATE_ISSUED'
        ]
        return event_type in infra_types
    
    def _is_vulnerability(self, event_type: str) -> bool:
        """Check if event type is a vulnerability."""
        vuln_types = [
            'VULNERABILITY_CVE_LOW', 'VULNERABILITY_CVE_MEDIUM',
            'VULNERABILITY_CVE_HIGH', 'VULNERABILITY_CVE_CRITICAL',
            'VULNERABILITY_GENERAL', 'SOFTWARE_USED'
        ]
        return event_type in vuln_types
    
    def _is_exposed_service(self, event_type: str) -> bool:
        """Check if event type is an exposed service."""
        service_types = [
            'TCP_PORT_OPEN', 'TCP_PORT_OPEN_BANNER', 'UDP_PORT_OPEN',
            'WEBSERVER_HTTPHEADERS', 'CO_HOSTED_SITE'
        ]
        return event_type in service_types
    
    def _is_data_leakage(self, event_type: str) -> bool:
        """Check if event type indicates data leakage."""
        leak_types = [
            'EMAILADDR', 'PHONE_NUMBER', 'HUMAN_NAME', 'PHYSICAL_ADDRESS',
            'ACCOUNT_EXTERNAL_OWNED', 'LEAKSITE_CONTENT', 'DARKWEB_MENTION'
        ]
        return event_type in leak_types
    
    async def _prepare_mcp_request(
        self, 
        workspace_data: Dict[str, Any], 
        template: dict,
        custom_prompt: str = None
    ) -> Dict[str, Any]:
        """Prepare MCP request payload.
        
        Args:
            workspace_data: Structured workspace data
            template: Report template
            custom_prompt: Custom prompt for analysis
            
        Returns:
            MCP request payload
        """
        # Base prompt for CTI analysis
        base_prompt = f"""
        You are a cybersecurity threat intelligence analyst. Analyze the provided OSINT data 
        and generate a comprehensive {template['name']}.
        
        The report should include the following sections:
        {', '.join(template['sections'])}
        
        Focus on:
        1. Actionable threat intelligence
        2. Risk assessment and prioritization
        3. Clear, professional language suitable for technical and management audiences
        4. Specific indicators of compromise (IOCs)
        5. Recommended security measures
        
        Data to analyze:
        """
        
        if custom_prompt:
            base_prompt = f"{base_prompt}\n\nAdditional instructions: {custom_prompt}"
        
        # Prepare the request
        mcp_request = {
            'id': str(uuid.uuid4()),
            'method': 'analyze_threat_intelligence',
            'params': {
                'prompt': base_prompt,
                'data': workspace_data,
                'report_template': template,
                'output_format': 'structured_json',
                'analysis_depth': 'comprehensive',
                'include_recommendations': True,
                'include_iocs': True
            }
        }
        
        return mcp_request
    
    async def _send_mcp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send request to MCP server.
        
        Args:
            request: MCP request payload
            
        Returns:
            MCP server response
        """
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'SpiderFoot-MCP-Client/1.0'
        }
        
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.server_url}/mcp/analyze",
                    json=request,
                    headers=headers
                )
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPError as e:
                self.log.error(f"HTTP error communicating with MCP server: {e}")
                raise
            except Exception as e:
                self.log.error(f"Error communicating with MCP server: {e}")
                raise
    
    async def _process_mcp_response(
        self, 
        response: Dict[str, Any], 
        workspace: SpiderFootWorkspace,
        template: dict,
        report_type: str
    ) -> Dict[str, Any]:
        """Process MCP server response into structured report.
        
        Args:
            response: MCP server response
            workspace: SpiderFoot workspace
            template: Report template used
            report_type: Type of report generated
            
        Returns:
            Structured CTI report
        """
        # Extract analysis result from MCP response
        if 'result' not in response:
            raise ValueError("Invalid MCP response: missing result")
        
        analysis_result = response['result']
        
        # Structure the CTI report
        cti_report = {
            'report_id': str(uuid.uuid4()),
            'workspace_id': workspace.workspace_id,
            'report_type': report_type,
            'template_used': template['name'],
            'generated_time': datetime.utcnow().isoformat(),
            'metadata': {
                'target_count': len(workspace.targets),
                'scan_count': len(workspace.scans),
                'analysis_engine': 'MCP',
                'confidence_score': analysis_result.get('confidence', 0.8)
            },
            'executive_summary': analysis_result.get('executive_summary', ''),
            'key_findings': analysis_result.get('key_findings', []),
            'threat_assessment': analysis_result.get('threat_assessment', {}),
            'risk_rating': analysis_result.get('risk_rating', 'MEDIUM'),
            'indicators_of_compromise': analysis_result.get('iocs', []),
            'recommendations': analysis_result.get('recommendations', []),
            'technical_details': analysis_result.get('technical_details', {}),
            'appendices': {
                'raw_analysis': analysis_result,
                'data_sources': self._extract_data_sources(workspace)
            }
        }
        
        return cti_report
    
    def _extract_data_sources(self, workspace: SpiderFootWorkspace) -> List[str]:
        """Extract data sources used in the workspace scans."""
        data_sources = set()
        
        # Get modules used across all scans
        for scan in workspace.scans:
            scan_id = scan['scan_id']
            scan_events = workspace.db.scanResultEvent(scan_id, 'ALL')
            
            for event in scan_events:
                module = event[3]  # Module name
                data_sources.add(module)
        
        return sorted(list(data_sources))
    
    async def _save_report_to_workspace(
        self, 
        workspace: SpiderFootWorkspace, 
        report: Dict[str, Any]
    ) -> None:
        """Save CTI report to workspace metadata.
        
        Args:
            workspace: SpiderFoot workspace
            report: Generated CTI report
        """
        if 'cti_reports' not in workspace.metadata:
            workspace.metadata['cti_reports'] = []
        
        # Add report to workspace metadata
        workspace.metadata['cti_reports'].append({
            'report_id': report['report_id'],
            'report_type': report['report_type'],
            'generated_time': report['generated_time'],
            'risk_rating': report['risk_rating'],
            'summary': report['executive_summary'][:500] + '...' if len(report['executive_summary']) > 500 else report['executive_summary']
        })
        
        # Save full report separately (could be stored in files or separate table)
        workspace.metadata[f'cti_report_{report["report_id"]}'] = report
        
        workspace.save_workspace()
        
        self.log.info(f"CTI report {report['report_id']} saved to workspace {workspace.workspace_id}")
    
    async def list_available_templates(self) -> Dict[str, dict]:
        """List available CTI report templates.
        
        Returns:
            Available report templates
        """
        return self.report_templates
    
    async def test_mcp_connection(self) -> bool:
        """Test connection to MCP server.
        
        Returns:
            True if connection successful
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.server_url}/health")
                return response.status_code == 200
        except Exception as e:
            self.log.error(f"MCP server connection test failed: {e}")
            return False


class CTIReportExporter:
    """Export CTI reports in various formats."""
    
    def __init__(self):
        self.log = logging.getLogger("spiderfoot.cti_exporter")
    
    def export_report(
        self, 
        report: Dict[str, Any], 
        format: str = 'json',
        output_path: str = None
    ) -> str:
        """Export CTI report to specified format.
        
        Args:
            report: CTI report data
            format: Export format ('json', 'pdf', 'docx', 'html')
            output_path: Output file path
            
        Returns:
            Path to exported file
        """
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"cti_report_{report['report_id']}_{timestamp}.{format}"
        
        if format == 'json':
            return self._export_json(report, output_path)
        elif format == 'html':
            return self._export_html(report, output_path)
        elif format == 'pdf':
            return self._export_pdf(report, output_path)
        elif format == 'docx':
            return self._export_docx(report, output_path)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _export_json(self, report: Dict[str, Any], output_path: str) -> str:
        """Export report as JSON."""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        return output_path
    
    def _export_html(self, report: Dict[str, Any], output_path: str) -> str:
        """Export report as HTML."""
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>{title}</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .header {{ border-bottom: 2px solid #333; padding-bottom: 20px; }}
                .section {{ margin: 30px 0; }}
                .finding {{ background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .risk-high {{ border-left: 5px solid #d32f2f; }}
                .risk-medium {{ border-left: 5px solid #f57c00; }}
                .risk-low {{ border-left: 5px solid #388e3c; }}
                .recommendations {{ background: #e3f2fd; padding: 20px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{title}</h1>
                <p><strong>Generated:</strong> {generated_time}</p>
                <p><strong>Risk Rating:</strong> {risk_rating}</p>
                <p><strong>Workspace:</strong> {workspace_id}</p>
            </div>
            
            <div class="section">
                <h2>Executive Summary</h2>
                <p>{executive_summary}</p>
            </div>
            
            <div class="section">
                <h2>Key Findings</h2>
                {key_findings}
            </div>
            
            <div class="section">
                <h2>Indicators of Compromise</h2>
                {iocs}
            </div>
            
            <div class="section recommendations">
                <h2>Recommendations</h2>
                {recommendations}
            </div>
        </body>
        </html>
        """
        
        # Format data for HTML
        key_findings_html = "<ul>"
        for finding in report.get('key_findings', []):
            key_findings_html += f"<li>{finding}</li>"
        key_findings_html += "</ul>"
        
        iocs_html = "<ul>"
        for ioc in report.get('indicators_of_compromise', []):
            iocs_html += f"<li><code>{ioc}</code></li>"
        iocs_html += "</ul>"
        
        recommendations_html = "<ul>"
        for rec in report.get('recommendations', []):
            recommendations_html += f"<li>{rec}</li>"
        recommendations_html += "</ul>"
        
        html_content = html_template.format(
            title=f"CTI Report - {report.get('report_type', 'Unknown').replace('_', ' ').title()}",
            generated_time=report.get('generated_time', ''),
            risk_rating=report.get('risk_rating', 'UNKNOWN'),
            workspace_id=report.get('workspace_id', ''),
            executive_summary=report.get('executive_summary', ''),
            key_findings=key_findings_html,
            iocs=iocs_html,
            recommendations=recommendations_html
        )
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return output_path
    
    def _export_pdf(self, report: Dict[str, Any], output_path: str) -> str:
        """Export report as PDF."""
        # This would require a PDF library like reportlab
        # For now, export as HTML and suggest conversion
        html_path = output_path.replace('.pdf', '.html')
        self._export_html(report, html_path)
        
        self.log.warning(f"PDF export not implemented. HTML version created at {html_path}")
        self.log.warning("Consider using wkhtmltopdf or similar tool to convert HTML to PDF")
        
        return html_path
    
    def _export_docx(self, report: Dict[str, Any], output_path: str) -> str:
        """Export report as DOCX."""
        # This would require python-docx library
        # For now, export as HTML
        html_path = output_path.replace('.docx', '.html')
        self._export_html(report, html_path)
        
        self.log.warning(f"DOCX export not implemented. HTML version created at {html_path}")
        self.log.warning("Consider using pandoc or python-docx to convert HTML to DOCX")
        
        return html_path
