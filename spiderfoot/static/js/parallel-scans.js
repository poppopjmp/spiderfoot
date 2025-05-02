/**
 * SpiderFoot parallel scanning functionality
 */

$(document).ready(function() {
    // Initialize multi-target scan form if present
    if ($("#multiscan-form").length) {
        initMultiScanForm();
    }
    
    // Initialize parallel scan monitor if present
    if ($("#parallel-scan-monitor").length) {
        initParallelScanMonitor();
    }
});

/**
 * Initialize the multi-target scan form
 */
function initMultiScanForm() {
    // Convert target textarea to tag input with comma as separator
    $("#scantargets").tagsInput({
        'defaultText': 'Add a target',
        'delimiter': ',',
        'height': '75px',
        'width': '100%',
        'removeWithBackspace': true,
        'placeholderColor': '#999'
    });
    
    // Handle form submission
    $("#multiscan-form").submit(function(e) {
        e.preventDefault();
        
        // Validate form
        let scanname = $("#scanname").val().trim();
        let targets = $("#scantargets").val().trim();
        
        if (!scanname) {
            alert("Please provide a scan name");
            return false;
        }
        
        if (!targets) {
            alert("Please provide at least one target");
            return false;
        }
        
        // Get selected modules or types
        let modulelist = [];
        let typelist = [];
        let usecase = "";
        
        if ($("#usecase").length && $("#usecase").val()) {
            usecase = $("#usecase").val();
        } else {
            // Get selected modules
            $("input[name='module']:checked").each(function() {
                modulelist.push($(this).val());
            });
            
            // Get selected types
            $("input[name='type']:checked").each(function() {
                typelist.push($(this).val());
            });
            
            if (modulelist.length === 0 && typelist.length === 0 && !usecase) {
                alert("Please select at least one module, type, or use case");
                return false;
            }
        }
        
        // Build form data
        let formData = {
            scanname: scanname,
            scantargets: targets,
            max_concurrent: $("#max_concurrent").val() || 3
        };
        
        if (modulelist.length > 0) {
            formData.modulelist = modulelist.join(',');
        }
        
        if (typelist.length > 0) {
            formData.typelist = typelist.join(',');
        }
        
        if (usecase) {
            formData.usecase = usecase;
        }
        
        // Show loading indicator
        $("#scan-loading").show();
        $("#scan-submit").prop('disabled', true);
        
        // Submit the form
        $.ajax({
            url: docroot + "/startscanmulti",
            type: "POST",
            data: formData,
            dataType: "json",
            success: function(data) {
                if (data[0] === "SUCCESS") {
                    // Redirect to scan info page
                    let scanIds = data[1];
                    if (scanIds.length === 1) {
                        window.location.href = docroot + "/scaninfo?id=" + scanIds[0];
                    } else {
                        window.location.href = docroot + "/scanlist?ids=" + scanIds.join(',');
                    }
                } else {
                    alert("Error starting scan: " + data[1]);
                    $("#scan-loading").hide();
                    $("#scan-submit").prop('disabled', false);
                }
            },
            error: function(xhr, status, error) {
                alert("Error starting scan: " + error);
                $("#scan-loading").hide();
                $("#scan-submit").prop('disabled', false);
            }
        });
    });
}

/**
 * Initialize the parallel scan monitor
 */
function initParallelScanMonitor() {
    // Get scan IDs from URL parameter
    let params = new URLSearchParams(window.location.search);
    let scanIds = params.get('ids') || '';
    
    if (!scanIds) {
        $("#parallel-scan-monitor").html("<p>No scan IDs specified.</p>");
        return;
    }
    
    // Start monitoring the scans
    monitorParallelScans(scanIds.split(','));
}

/**
 * Monitor parallel scans and update the UI
 */
function monitorParallelScans(scanIds) {
    if (!scanIds || scanIds.length === 0) return;
    
    let monitorInterval;
    let monitorContainer = $("#parallel-scan-monitor");
    
    // Create status table
    monitorContainer.html(`
        <h4>Parallel Scan Status</h4>
        <table class="table table-striped table-bordered">
            <thead>
                <tr>
                    <th>Scan ID</th>
                    <th>Name</th>
                    <th>Target</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody id="parallel-scan-status">
                <tr>
                    <td colspan="5" class="text-center">Loading scan status...</td>
                </tr>
            </tbody>
        </table>
    `);
    
    // Function to update scan status
    function updateScanStatus() {
        $.ajax({
            url: docroot + "/getparallelscanstatus",
            type: "GET",
            data: { ids: scanIds.join(',') },
            dataType: "json",
            success: function(data) {
                let tbody = $("#parallel-scan-status");
                tbody.empty();
                
                // Check if we received error
                if (data.error) {
                    tbody.html(`<tr><td colspan="5" class="text-danger">${data.error.message}</td></tr>`);
                    return;
                }
                
                // Process each scan
                let allComplete = true;
                let scanCount = 0;
                
                for (let scanId in data) {
                    scanCount++;
                    let scan = data[scanId];
                    let status = scan.status || "UNKNOWN";
                    
                    // Check if any scans are still running
                    if (status === "RUNNING" || status === "STARTING" || status === "STARTED") {
                        allComplete = false;
                    }
                    
                    // Status class
                    let statusClass = "badge-secondary";
                    if (status === "FINISHED") statusClass = "badge-success";
                    if (status === "RUNNING" || status === "STARTED") statusClass = "badge-primary";
                    if (status === "STARTING") statusClass = "badge-info";
                    if (status === "ABORTED" || status === "ABORT-REQUESTED") statusClass = "badge-warning";
                    if (status === "FAILED" || status.startsWith("ERROR")) statusClass = "badge-danger";
                    
                    // Actions
                    let actions = `<a href="${docroot}/scaninfo?id=${scanId}" class="btn btn-sm btn-info">View</a>`;
                    
                    if (status === "RUNNING" || status === "STARTING" || status === "STARTED") {
                        actions += ` <button class="btn btn-sm btn-danger stop-scan-btn" data-id="${scanId}">Stop</button>`;
                    }
                    
                    // Add row
                    tbody.append(`
                        <tr data-id="${scanId}">
                            <td><small>${scanId}</small></td>
                            <td>${scan.name || ""}</td>
                            <td>${scan.target || ""}</td>
                            <td><span class="badge ${statusClass}">${status}</span></td>
                            <td>${actions}</td>
                        </tr>
                    `);
                }
                
                // If no scans found
                if (scanCount === 0) {
                    tbody.html(`<tr><td colspan="5" class="text-center">No scan data found.</td></tr>`);
                }
                
                // If all scans are complete, stop monitoring
                if (allComplete) {
                    clearInterval(monitorInterval);
                }
                
                // Setup stop scan buttons
                $(".stop-scan-btn").click(function() {
                    let scanId = $(this).data("id");
                    stopScan(scanId);
                });
            },
            error: function(xhr, status, error) {
                console.error("Error fetching scan status:", error);
                $("#parallel-scan-status").html(`
                    <tr>
                        <td colspan="5" class="text-danger">Error fetching scan status: ${error}</td>
                    </tr>
                `);
            }
        });
    }
    
    // Function to stop a scan
    function stopScan(scanId) {
        if (confirm("Are you sure you want to stop this scan?")) {
            $.ajax({
                url: docroot + "/stopscan",
                type: "POST",
                data: { id: scanId },
                dataType: "json",
                success: function(data) {
                    if (data.success) {
                        // Update UI to show stopping
                        $(`tr[data-id="${scanId}"] td:nth-child(4)`).html(
                            '<span class="badge badge-warning">STOPPING</span>'
                        );
                        // Disable the button
                        $(`tr[data-id="${scanId}"] .stop-scan-btn`).prop('disabled', true);
                    } else {
                        alert("Failed to stop scan: " + (data.message || "Unknown error"));
                    }
                },
                error: function(xhr, status, error) {
                    alert("Error stopping scan: " + error);
                }
            });
        }
    }
    
    // Update immediately then set interval
    updateScanStatus();
    monitorInterval = setInterval(updateScanStatus, 3000);
}
