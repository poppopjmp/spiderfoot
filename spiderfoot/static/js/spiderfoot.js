/**
 * spiderfoot.js
 * All the JavaScript code for the SpiderFoot aspects of the UI.
 * 
 * Author: Steve Micallef <steve@binarypool.com>
 * Created: 03/10/2012
 * Copyright: (c) Steve Micallef 2012
 * Licence: MIT
 */

// Toggler for theme
document.addEventListener("DOMContentLoaded", () => {
  const themeToggler = document.getElementById("theme-toggler");
  const head = document.getElementsByTagName("HEAD")[0];
  const togglerText = document.getElementById("toggler-text");
  let link = document.createElement("link");

  if (localStorage.getItem("mode") === "Light Mode") {
    togglerText.innerText = "Dark Mode";
    document.getElementById("theme-toggler").checked = true; // ensure theme toggle is set to dark
  } else { // initial mode ist null
    togglerText.innerText = "Light Mode";
    document.getElementById("theme-toggler").checked = false; // ensure theme toggle is set to light
  }

  themeToggler.addEventListener("click", () => {
    togglerText.innerText = "Light Mode";

    if (localStorage.getItem("theme") === "dark-theme") {
      localStorage.removeItem("theme");
      localStorage.setItem("mode", "Dark Mode");
      link.rel = "stylesheet";
      link.type = "text/css";
      link.href = "${docroot}/static/css/spiderfoot.css";

      head.appendChild(link);
      location.reload();
    } else {
      localStorage.setItem("theme", "dark-theme");
      localStorage.setItem("mode", "Light Mode");
      link.rel = "stylesheet";
      link.type = "text/css";
      link.href = "${docroot}/static/css/dark.css";

      head.appendChild(link);
      location.reload();
    }
  });
});

var sf = {};

sf.replace_sfurltag = function (data) {
  if (data.toLowerCase().indexOf("&lt;sfurl&gt;") >= 0) {
    data = data.replace(
      RegExp("&lt;sfurl&gt;(.*)&lt;/sfurl&gt;", "img"),
      "<a target=_new href='$1'>$1</a>"
    );
  }
  if (data.toLowerCase().indexOf("<sfurl>") >= 0) {
    data = data.replace(
      RegExp("<sfurl>(.*)</sfurl>", "img"),
      "<a target=_new href='$1'>$1</a>"
    );
  }
  return data;
};

sf.remove_sfurltag = function (data) {
  if (data.toLowerCase().indexOf("&lt;sfurl&gt;") >= 0) {
    data = data
      .toLowerCase()
      .replace("&lt;sfurl&gt;", "")
      .replace("&lt;/sfurl&gt;", "");
  }
  if (data.toLowerCase().indexOf("<sfurl>") >= 0) {
    data = data.toLowerCase().replace("<sfurl>", "").replace("</sfurl>", "");
  }
  return data;
};

sf.search = function (scan_id, value, type, postFunc) {
  sf.fetchData(
    docroot + "/search",
    { id: scan_id, eventType: type, value: value },
    postFunc
  );
};

sf.deleteScan = function(scan_id, callback) {
    var req = $.ajax({
      type: "GET",
      url: docroot + "/scandelete?id=" + scan_id
    });
    req.done(function() {
        alertify.success('<i class="glyphicon glyphicon-ok-circle"></i> <b>Scans Deleted</b><br/><br/>' + scan_id.replace(/,/g, "<br/>"));
        sf.log("Deleted scans: " + scan_id);
        callback();
    });
    req.fail(function (hr, textStatus, errorThrown) {
        alertify.error('<i class="glyphicon glyphicon-minus-sign"></i> <b>Error</b><br/></br>' + hr.responseText);
        sf.log("Error deleting scans: " + scan_id + ": " + hr.responseText);
    });
};

sf.stopScan = function(scan_id, callback) {
    var req = $.ajax({
      type: "GET",
      url: docroot + "/stopscan?id=" + scan_id
    });
    req.done(function() {
        alertify.success('<i class="glyphicon glyphicon-ok-circle"></i> <b>Scans Aborted</b><br/><br/>' + scan_id.replace(/,/g, "<br/>"));
        sf.log("Aborted scans: " + scan_id);
        callback();
    });
    req.fail(function (hr, textStatus, errorThrown) {
        alertify.error('<i class="glyphicon glyphicon-minus-sign"></i> <b>Error</b><br/><br/>' + hr.responseText);
        sf.log("Error stopping scans: " + scan_id + ": " + hr.responseText);
    });
};

sf.fetchData = function (url, postData, postFunc) {
  var req = $.ajax({
    type: "POST",
    url: url,
    data: postData,
    cache: false,
    dataType: "json",
  });

  req.done(postFunc);
  req.fail(function (hr, status) {
      alertify.error('<i class="glyphicon glyphicon-minus-sign"></i> <b>Error</b><br/>' + status);
  });
};

sf.updateTooltips = function () {
  $(document).ready(function () {
    if ($("[rel=tooltip]").length) {
      $("[rel=tooltip]").tooltip({ container: "body" });
    }
  });
};

sf.log = function (message) {
  if (typeof console == "object" && typeof console.log == "function") {
    var currentdate = new Date();
    var pad = function (n) {
      return ("0" + n).slice(-2);
    };
    var datetime =
      currentdate.getFullYear() +
      "-" +
      pad(currentdate.getMonth() + 1) +
      "-" +
      pad(currentdate.getDate()) +
      " " +
      pad(currentdate.getHours()) +
      ":" +
      pad(currentdate.getMinutes()) +
      ":" +
      pad(currentdate.getSeconds());
    console.log("[" + datetime + "] " + message);
  }
};

// View scan logs function
function viewScanLog(scanId) {
    sf.log("Viewing scan log for: " + scanId);
    
    // Set active button
    navTo("btn-log");
    $("#modifyactions").hide();
    $("#customtabview").hide();
    $("#customvizview").hide();
    $("#btn-export").hide();
    $("#btn-download-logs").show();
    $("#loader").show();
    
    // Remove existing content
    $("#scansummary-content").remove();
    $("#scanlogs-content").remove();
    
    // Load scan logs via AJAX
    var req = $.ajax({
        type: "GET",
        url: docroot + "/scanlog?scanid=" + scanId,
        cache: false,
        dataType: "json"
    });
    
    req.done(function(data) {
        var table = "<div id='scanlogs-content'>";
        
        if (data && data.length > 0) {
            table += "<table class='table table-bordered table-striped small tablesorter'>";
            table += "<thead><tr><th>Date</th><th>Component</th><th>Type</th><th>Event</th><th>Event ID</th></tr></thead><tbody>";
            
            for (var i = 0; i < data.length; i++) {
                var row = data[i];
                table += "<tr>";
                table += "<td>" + (row[0] || '') + "</td>";
                table += "<td>" + (row[1] || '') + "</td>";
                table += "<td>" + (row[2] || '') + "</td>";
                table += "<td>" + (row[3] || '') + "</td>";
                table += "<td>" + (row[4] || '') + "</td>";
                table += "</tr>";
            }
            table += "</tbody></table>";
        } else {
            table += "<div class='alert alert-info'>No log entries found.</div>";
        }
        
        table += "</div>";
        
        $("#loader").fadeOut(500);
        $("#mainbody").append(table);
    });
    
    req.fail(function(hr, textStatus, errorThrown) {
        $("#loader").fadeOut(500);
        sf.log("Error loading scan log: " + hr.responseText);
        alertify.error('<i class="glyphicon glyphicon-minus-sign"></i> <b>Error</b><br/>Could not load scan log: ' + textStatus);
    });
}

// Scan Summary View function
function scanSummaryView(scanId) {
    sf.log("Viewing scan summary for: " + scanId);
    
    // Set active button
    navTo("btn-status");
    $("#modifyactions").hide();
    $("#customtabview").hide();
    $("#customvizview").hide();
    $("#btn-export").hide();
    $("#btn-download-logs").hide();
    $("#loader").show();
    
    // Remove existing content
    $("#scansummary-content").remove();
    $("#scanlogs-content").remove();
    
    // Load scan summary via AJAX
    var req = $.ajax({
        type: "GET",
        url: docroot + "/scansummary?id=" + scanId + "&by=type",
        cache: false,
        dataType: "json"
    });
    
    req.done(function(data) {
        var table = "<div id='scansummary-content'>";
        
        if (data && data.length > 0) {
            table += "<table class='table table-bordered table-striped small tablesorter'>";
            table += "<thead><tr><th>Event Type</th><th>Count</th></tr></thead><tbody>";
            
            for (var i = 0; i < data.length; i++) {
                var row = data[i];
                table += "<tr>";
                table += "<td>" + (row[0] || '') + "</td>";
                table += "<td>" + (row[1] || 0) + "</td>";
                table += "</tr>";
            }
            table += "</tbody></table>";
        } else {
            table += "<div class='alert alert-info'>No summary data found.</div>";
        }
        
        table += "</div>";
        
        $("#loader").fadeOut(500);
        $("#mainbody").append(table);
    });
    
    req.fail(function(hr, textStatus, errorThrown) {
        $("#loader").fadeOut(500);
        sf.log("Error loading scan summary: " + hr.responseText);
        alertify.error('<i class="glyphicon glyphicon-minus-sign"></i> <b>Error</b><br/>Could not load scan summary: ' + textStatus);
    });
}

// Browse Correlations function
function browseCorrelations(scanId) {
    sf.log("Viewing correlations for: " + scanId);
    
    // Set active button
    navTo("btn-correlations");
    $("#modifyactions").hide();
    $("#customtabview").hide();
    $("#customvizview").hide();
    $("#btn-export").hide();
    $("#btn-download-logs").hide();
    $("#loader").show();
    
    // Remove existing content
    $("#scansummary-content").remove();
    $("#scanlogs-content").remove();
    
    // Load correlations via AJAX
    var req = $.ajax({
        type: "GET",
        url: docroot + "/scancorrelations?id=" + scanId,
        cache: false,
        dataType: "json"
    });
    
    req.done(function(data) {
        var table = "<div id='scansummary-content'>";
        
        if (data && data.length > 0) {
            table += "<table class='table table-bordered table-striped small tablesorter'>";
            table += "<thead><tr><th>Rule Name</th><th>Correlation</th><th>Risk</th><th>Description</th></tr></thead><tbody>";
            
            for (var i = 0; i < data.length; i++) {
                var row = data[i];
                table += "<tr>";
                table += "<td>" + (row[0] || '') + "</td>";
                table += "<td>" + (row[1] || '') + "</td>";
                table += "<td>" + (row[2] || '') + "</td>";
                table += "<td>" + (row[3] || '') + "</td>";
                table += "</tr>";
            }
            table += "</tbody></table>";
        } else {
            table += "<div class='alert alert-info'>No correlations found.</div>";
        }
        
        table += "</div>";
        
        $("#loader").fadeOut(500);
        $("#mainbody").append(table);
    });
    
    req.fail(function(hr, textStatus, errorThrown) {
        $("#loader").fadeOut(500);
        sf.log("Error loading correlations: " + hr.responseText);
        alertify.error('<i class="glyphicon glyphicon-minus-sign"></i> <b>Error</b><br/>Could not load correlations: ' + textStatus);
    });
}

// Browse Event List function
function browseEventList(scanId) {
    sf.log("Viewing event list for: " + scanId);
    
    // Set active button
    navTo("btn-browse");
    $("#modifyactions").show();
    $("#customtabview").show();
    $("#customvizview").hide();
    $("#btn-export").show();
    $("#btn-download-logs").hide();
    $("#loader").show();
    
    // Remove existing content
    $("#scansummary-content").remove();
    $("#scanlogs-content").remove();
    
    // Load event results via AJAX
    var req = $.ajax({
        type: "GET",
        url: docroot + "/scaneventresults?id=" + scanId,
        cache: false,
        dataType: "json"
    });
    
    req.done(function(data) {
        var table = "<div id='scansummary-content'>";
        
        if (data && data.length > 0) {
            table += "<table class='table table-bordered table-striped small tablesorter'>";
            table += "<thead><tr><th>Date</th><th>Type</th><th>Value</th><th>Source</th><th>Module</th><th>Risk</th></tr></thead><tbody>";
            
            for (var i = 0; i < data.length; i++) {
                var row = data[i];
                table += "<tr>";
                table += "<td>" + (row[0] || '') + "</td>";
                table += "<td>" + (row[1] || '') + "</td>";
                table += "<td>" + (row[2] || '') + "</td>";
                table += "<td>" + (row[3] || '') + "</td>";
                table += "<td>" + (row[4] || '') + "</td>";
                table += "<td>" + (row[5] || '') + "</td>";
                table += "</tr>";
            }
            table += "</tbody></table>";
        } else {
            table += "<div class='alert alert-info'>No event results found.</div>";
        }
        
        table += "</div>";
        
        $("#loader").fadeOut(500);
        $("#mainbody").append(table);
    });
    
    req.fail(function(hr, textStatus, errorThrown) {
        $("#loader").fadeOut(500);
        sf.log("Error loading event results: " + hr.responseText);
        alertify.error('<i class="glyphicon glyphicon-minus-sign"></i> <b>Error</b><br/>Could not load event results: ' + textStatus);
    });
}

// Graph Events function
function graphEvents(scanId) {
    sf.log("Viewing graph for: " + scanId);
    
    // Set active button
    $(".btn-toolbar .btn").removeClass("active");
    $("#btn-graph").addClass("active");
    
    // For now, show a placeholder
    var graphHtml = '<div class="container-fluid"><h3>Graph View for ' + scanId + '</h3>';
    graphHtml += '<div class="alert alert-info"><strong>Info:</strong> Graph visualization is not yet implemented.</div>';
    graphHtml += '</div>';
    
    // Display in the main content area
    $("#scancontent").html(graphHtml);
}

// View Scan Config function
function viewScanConfig(scanId) {
    sf.log("Viewing scan config for: " + scanId);
    
    // Set active button
    $(".btn-toolbar .btn").removeClass("active");
    $("#btn-info").addClass("active");
    
    // Load scan config via AJAX
    var req = $.ajax({
        type: "GET",
        url: docroot + "/scanopts?id=" + scanId,
        cache: false,
        dataType: "json"
    });
    
    req.done(function(data) {
        var configHtml = '<div class="container-fluid"><h3>Scan Configuration for ' + scanId + '</h3>';
        
        if (data && data.meta) {
            configHtml += '<div class="panel panel-default"><div class="panel-heading"><h4>Scan Information</h4></div>';
            configHtml += '<div class="panel-body"><table class="table table-striped">';
            configHtml += '<tr><td><strong>Scan ID:</strong></td><td>' + (data.meta[0] || '') + '</td></tr>';
            configHtml += '<tr><td><strong>Name:</strong></td><td>' + (data.meta[1] || '') + '</td></tr>';
            configHtml += '<tr><td><strong>Target:</strong></td><td>' + (data.meta[2] || '') + '</td></tr>';
            configHtml += '<tr><td><strong>Started:</strong></td><td>' + (data.meta[3] || '') + '</td></tr>';
            configHtml += '<tr><td><strong>Finished:</strong></td><td>' + (data.meta[4] || '') + '</td></tr>';
            configHtml += '<tr><td><strong>Status:</strong></td><td>' + (data.meta[5] || '') + '</td></tr>';
            configHtml += '</table></div></div>';
        } else {
            configHtml += '<div class="alert alert-warning">No scan configuration found.</div>';
        }
        
        configHtml += '</div>';
        
        // Display in the main content area
        $("#scancontent").html(configHtml);
    });
    
    req.fail(function(hr, textStatus, errorThrown) {
        sf.log("Error loading scan config: " + hr.responseText);
        alertify.error('<i class="glyphicon glyphicon-minus-sign"></i> <b>Error</b><br/>Could not load scan config: ' + textStatus);
    });
}

// Responsive design adjustments
window.addEventListener("resize", () => {
  const width = window.innerWidth;

  if (width < 576) {
    document.body.style.fontSize = "0.6rem";
  } else if (width < 768) {
    document.body.style.fontSize = "0.7rem";
  } else if (width < 992) {
    document.body.style.fontSize = "0.8rem";
  } else if (width < 1200) {
    document.body.style.fontSize = "0.9rem";
  } else {
    document.body.style.fontSize = "1rem";
  }
});
