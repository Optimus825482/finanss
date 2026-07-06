"use client";

import { AgentStatus } from "../lib/api";

const STATUS_LABEL: Record<string, string> = {
  idle: "BEKLEMEDE",
  running: "ÇALIŞIYOR",
  done: "TAMAM",
  error: "HATA",
};

function NodeDot({ status }: { status: AgentStatus["status"] }) {
  const base = "w-3 h-3 rounded-full border";
  if (status === "done") return <div className={`${base} bg-term-amber border-term-amber shadow-glow`} />;
  if (status === "running") return <div className={`${base} bg-term-amber border-term-amber pulse-node`} />;
  if (status === "error") return <div className={`${base} bg-term-red border-term-red`} />;
  return <div className={`${base} bg-transparent border-term-muted`} />;
}

export default function SignalChain({ agents }: { agents: AgentStatus[] }) {
  return (
    <div className="border border-term-border bg-term-panel rounded-sm p-4">
      <div className="text-[11px] tracking-[0.2em] text-term-muted font-mono mb-3">
        AJAN SİNYAL ZİNCİRİ
      </div>
      <div className="flex items-stretch">
        {agents.map((agent, idx) => (
          <div key={agent.name} className="flex items-center flex-1">
            <div className="flex flex-col items-center gap-2 flex-1">
              <NodeDot status={agent.status} />
              <div className="font-mono text-xs text-term-text text-center">{agent.label}</div>
              <div
                className={`font-mono text-[10px] tracking-wider ${
                  agent.status === "error"
                    ? "text-term-red"
                    : agent.status === "done"
                    ? "text-term-green"
                    : agent.status === "running"
                    ? "text-term-amber"
                    : "text-term-muted"
                }`}
              >
                {STATUS_LABEL[agent.status]}
              </div>
              {agent.detail && (
                <div className="text-[10px] text-term-muted text-center px-1 leading-tight">
                  {agent.detail}
                </div>
              )}
            </div>
            {idx < agents.length - 1 && (
              <div
                className={`h-px flex-1 mx-1 mb-8 ${
                  agent.status === "done" ? "bg-term-amber" : "bg-term-border"
                }`}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
