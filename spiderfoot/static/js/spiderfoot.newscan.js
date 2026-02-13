    tabs = [ "use", "type", "module" ];
    activeTab = "use";

    function submitForm() {
        list = "";
        
        // Handle different tab types
        if (activeTab === "use") {
            // For use case tab, get the selected radio button value
            var selectedUsecase = $("input[name='usecase']:checked").val();
            // The usecase is handled by the radio button, no need to set a hidden field
            return;
        } else {
            // For module and type tabs, collect checked items
            $("[id^="+activeTab+"_]").each(function() {
                if ($(this).is(":checked")) {
                    var elementId = $(this).attr('id');
                    // For module tab, strip the 'module_' prefix to get actual module name
                    if (activeTab === "module") {
                        elementId = elementId.replace(/^module_/, '');
                    }
                    list += elementId + ",";
                }
            });
            
            $("#"+activeTab+"list").val(list);
            
            // Clear other lists
            for (i = 0; i < tabs.length; i++) {
                if (tabs[i] != activeTab && tabs[i] != "use") {
                    $("#"+tabs[i]+"list").val("");
                }
            }
        }
    }

    function switchTab(tabname) {
        $("#"+activeTab+"table").hide();
        $("#"+activeTab+"tab").removeClass("active");
        $("#"+tabname+"table").show();
        $("#"+tabname+"tab").addClass("active");
        activeTab = tabname;
        if (activeTab == "use") {
            $("#selectors").hide();
        } else {
            $("#selectors").show();
        }
    }

    function selectAll() {
        $("[id^="+activeTab+"_]").prop("checked", true);
    }

    function deselectAll() {
        $("[id^="+activeTab+"_]").prop("checked", false);
    }

    function checkInteractiveModules() {
        var interactiveChecked = [];
        $("tr.sf-interactive-module input[type=checkbox]:checked").each(function() {
            var modId = $(this).attr('id').replace('module_', '');
            var modName = $(this).closest('tr').find('td:nth-child(2)').text().trim();
            interactiveChecked.push(modName);
        });

        var $banner = $('#interactive-warning');
        if (interactiveChecked.length > 0) {
            var names = interactiveChecked.join(', ');
            $banner.html(
                '<div class="alert alert-warning" style="margin-top: 10px; font-size: 12px;">' +
                '<i class="glyphicon glyphicon-hand-up"></i>&nbsp;&nbsp;<strong>Interactive modules selected:</strong> ' +
                names + '<br>' +
                '<small>These modules require user interaction (e.g. file upload) during each scan run. ' +
                'You can upload documents via <a href="' + docroot + '/enrichment">Document Upload</a> while the scan is running.</small>' +
                '</div>'
            );
            $banner.show();
        } else {
            $banner.hide();
        }
    }

$(document).ready(function() {
    $("#usetab").click(function() { switchTab("use"); });
    $("#typetab").click(function() { switchTab("type"); });
    $("#moduletab").click(function() { switchTab("module"); });
    $("#btn-select-all").click(function() { selectAll(); checkInteractiveModules(); });
    $("#btn-deselect-all").click(function() { deselectAll(); checkInteractiveModules(); });
    
    // Monitor interactive module checkbox changes
    $(document).on('change', 'tr.sf-interactive-module input[type=checkbox]', function() {
        checkInteractiveModules();
    });

    // Handle form submission to ensure JavaScript runs before submit
    $("#btn-run-scan").click(function(e) { 
        e.preventDefault();
        submitForm(); 
        // Submit the form after processing
        $(this).closest('form').submit();
    });
    
    // Also handle direct form submission
    $('form').submit(function(e) {
        submitForm();
    });

    $('#scantarget').popover({ 'html': true, 'animation': true, 'trigger': 'focus'});

    // Initial check for interactive modules
    checkInteractiveModules();
});
