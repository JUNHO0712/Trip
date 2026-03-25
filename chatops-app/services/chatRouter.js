const {
  getProblemPods,
  getAllPods,
  findMentionedServicesFromText,
  checkServiceConnectionBasic,
  getServiceConfigSummary,
} = require("./k8s");
const { getLogs } = require("./logs");
const {
  analyzeLogs,
  chatWithAI,
  parseUserRequestWithAI,
} = require("./gpt");
const { getClusterResourceUsage } = require("./metrics");
const { queryPrometheus } = require("./prometheus");
const { setRecentContext, getRecentContext } = require("./recentContext");

function normalizeInput(text) {
  return String(text || "")
    .trim()
    .toLowerCase()
    .replace(/promethous/g, "prometheus")
    .replace(/머게/g, "뭐야")
    .replace(/머임/g, "뭐야")
    .replace(/뭐게/g, "뭐야")
    .replace(/머야/g, "뭐야")
    .replace(/머냐/g, "뭐야")
    .replace(/어딨냐/g, "어디있어")
    .replace(/어딨음/g, "어디있어")
    .replace(/namespace/g, "네임스페이스");
}

function compactText(text) {
  return String(text || "").replace(/\s+/g, "");
}

function inferIntentFallback(text, parsed = {}) {
  const normalized = normalizeInput(text);
  const compact = compactText(normalized);

  if (
    compact.includes("두파드") ||
    compact.includes("그파드") ||
    compact.includes("방금그거")
  ) {
    return "analyzeRecentPods";
  }

  if (
    compact.includes("설정") ||
    compact.includes("config") ||
    compact.includes("values")
  ) {
    return "checkConfig";
  }

  if (compact.includes("네임스페이스")) {
    return "findNamespace";
  }

  if (
    parsed.intent &&
    parsed.intent !== "chat" &&
    parsed.intent !== "unclear"
  ) {
    return parsed.intent;
  }

  if (
    (compact.includes("전체") || compact.includes("모든")) &&
    (compact.includes("파드") || compact.includes("pod"))
  ) {
    return "allPods";
  }

  if (
    (compact.includes("문제") ||
      compact.includes("비정상") ||
      compact.includes("이상")) &&
    (compact.includes("파드") || compact.includes("pod"))
  ) {
    return "pods";
  }

  if (compact.includes("연결") || compact.includes("연동")) {
    return "checkConnection";
  }

  if (compact.includes("상태") && !compact.includes("클러스터")) {
    return "serviceStatus";
  }

  if (compact.includes("어디있") || compact.includes("어딨")) {
    return "findService";
  }

  return parsed.intent || "chat";
}

async function handleProblemPodsQuery(scope) {
  const problemPods = (await getProblemPods()) || [];

  if (problemPods.length === 0) {
    return "현재 비정상 Pod는 없습니다.";
  }

  setRecentContext(scope, {
    type: "problemPods",
    pods: problemPods.map((p) => ({
      namespace: p.namespace,
      name: p.name,
      status: p.displayStatus || p.phase || "Unknown",
    })),
  });

  const lines = problemPods
    .slice(0, 20)
    .map(
      (p) =>
        `- ${p.namespace}/${p.name} (${p.displayStatus || p.phase || "Unknown"})`
    );

  return [
    `현재 문제 있는 Pod는 ${problemPods.length}개입니다.`,
    "",
    ...lines,
  ].join("\n");
}

async function handleAllPodsQuery() {
  const allPods = (await getAllPods()) || [];

  if (allPods.length === 0) {
    return "현재 조회된 Pod가 없습니다.";
  }

  const lines = allPods
    .slice(0, 25)
    .map(
      (p) =>
        `- ${p.namespace}/${p.name} (${p.displayStatus || p.phase || "Unknown"})`
    );

  return [
    `현재 전체 Pod는 ${allPods.length}개입니다.`,
    "",
    ...lines,
  ].join("\n");
}

async function handleStatusQuery() {
  let upCount = "N/A";
  let cpuText = "N/A";
  let memoryText = "N/A";

  try {
    const upResult = await queryPrometheus("up");
    upCount = Array.isArray(upResult) ? upResult.length : "N/A";
  } catch (_) {}

  const allPods = (await getAllPods()) || [];
  const problemPods = (await getProblemPods()) || [];
  const runningPods = allPods.filter((p) => p.phase === "Running").length;

  try {
    const metrics = await getClusterResourceUsage();
    cpuText = `${metrics.totalCpuMillicores.toFixed(0)}m`;
    memoryText = `${metrics.totalMemoryMi.toFixed(1)} MiB`;
  } catch (_) {}

  return [
    "Kubernetes Cluster Status",
    "",
    `Up 대상: ${upCount}`,
    `Running Pod: ${runningPods}`,
    `Problem Pod: ${problemPods.length}`,
    "",
    `클러스터 CPU 사용량: ${cpuText}`,
    `클러스터 Memory 사용량: ${memoryText}`,
  ].join("\n");
}

async function handleServiceStatusQuery(text) {
  const services = await findMentionedServicesFromText(text);
  const target = services[0];

  if (!target) {
    return "특정 서비스 상태를 찾지 못했습니다.";
  }

  const allPods = (await getAllPods()) || [];
  const matchedPods = allPods.filter((p) =>
    p.name.toLowerCase().includes(target)
  );

  if (matchedPods.length === 0) {
    return `${target} 관련 Pod를 찾지 못했습니다.`;
  }

  const running = matchedPods.filter((p) => p.phase === "Running");
  const problems = matchedPods.filter((p) => p.phase !== "Running");

  const lines = matchedPods.map(
    (p) => `- ${p.namespace}/${p.name} (${p.displayStatus || p.phase})`
  );

  return [
    `${target.toUpperCase()} 상태`,
    "",
    `Running: ${running.length}`,
    `Problem: ${problems.length}`,
    "",
    ...lines,
  ].join("\n");
}

async function handleFindServiceQuery(text) {
  const services = await findMentionedServicesFromText(text);
  const target = services[0];

  if (!target) {
    return "찾을 서비스 이름을 이해하지 못했습니다.";
  }

  const allPods = (await getAllPods()) || [];
  const matchedPods = allPods.filter((p) =>
    p.name.toLowerCase().includes(target)
  );

  if (matchedPods.length === 0) {
    return `${target} 관련 Pod를 찾지 못했습니다.`;
  }

  const lines = matchedPods.map(
    (p) => `- ${p.namespace}/${p.name} (${p.displayStatus || p.phase})`
  );

  return [
    `${target.toUpperCase()} 관련 Pod 위치`,
    "",
    ...lines,
  ].join("\n");
}

async function handleFindNamespaceQuery(text) {
  const services = await findMentionedServicesFromText(text);
  const target = services[0];

  if (!target) {
    return "서비스 이름을 찾지 못했습니다.";
  }

  const allPods = (await getAllPods()) || [];
  const namespaces = Array.from(
    new Set(
      allPods
        .filter((p) => p.name.toLowerCase().includes(target))
        .map((p) => p.namespace)
    )
  ).sort((a, b) => a.localeCompare(b));

  if (namespaces.length === 0) {
    return `${target} 관련 namespace를 찾지 못했습니다.`;
  }

  if (namespaces.length === 1) {
    return `${target}는 ${namespaces[0]} 네임스페이스에 있습니다.`;
  }

  return [
    `${target} 관련 namespace는 여러 개입니다.`,
    "",
    ...namespaces.map((ns) => `- ${ns}`),
  ].join("\n");
}

async function handleCheckConnectionQuery(text) {
  const services = await findMentionedServicesFromText(text);

  if (services.length < 2) {
    return "연결 여부를 확인하려면 서비스 2개가 필요합니다.";
  }

  const [serviceA, serviceB] = services;
  const result = await checkServiceConnectionBasic(serviceA, serviceB);

  if (!result.existsA && !result.existsB) {
    return `${serviceA}, ${serviceB} 관련 Pod를 모두 찾지 못했습니다.`;
  }

  if (!result.existsA) {
    return `${serviceA} 관련 Pod를 찾지 못했습니다.`;
  }

  if (!result.existsB) {
    return `${serviceB} 관련 Pod를 찾지 못했습니다.`;
  }

  const lines = [
    `${serviceA}와 ${serviceB}를 확인했습니다.`,
    "",
    `${serviceA}: ${result.podsA.length}개 Pod 확인`,
    `${serviceB}: ${result.podsB.length}개 Pod 확인`,
    "",
    `${serviceA} namespace: ${result.namespacesA.join(", ")}`,
    `${serviceB} namespace: ${result.namespacesB.join(", ")}`,
  ];

  if (result.sameNamespace.length > 0) {
    lines.push("");
    lines.push(`같은 namespace: ${result.sameNamespace.join(", ")}`);
    lines.push("기본 배포 구조상 연동 대상으로 볼 수 있습니다.");
  }

  lines.push("정확한 datasource 연동 여부는 Grafana 설정 확인이 추가로 필요합니다.");

  return lines.join("\n");
}

function classifyPodStatus(statusText) {
  const s = String(statusText || "").toLowerCase();

  if (s.includes("crashloopbackoff")) {
    return "컨테이너가 실행 직후 계속 종료되어 재시작을 반복하는 상태입니다.";
  }

  if (s.includes("createcontainerconfigerror")) {
    return "ConfigMap 또는 Secret 등 컨테이너 설정 참조 문제 가능성이 큽니다.";
  }

  if (s.includes("imagepullbackoff") || s.includes("errimagepull")) {
    return "이미지 pull 실패 가능성이 큽니다.";
  }

  if (s.includes("unknown")) {
    return "노드 상태 또는 컨테이너 상태를 정상적으로 확인하지 못한 상태입니다.";
  }

  if (s.includes("error")) {
    return "컨테이너 실행 중 일반 오류가 발생한 상태입니다.";
  }

  return "추가 로그/describe 확인이 필요합니다.";
}

async function handleAnalyzeRecentPods(scope) {
  const recent = getRecentContext(scope);

  if (!recent || recent.type !== "problemPods" || !Array.isArray(recent.pods)) {
    return "최근에 조회한 문제 Pod 목록이 없습니다. 먼저 `문제 있는 파드 뭐야?`를 실행해주세요.";
  }

  const targets = recent.pods.slice(0, 5);

  const lines = [];

  for (let i = 0; i < targets.length; i += 1) {
    const pod = targets[i];
    lines.push(`${i + 1}. ${pod.namespace}/${pod.name}`);
    lines.push(`- 상태: ${pod.status}`);
    lines.push(`- 원인 후보: ${classifyPodStatus(pod.status)}`);
    lines.push("");
  }

  return lines.join("\n").trim();
}

async function handleCheckConfigQuery(text) {
  const services = await findMentionedServicesFromText(text);
  const target = services[0];

  if (!target) {
    return "설정을 확인할 서비스 이름을 찾지 못했습니다. 예: `alloy 설정 확인해줘`";
  }

  const summary = await getServiceConfigSummary(target);

  if (!summary.found) {
    return `${target} 관련 Pod를 찾지 못했습니다.`;
  }

  const lines = [
    `${target} 설정 확인 결과`,
    "",
    `namespace: ${summary.namespaces.join(", ")}`,
    `Pod 수: ${summary.pods.length}`,
    "",
    "상태 요약:",
    ...summary.statusSummary.map(
      (p) => `- ${p.namespace}/${p.name} (${p.status})`
    ),
  ];

  if (summary.configMaps.length > 0) {
    lines.push("");
    lines.push("ConfigMap 참조:");
    lines.push(...summary.configMaps.map((x) => `- ${x}`));
  }

  if (summary.secrets.length > 0) {
    lines.push("");
    lines.push("Secret 참조:");
    lines.push(...summary.secrets.map((x) => `- ${x}`));
  }

  if (summary.configMaps.length === 0 && summary.secrets.length === 0) {
    lines.push("");
    lines.push("Pod spec 기준으로 직접 확인된 ConfigMap/Secret 참조는 없습니다.");
  }

  const hasCreateConfigError = summary.statusSummary.some((p) =>
    String(p.status).toLowerCase().includes("createcontainerconfigerror")
  );

  if (hasCreateConfigError) {
    lines.push("");
    lines.push(
      "추정 원인: CreateContainerConfigError 상태이므로 ConfigMap 또는 Secret 누락 가능성이 큽니다."
    );
  }

  return lines.join("\n");
}

async function routeChatMessage(text, scope = {}) {
  try {
    const normalizedText = normalizeInput(text);
    const parsed = await parseUserRequestWithAI(normalizedText);
    const finalIntent = inferIntentFallback(normalizedText, parsed);

    console.log(
      "[chatRouter][AI parsed]",
      parsed,
      "| finalIntent:",
      finalIntent,
      "| input:",
      text
    );

    switch (finalIntent) {
      case "pods":
        return handleProblemPodsQuery(scope);

      case "allPods":
        return handleAllPodsQuery();

      case "status":
        return handleStatusQuery();

      case "serviceStatus":
        return handleServiceStatusQuery(normalizedText);

      case "findService":
        return handleFindServiceQuery(normalizedText);

      case "findNamespace":
        return handleFindNamespaceQuery(normalizedText);

      case "checkConnection":
        return handleCheckConnectionQuery(normalizedText);

      case "checkConfig":
        return handleCheckConfigQuery(normalizedText);

      case "analyzeRecentPods":
        return handleAnalyzeRecentPods(scope);

      case "chat":
      default:
        return chatWithAI(text);
    }
  } catch (error) {
    console.error("chatRouter 처리 오류:", error);
    return "챗봇 처리 중 오류가 발생했습니다.";
  }
}

module.exports = {
  routeChatMessage,
};