activeTab = "global";
function saveSettings() {
    var retarr = {}
    $(":input").each(function(i) {
        retarr[$(this).attr('id')] = $(this).val();
    });

    $("#allopts").val(JSON.stringify(retarr));
}

function clearSettings() {
    $("#allopts").val("RESET");
}

function switchTab(tab) {
    $("#optsect_"+activeTab).hide();
    $("#optsect_"+tab).show();
    $("#tab_"+activeTab).removeClass("active");
    $("#tab_"+tab).addClass("active");
    activeTab = tab;
}

function getFile(elemId) {
   var elem = document.getElementById(elemId);
   if(elem && document.createEvent) {
      var evt = document.createEvent("MouseEvents");
      evt.initEvent("click", true, false);
      elem.dispatchEvent(evt);
   }
}

$(document).ready(function() {
  $("#btn-save-changes").click(function() { saveSettings(); });
  $("#btn-import-config").click(function() { getFile("configFile"); return false; });
  $("#btn-reset-settings").click(function() { clearSettings(); });
  $("#btn-opt-export").click(function() { window.location.href=docroot + "/optsexport?pattern=api_key"; return false; });
  $("#tab_global").click(function() { switchTab("global"); });
});

$(function () {
  $('[data-toggle="popover"]').popover()
  $('[data-toggle="popover"]').on("show.bs.popover", function() { $(this).data("bs.popover").tip().css("max-width", "600px") });
});

document.addEventListener('DOMContentLoaded', function () {
    var form = document.getElementById('savesettingsform');
    if (!form) return;

    form.addEventListener('submit', function (e) {
        // Collect all input and select values
        var opts = {};
        var elements = form.querySelectorAll('input, select');
        elements.forEach(function (el) {
            if (!el.id || el.id === 'allopts' || el.id === 'token' || el.type === 'file') return;
            if (el.type === 'checkbox') {
                opts[el.id] = el.checked;
            } else if (el.tagName.toLowerCase() === 'select') {
                // For bool selects, convert to boolean
                if (el.options.length === 2 &&
                    el.options[0].value === "1" && el.options[1].value === "0") {
                    opts[el.id] = el.value === "1";
                } else {
                    opts[el.id] = el.value;
                }
            } else {
                opts[el.id] = el.value;
            }
        });
        // Set the JSON string to the hidden allopts field
        document.getElementById('allopts').value = JSON.stringify(opts);
    });

    // Optional: handle reset button to set allopts to "RESET"
    var resetBtn = document.getElementById('btn-reset-settings');
    if (resetBtn) {
        resetBtn.addEventListener('click', function (e) {
            e.preventDefault();
            document.getElementById('allopts').value = "RESET";
            form.submit();
        });
    }
});
