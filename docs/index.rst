.. spiderfoot documentation master file, created by
   sphinx-quickstart on Sat Jun 26 01:55:34 2021.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to SpiderFoot Enterprise Documentation!
===============================================

SpiderFoot is a production-ready, enterprise-grade open source intelligence (OSINT) automation platform. Enhanced with advanced storage capabilities, AI-powered threat intelligence, and comprehensive security hardening, it integrates with hundreds of data sources and utilizes advanced methods for data analysis, making intelligence data easily navigable and actionable.

.. toctree::
   :maxdepth: 2
   :caption: Getting Started:

   overview
   PRODUCTION_READY
   README
   installation
   quickstart
   configuration

.. toctree::
   :maxdepth: 2
   :caption: Enterprise Features:

   enterprise_deployment
   advanced/enterprise_storage
   advanced/ai_threat_intelligence
   advanced/security_hardening
   advanced/performance_optimization

.. toctree::
   :maxdepth: 2
   :caption: User Guide:

   user_guide/basic_usage
   user_guide/web_interface
   user_guide/cli_usage
   user_guide/modules_guide

.. toctree::
   :maxdepth: 2
   :caption: Workflow & Advanced Features:

   workflow/getting_started
   workflow/multi_target_scanning
   workflow/correlation_analysis
   workflow/cti_reports

.. toctree::
   :maxdepth: 2
   :caption: Module Documentation:

   modules_guide
   modules/

.. toctree::
   :maxdepth: 2
   :caption: API Reference:

   api/rest_api
   python_api
   webhook_integration

.. toctree::
   :maxdepth: 2
   :caption: Advanced Topics:

   docker_deployment
   advanced/performance_optimization
   advanced/performance_tuning
   advanced/security_hardening
   security_considerations
   troubleshooting

.. toctree::
   :maxdepth: 2
   :caption: Developer Guide:

   contributing
   developer/module_development
   developer/api_development
   VERSION_MANAGEMENT
   DOCUMENTATION_BUILD
   DOCUMENTATION_FIXES
   spiderfoot

Version 5.2.3
=============

SpiderFoot 5.2.3 introduces powerful new workflow capabilities including multi-target scanning, workspace management, cross-correlation analysis, and CTI report generation with MCP integration.

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
