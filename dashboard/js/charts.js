const DATA_URL = "../data/issues.json";

const CHART_COLORS = [
  "#58a6ff",
  "#3fb950",
  "#d29922",
  "#f85149",
  "#a371f7",
  "#79c0ff",
  "#56d364",
  "#e3b341",
];

let chartStatus, chartType, chartAssignee;

async function loadData() {
  try {
    const res = await fetch(DATA_URL);
    if (!res.ok) throw new Error("Dados não encontrados");
    return await res.json();
  } catch (err) {
    console.error(err);
    return null;
  }
}

function renderCards(aggregates) {
  const total = aggregates?.total ?? 0;
  const byStatus = aggregates?.by_status ?? {};
  const inProgress =
    (byStatus["In Progress"] ?? 0) +
    (byStatus["Em Progresso"] ?? 0) +
    (byStatus["In development"] ?? 0);
  const done =
    (byStatus["Done"] ?? 0) +
    (byStatus["Concluído"] ?? 0) +
    (byStatus["Resolved"] ?? 0);

  document.getElementById("totalIssues").textContent = total;
  document.getElementById("inProgress").textContent = inProgress;
  document.getElementById("done").textContent = done;
}

function renderCharts(aggregates) {
  const byStatus = aggregates?.by_status ?? {};
  const byType = aggregates?.by_type ?? {};
  const byAssignee = aggregates?.by_assignee ?? {};

  let statusLabels = Object.keys(byStatus);
  let statusData = Object.values(byStatus);
  if (!statusLabels.length) {
    statusLabels = ["Sem dados"];
    statusData = [0];
  }

  let typeLabels = Object.keys(byType);
  let typeData = Object.values(byType);
  if (!typeLabels.length) {
    typeLabels = ["Sem dados"];
    typeData = [0];
  }

  let assigneeLabels = Object.keys(byAssignee);
  let assigneeData = Object.values(byAssignee);
  if (!assigneeLabels.length) {
    assigneeLabels = ["Sem dados"];
    assigneeData = [0];
  }

  if (chartStatus) chartStatus.destroy();
  chartStatus = new Chart(document.getElementById("chartStatus"), {
    type: "doughnut",
    data: {
      labels: statusLabels,
      datasets: [
        {
          data: statusData,
          backgroundColor: CHART_COLORS.slice(0, statusLabels.length),
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { position: "bottom" },
      },
    },
  });

  if (chartType) chartType.destroy();
  chartType = new Chart(document.getElementById("chartType"), {
    type: "bar",
    data: {
      labels: typeLabels,
      datasets: [
        {
          data: typeData,
          backgroundColor: CHART_COLORS.slice(0, typeLabels.length),
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
      },
      scales: {
        y: { beginAtZero: true },
      },
    },
  });

  if (chartAssignee) chartAssignee.destroy();
  chartAssignee = new Chart(document.getElementById("chartAssignee"), {
    type: "bar",
    data: {
      labels: assigneeLabels,
      datasets: [
        {
          data: assigneeData,
          backgroundColor: CHART_COLORS[0],
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: { beginAtZero: true },
      },
    },
  });
}

function renderTable(issues) {
  const tbody = document.getElementById("issuesTableBody");
  if (!issues || issues.length === 0) {
    tbody.innerHTML = "<tr><td colspan='6'>Nenhuma issue encontrada</td></tr>";
    return;
  }

  tbody.innerHTML = issues
    .slice(0, 20)
    .map(
      (i) => `
    <tr>
      <td><strong>${escapeHtml(i.key)}</strong></td>
      <td>${escapeHtml(i.summary || "-")}</td>
      <td>${escapeHtml(i.status)}</td>
      <td>${escapeHtml(i.issuetype)}</td>
      <td>${escapeHtml(i.assignee)}</td>
      <td class="link-cell"><a href="${escapeHtml(i.url)}" target="_blank" rel="noopener">Abrir</a></td>
    </tr>
  `
    )
    .join("");
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function formatLastUpdated(iso) {
  if (!iso) return "--";
  try {
    const d = new Date(iso);
    return d.toLocaleString("pt-BR");
  } catch {
    return iso;
  }
}

async function init() {
  const data = await loadData();
  if (!data) {
    document.getElementById("issuesTableBody").innerHTML =
      "<tr><td colspan='6'>Erro ao carregar dados. Execute a extração primeiro.</td></tr>";
    document.getElementById("lastUpdated").textContent = "--";
    return;
  }

  document.getElementById("lastUpdated").textContent = formatLastUpdated(
    data.last_updated
  );
  renderCards(data.aggregates);
  renderCharts(data.aggregates);
  renderTable(data.issues);
}

init();
