import type { AgentHealth } from "../../lib/types";

const statusLabel: Record<AgentHealth["status"], string> = {
  idle: "等待调用",
  healthy: "正常",
  degraded: "已降级",
};

export function ModelHealthPanel({ health }: { health?: AgentHealth }) {
  if (!health) return null;

  return <section className="model-health-panel" aria-label="模型运行状态">
    <h2>模型运行</h2>
    <p>模型状态：<strong className={`model-health-${health.status}`}>{statusLabel[health.status]}</strong></p>
    <p className="muted">调用 {health.total_calls} 次 · 平均 {health.average_latency_ms} ms</p>
    {health.fallback_calls > 0 && <p className="model-health-warning">降级 {health.fallback_calls} 次</p>}
    {health.latest_failure_kind && <p className="muted">最近原因：{health.latest_failure_kind}</p>}
  </section>;
}
