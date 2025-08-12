$(document).ready(function () {
  const charts = {}; // Chart instances

  $("#generate-report").on("click", function () {
    updateAllCharts();
  });

  function updateAllCharts() {
    $("#reports-container").empty();
    const start_date = $("#start-date").val();
    const end_date = $("#end-date").val();

    if (!start_date || !end_date) {
      alert("Please select both start and end dates.");
      return;
    }

    console.log("Updating charts with:", start_date, end_date);

    fetchAndUpdateChart(
      "attendance",
      "/api/attendance_report",
      start_date,
      end_date
    );
    fetchAndUpdateChart("payroll", "/api/payroll_report", start_date, end_date);
    fetchAndUpdateChart(
      "performance",
      "/api/performance_report",
      start_date,
      end_date
    );
    fetchAndUpdateChart(
      "productivity",
      "/api/productivity_report",
      start_date,
      end_date
    );
  }

  function fetchAndUpdateChart(type, url, start, end) {
    const token = sessionStorage.getItem("adminToken");

    if (!token) {
      console.error("No adminToken found in sessionStorage.");
      return;
    }

    $.ajax({
      url: url,
      method: "GET",
      data: { start_date: start, end_date: end },
      beforeSend: function (xhr) {
        xhr.setRequestHeader("Authorization", "Bearer " + token);
      },
      success: function (response) {
        updateChart(type, response);
      },
      error: function (xhr) {
        console.error(`Error loading ${type} report:`, xhr.responseText);
      },
    });
  }

  function createChartCard(reportType, canvasId) {
    const titleMap = {
      attendance: "Attendance Report",
      payroll: "Payroll Report",
      performance: "Performance Report",
      productivity: "Productivity Report",
    };

    return `
    <div class="col-md-6 grid-margin stretch-card">
      <div class="card" style="height: 350px;"> <!-- fix card height -->
        <div class="card-body" style="height: 100%; display: flex; flex-direction: column;">
          <h5 class="card-title">${titleMap[reportType]}</h5>
          <canvas id="${canvasId}" style="flex-grow: 1;"></canvas>
        </div>
      </div>
    </div>
  `;
  }

  function updateChart(type, data) {
    const chartIdMap = {
      attendance: "areaChart",
      payroll: "pieChart",
      performance: "lineChart",
      productivity: "barChart",
    };

    const canvasId = chartIdMap[type];
    console.log(`Updating chart for: ${type}, Canvas ID: ${canvasId}`);

    let chartCanvas = document.getElementById(canvasId);

    // Create card if canvas not found
    if (!chartCanvas) {
      console.log(`Canvas not found for ${type}, creating new chart card.`);
      const newChartHTML = createChartCard(type, canvasId);
      $("#reports-container").append(newChartHTML);

      // ✅ re-select after appending to the DOM
      chartCanvas = document.getElementById(canvasId);
    } else {
      console.log(`Canvas already exists for ${type}, reusing.`);
    }

    const ctx = chartCanvas.getContext("2d");

    // ✅ Destroy previous chart instance if exists
    if (charts[type]) {
      charts[type].destroy();
    }

    let chartType;
    switch (type) {
      case "payroll":
        chartType = "pie";
        break;
      case "productivity":
        chartType = "bar";
        break;
      case "attendance":
      case "performance":
      default:
        chartType = "line";
        break;
    }

    charts[type] = new Chart(ctx, {
      type: chartType,
      data: {
        labels: data.labels || [],
        datasets: [
          {
            label: `${type} data`,
            data: data.data || [],
            backgroundColor: [
              "rgba(255, 99, 132, 0.5)",
              "rgba(54, 162, 235, 0.5)",
              "rgba(255, 206, 86, 0.5)",
              "rgba(75, 192, 192, 0.5)",
              "rgba(153, 102, 255, 0.5)",
            ],
            borderColor: [
              "rgba(255, 99, 132, 1)",
              "rgba(54, 162, 235, 1)",
              "rgba(255, 206, 86, 1)",
              "rgba(75, 192, 192, 1)",
              "rgba(153, 102, 255, 1)",
            ],
            borderWidth: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: chartType === "pie" || chartType === "bar",
          },
        },
        scales:
          chartType !== "pie"
            ? {
                y: {
                  beginAtZero: true,
                },
              }
            : {},
      },
    });
  }
});
