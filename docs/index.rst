.. spiderfoot documentation master file, created by
   sphinx-quickstart on Sat Jun 26 01:55:34 2021.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to SpiderFoot's Documentation!
=====================================

SpiderFoot is an open source intelligence (OSINT) automation tool that integrates with just about every data source available and utilizes a range of methods for data analysis, making that data easy to navigate.

.. toctree::
   :maxdepth: 2
   :caption: Getting Started:

   README
   installation
   quickstart
   configuration

.. toctree::
   :maxdepth: 2
   :caption: User Guide:

   user_guide/basic_usage
   user_guide/web_interface
   user_guide/cli_usage
   user_guide/modules
   user_guide/targets

.. toctree::
   :maxdepth: 2
   :caption: Workflow & Workspaces:

   WORKFLOW_DOCUMENTATION
   WORKSPACE_INTEGRATION_COMPLETE
   workflow/getting_started
   workflow/multi_target_scanning
   workflow/correlation_analysis
   workflow/cti_reports

.. toctree::
   :maxdepth: 2
   :caption: Module Documentation:

   modules/index
   modules/sfp_recordedfuture
   modules/custom_modules

.. toctree::
   :maxdepth: 2
   :caption: API Reference:

   api/rest_api
   api/python_api
   api/webhook_integration

.. toctree::
   :maxdepth: 2
   :caption: Advanced Topics:

   advanced/docker_deployment
   advanced/performance_tuning
   advanced/security_considerations
   advanced/troubleshooting

.. toctree::
   :maxdepth: 2
   :caption: Developer Guide:

   developer/contributing
   developer/module_development
   developer/api_development
   spiderfoot

Version 5.2.1
=============

SpiderFoot 5.2.1 introduces powerful new workflow capabilities including multi-target scanning, workspace management, cross-correlation analysis, and CTI report generation with MCP integration.

Key Features
-----------

* **Workspace Management**: Organize multiple targets and scans in logical containers
* **Multi-Target Scanning**: Run concurrent scans across multiple targets efficiently
* **Cross-Correlation Analysis**: Identify patterns and relationships across scan results
* **CTI Report Generation**: Generate comprehensive threat intelligence reports using MCP
* **Advanced API**: RESTful API for automation and integration
* **200+ Modules**: Comprehensive data collection and analysis capabilities

Release Highlights
-----------------

- **New Workflow Engine**: Complete multi-target scanning and correlation framework
- **MCP Integration**: Advanced CTI report generation with multiple export formats
- **Enhanced Web UI**: Improved workspace management and visualization
- **API Expansion**: Comprehensive REST API for all workflow operations
- **Performance Improvements**: Optimized scanning and correlation algorithms
- **Security Enhancements**: Enhanced data protection and access control
- **Documentation**: Comprehensive guides and API documentation

Quick Start
----------

.. code-block:: bash

   # Install SpiderFoot
   git clone https://github.com/poppopjmp/spiderfoot.git
   cd spiderfoot
   pip3 install -r requirements.txt
   
   # Start web interface
   python3 ./sf.py -l 127.0.0.1:5001
   
   # Create a workspace and start scanning
   python3 sfworkflow.py create-workspace "My Assessment"
   python3 sfworkflow.py add-target ws_abc123 example.com --type DOMAIN_NAME
   python3 sfworkflow.py multi-scan ws_abc123 --modules sfp_dnsresolve sfp_ssl

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
