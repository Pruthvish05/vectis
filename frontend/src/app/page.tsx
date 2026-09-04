"use client";

import { useState } from "react";
import {
  ArrowRight,
  Check,
  Clock3,
  Cpu,
  Eye,
  Gauge,
  LockKeyhole,
  Play,
  ShieldCheck,
  Sparkles,
  Terminal,
  X,
} from "lucide-react";

const steps = [
  { label: "Intercept", detail: "Request enters the relay", icon: Eye },
  { label: "Scrub", detail: "PII becomes a safe token", icon: LockKeyhole },
  { label: "Forward", detail: "Model receives clean context", icon: ArrowRight },
];

export default function Home() {
  const [model, setModel] = useState("llama3.2:3b");
  const [upstreamUrl, setUpstreamUrl] = useState("http://127.0.0.1:11434/v1");
  const [duration, setDuration] = useState(15);
  const [status, setStatus] = useState<"idle" | "active">("idle");
  const [notice, setNotice] = useState("");
  const [prompt, setPrompt] = useState("Draft a short greeting for john.doe@example.com.");
  const [response, setResponse] = useState("");
  const [isSending, setIsSending] = useState(false);

  const startSession = async () => {
    setIsSending(true);
    setNotice("");
    try {
      const result = await fetch("http://127.0.0.1:8000/chat/completions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model,
          messages: [{ role: "user", content: prompt }],
          stream: false,
        }),
      });
      const data = await result.json();
      if (!result.ok) throw new Error(data?.error?.message ?? "Proxy request failed");
      setResponse(data.choices?.[0]?.message?.content ?? "No response returned.");
      setStatus("active");
      setNotice("Prompt protected and answered through the Vectis relay.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not reach the Vectis API.");
      setStatus("idle");
    } finally {
      setIsSending(false);
    }
  };

  const endSession = () => {
    setStatus("idle");
    setNotice("Relay disarmed. Upstream access is paused.");
    setResponse("");
  };

  return (
    <main className="vectis-shell min-h-screen text-[#e8edf2]">
      <div className="noise-layer" />
      <div className="shell-inner mx-auto flex min-h-screen max-w-[1440px] flex-col px-5 py-5 sm:px-8 lg:px-12">
        <header className="topbar flex items-center justify-between">
          <div className="brand-lockup"><div className="brand-mark"><ShieldCheck size={21} strokeWidth={2.4} /></div><div><p className="brand-name">Vectis</p><p className="brand-subtitle">AI traffic control</p></div></div>
          <div className="status-chip"><span className={`status-dot ${status === "active" ? "is-live" : ""}`} /><span>{status === "active" ? "Relay live" : "Standby"}</span><span className="status-divider" /><span className="mono-muted">LOCAL / 01</span></div>
        </header>

        <section className="intro grid gap-10 pb-12 pt-14 lg:grid-cols-[1.15fr_0.85fr] lg:items-end lg:pt-20">
          <div><div className="eyebrow"><span /> PRIVATE MODEL GATEWAY</div><h1>Put a clean room<br /><em>between</em> data and AI.</h1><p className="intro-copy">Vectis intercepts every prompt, removes sensitive data before it leaves your machine, and restores the response on the way back.</p></div>
          <div className="intro-meta"><div className="meta-line"><span>ACTIVE MODEL</span><strong>{model}</strong></div><div className="meta-line"><span>PROTECTION</span><strong className="green-text">PII VAULT / ON</strong></div><div className="meta-line"><span>LATENCY TARGET</span><strong>&lt; 120 ms</strong></div></div>
        </section>

        <section className="pipeline-section" aria-label="How Vectis works"><div className="section-kicker"><span>01</span> THE RELAY</div><div className="pipeline-grid">{steps.map((step, index) => { const Icon = step.icon; return <div className="pipeline-step" key={step.label}><div className="step-icon"><Icon size={19} /></div><div><p className="step-label">{step.label}</p><p className="step-detail">{step.detail}</p></div>{index < steps.length - 1 && <ArrowRight className="step-arrow" size={17} />}</div>; })}</div></section>

        <section className="workspace grid gap-5 py-5 lg:grid-cols-[minmax(0,1fr)_380px]">
          <div className="monitor-panel"><div className="panel-heading"><div><div className="section-kicker"><span>02</span> REQUEST MONITOR</div><h2>Protected traffic</h2></div><div className="live-readout"><span className="status-dot is-live" /> {status === "active" ? "LISTENING" : "READY"}</div></div><div className="monitor-screen"><div className="screen-grid" /><div className="screen-content"><div className="screen-badge"><Terminal size={15} /> VECTIS / LOCAL RELAY</div><div className="route-row"><span className="route-node node-client">CLIENT</span><ArrowRight size={20} /><span className="route-line" /><span className="route-node node-vault">PII VAULT</span><ArrowRight size={20} /><span className="route-line" /><span className="route-node node-model">MODEL</span></div>{response ? <p className="screen-response">{response}</p> : <p className="screen-caption">Arm a session to send protected traffic.</p>}</div></div><div className="metric-row"><div><Gauge size={16} /><span>REQUESTS</span><strong>{response ? "01" : "00"}</strong></div><div><LockKeyhole size={16} /><span>IDENTITIES VAULTED</span><strong>{response ? "01" : "00"}</strong></div><div><Cpu size={16} /><span>MODEL HEALTH</span><strong className="green-text">READY</strong></div></div></div>

          <div className="control-panel"><div className="panel-heading"><div><div className="section-kicker"><span>03</span> CONTROL DECK</div><h2>Arm a session</h2></div><Sparkles size={18} className="gold-icon" /></div><div className="field-group"><label htmlFor="model">MODEL</label><div className="input-shell"><Cpu size={16} /><input id="model" value={model} onChange={(event) => setModel(event.target.value)} /></div><p className="field-hint">Local Ollama endpoint / OpenAI compatible</p></div><div className="field-group"><label htmlFor="upstream">UPSTREAM URL</label><div className="input-shell"><ArrowRight size={16} /><input id="upstream" value={upstreamUrl} onChange={(event) => setUpstreamUrl(event.target.value)} /></div></div><div className="field-group"><label htmlFor="prompt">TEST PROMPT</label><div className="input-shell"><Terminal size={16} /><input id="prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} /></div></div><div className="field-group"><div className="label-row"><label htmlFor="duration">SESSION WINDOW</label><strong>{duration} MIN</strong></div><input id="duration" type="range" min="1" max="60" value={duration} onChange={(event) => setDuration(Number(event.target.value))} /></div>{notice && <div className="notice"><Check size={15} /> {notice}</div>}{status === "active" ? <button className="metal-button danger-button" onClick={endSession}><X size={17} /> DISARM RELAY</button> : <button className="metal-button" onClick={startSession} disabled={isSending}><Play size={17} fill="currentColor" /> {isSending ? "CONTACTING MODEL" : "SEND THROUGH VECTIS"}</button>}<p className="control-footnote"><Clock3 size={14} /> Access automatically expires after the session window.</p></div>
        </section>

        <footer className="bottom-bar mt-auto pt-7"><span>VECTIS SECURITY SYSTEMS</span><span>LOCAL-FIRST / ZERO RETENTION</span><span>BUILD 0.4.1</span></footer>
      </div>
    </main>
  );
}