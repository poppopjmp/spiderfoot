/**
 * spiderfoot.js
 * All the JavaScript code for the SpiderFoot aspects of the UI.
 * 
 * Author: Steve Micallef <steve@binarypool.com>
 * Created: 03/10/2012
 * Copyright: (c) Steve Micallef 2012
 * Licence: MIT
 */

import alertify from 'alertifyjs';
import 'bootstrap/dist/css/bootstrap.min.css';
import * as d3 from 'd3';
import $ from 'jquery';
import sigma from 'sigma';
import 'tablesorter';

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

  // Use sigma for data visualization
  const s = new sigma({
    graph: {
      nodes: [
        { id: 'n0', label: 'Node 0', x: 0, y: 0, size: 1, color: '#f00' },
        { id: 'n1', label: 'Node 1', x: 1, y: 1, size: 1, color: '#0f0' },
        { id: 'n2', label: 'Node 2', x: 2, y: 2, size: 1, color: '#00f' }
      ],
      edges: [
        { id: 'e0', source: 'n0', target: 'n1', color: '#ccc' },
        { id: 'e1', source: 'n1', target: 'n2', color: '#ccc' },
        { id: 'e2', source: 'n2', target: 'n0', color: '#ccc' }
      ]
    },
    container: 'sigma-container'
  });

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
    docroot + "/api/search",
    { id: scan_id, eventType: type, value: value },
    postFunc
  );
};

sf.deleteScan = function(scan_id, callback) {
    var req = $.ajax({
      type: "GET",
      url: docroot + "/api/scandelete?id=" + scan_id
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
      url: docroot + "/api/stopscan?id=" + scan_id
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

// Add a new function for geo visualization using d3
sf.geoVisualization = function (data) {
  const width = 960;
  const height = 500;

  const projection = d3.geoMercator()
    .scale(150)
    .translate([width / 2, height / 2]);

  const path = d3.geoPath().projection(projection);

  const svg = d3.select("#geo-visualization").append("svg")
    .attr("width", width)
    .attr("height", height);

  d3.json("https://d3js.org/world-50m.v1.json").then(world => {
    svg.append("path")
      .datum(topojson.feature(world, world.objects.countries))
      .attr("d", path);

    svg.selectAll(".pin")
      .data(data)
      .enter().append("circle", ".pin")
      .attr("r", 5)
      .attr("transform", d => `translate(${projection([d.longitude, d.latitude])})`);
  });
};
