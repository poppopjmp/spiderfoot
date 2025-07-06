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

$(document).ready(function() {
    $("#usetab").click(function() { switchTab("use"); });
    $("#typetab").click(function() { switchTab("type"); });
    $("#moduletab").click(function() { switchTab("module"); });
    $("#btn-select-all").click(function() { selectAll(); });
    $("#btn-deselect-all").click(function() { deselectAll(); });
    
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
});
