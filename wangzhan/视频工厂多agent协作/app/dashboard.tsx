'use client'

import { useEffect, useMemo, useState } from 'react'
import type { AgentRun, MultiAgentJob, RunMode } from '@/lib/types'

type FormState = {
  horse: string
  topic: string
  runMode: RunMode
  shotCount: number
  clipCount: number
  videoCount: number
  agentConcurrency: number
  clipConcurrency: number
  referenceSummary: string
}

const initialForm: FormState = {
  horse: '赤兔',
  topic: '赤兔为什么从吕布的锋芒走到关羽的忠义',
  runMode: 'preview',
  shotCount: 3,
  clipCount: 3,
  videoCount: 1,
  agentConcurrency: 4,
  clipConcurrency: 3,
  referenceSummary: '只参考水墨卷轴展开、纸本留白、烟尘和战旗气质，不照搬旧样片。',
}

function stateText(state: AgentRun['state']) {
  const map = {
    queued: '等待',
    working: '工作中',
    waiting: '等待依赖',
    done: '完成',
    failed: '失败',
  }
  return map[state]
}

function laneName(lane: AgentRun['lane']) {
  const map = {
    input: '输入与参考',
    text: '文本与声音',
    visual: '视觉资产',
    video: '视频片段',
    finish: '合成与质检',
  }
  return map[lane]
}

function duration(ms?: number) {
  if (!ms) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${Math.round(ms / 100) / 10}s`
}

function useJobPolling(jobId?: string) {
  const [job, setJob] = useState<MultiAgentJob | null>(null)
  useEffect(() => {
    if (!jobId) return
    let cancelled = false
    const load = async () => {
      const response = await fetch(`/api/multiagent/jobs/${jobId}`, { cache: 'no-store' })
      if (!response.ok) return
      const payload = await response.json()
      if (!cancelled) setJob(payload.job)
    }
    void load()
    const timer = window.setInterval(load, 1200)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [jobId])
  return job
}

function AgentDesk({ agent }: { agent: AgentRun }) {
  const activeSubagents = agent.subagents?.filter((sub) => sub.state === 'working') || []
  return (
    <article className={`agent-desk ${agent.state}`}>
      <div className="desk-head">
        <span className="agent-code">{agent.emoji}</span>
        <div>
          <h3>{agent.name}</h3>
          <p>{agent.shortRole}</p>
        </div>
        <strong>{stateText(agent.state)}</strong>
      </div>
      <div className="bar">
        <span style={{ width: `${agent.progress}%` }} />
      </div>
      <p className="desk-role">{agent.role}</p>
      {activeSubagents.length > 0 && (
        <div className="subagent-row">
          {activeSubagents.map((sub) => (
            <span key={sub.id}>{sub.name}</span>
          ))}
        </div>
      )}
      {agent.summary && <p className="desk-summary">{agent.summary}</p>}
      {agent.error && <p className="desk-error">{agent.error}</p>}
    </article>
  )
}

function PixelOffice({ job }: { job: MultiAgentJob | null }) {
  const lanes = useMemo(() => {
    const source = job?.agents || []
    return ['input', 'text', 'visual', 'video', 'finish'].map((lane) => ({
      lane: lane as AgentRun['lane'],
      agents: source.filter((agent) => agent.lane === lane),
    }))
  }, [job])

  return (
    <section className="office-panel">
      <div className="section-title">
        <span>Pixel Office</span>
        <strong>{job ? job.status : '等待任务'}</strong>
      </div>
      <div className="office-grid">
        {lanes.map((lane) => (
          <div className="lane" key={lane.lane}>
            <h2>{laneName(lane.lane)}</h2>
            <div className="lane-desks">
              {lane.agents.map((agent) => <AgentDesk key={agent.id} agent={agent} />)}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function ControlPanel({ onStart, busy }: { onStart: (form: FormState) => void; busy: boolean }) {
  const [form, setForm] = useState<FormState>(initialForm)
  const update = <K extends keyof FormState>(key: K, value: FormState[K]) => setForm((prev) => ({ ...prev, [key]: value }))
  return (
    <section className="control-panel">
      <div className="section-title">
        <span>任务配置</span>
        <strong>Codex Multi-Agent</strong>
      </div>
      <label>
        主角名马
        <select value={form.horse} onChange={(event) => update('horse', event.target.value)}>
          {['赤兔', '的卢', '汗血', '绝影', '乌骓'].map((horse) => <option key={horse}>{horse}</option>)}
        </select>
      </label>
      <label>
        视频主题
        <input value={form.topic} onChange={(event) => update('topic', event.target.value)} />
      </label>
      <div className="field-row">
        <label>
          模式
          <select value={form.runMode} onChange={(event) => update('runMode', event.target.value as RunMode)}>
            <option value="preview">快速预演</option>
            <option value="final">成片策划</option>
          </select>
        </label>
        <label>
          分镜
          <select value={form.shotCount} onChange={(event) => update('shotCount', Number(event.target.value))}>
            {[1, 2, 3, 4, 5, 6, 8].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <label>
          片段
          <select value={form.clipCount} onChange={(event) => update('clipCount', Number(event.target.value))}>
            {[1, 2, 3, 4, 5, 6, 8].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
      </div>
      <div className="field-row">
        <label>
          批量
          <select value={form.videoCount} onChange={(event) => update('videoCount', Number(event.target.value))}>
            {[1, 3, 5, 10].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <label>
          Agent 并发
          <select value={form.agentConcurrency} onChange={(event) => update('agentConcurrency', Number(event.target.value))}>
            {[2, 3, 4, 5, 6, 8].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <label>
          片段并发
          <select value={form.clipConcurrency} onChange={(event) => update('clipConcurrency', Number(event.target.value))}>
            {[1, 2, 3, 4, 5, 6].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
      </div>
      <label>
        参考约束
        <textarea value={form.referenceSummary} onChange={(event) => update('referenceSummary', event.target.value)} />
      </label>
      <button disabled={busy} onClick={() => onStart(form)}>
        {busy ? '运行中' : '启动多 Agent 协作'}
      </button>
    </section>
  )
}

function JobStats({ job }: { job: MultiAgentJob | null }) {
  const done = job?.agents.filter((agent) => agent.state === 'done').length || 0
  const failed = job?.agents.filter((agent) => agent.state === 'failed').length || 0
  const working = job?.agents.filter((agent) => agent.state === 'working').length || 0
  return (
    <section className="stats-grid">
      <div><span>节点</span><strong>{done}/{job?.agents.length || 0}</strong></div>
      <div><span>工作中</span><strong>{working}</strong></div>
      <div><span>失败</span><strong>{failed}</strong></div>
      <div><span>预计提速</span><strong>{job?.output?.estimatedSpeedup ? '25-45%' : '-'}</strong></div>
    </section>
  )
}

function ArtifactPanel({ job }: { job: MultiAgentJob | null }) {
  const selected = job?.agents.filter((agent) => agent.summary || agent.error) || []
  return (
    <section className="artifact-panel">
      <div className="section-title">
        <span>协作产物</span>
        <strong>{selected.length} 个节点</strong>
      </div>
      <div className="artifact-list">
        {selected.map((agent) => (
          <details key={agent.id} open={agent.state === 'failed'}>
            <summary>
              <span>{agent.name}</span>
              <small>{duration(agent.durationMs)}</small>
            </summary>
            <p>{agent.error || agent.summary}</p>
          </details>
        ))}
        {job?.output?.videoFactoryPayload && (
          <details open>
            <summary>
              <span>视频工厂 Payload</span>
              <small>可交付</small>
            </summary>
            <pre>{JSON.stringify(job.output.videoFactoryPayload, null, 2)}</pre>
          </details>
        )}
      </div>
    </section>
  )
}

function EventLog({ job }: { job: MultiAgentJob | null }) {
  return (
    <section className="event-panel">
      <div className="section-title">
        <span>运行记录</span>
        <strong>{job?.events.length || 0}</strong>
      </div>
      <div className="event-list">
        {(job?.events || []).map((event) => (
          <div className={`event ${event.level}`} key={event.id}>
            <time>{new Date(event.at).toLocaleTimeString()}</time>
            <span>{event.text}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

export default function Dashboard() {
  const [jobId, setJobId] = useState<string>()
  const job = useJobPolling(jobId)
  const busy = job?.status === 'queued' || job?.status === 'running'

  const start = async (form: FormState) => {
    const response = await fetch('/api/multiagent/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...form, title: `${form.horse}多 Agent 视频任务` }),
    })
    const payload = await response.json()
    setJobId(payload.job.id)
  }

  return (
    <main className="page-shell">
      <header className="topbar">
        <div>
          <p>OpenClaw Inspired / Codex API / Video Factory DAG</p>
          <h1>视频工厂多 Agent 协作办公室</h1>
        </div>
        <a href="./openclaw-source/README.md" target="_blank">OpenClaw 源码参考</a>
      </header>
      <div className="layout">
        <aside>
          <ControlPanel onStart={start} busy={Boolean(busy)} />
          <JobStats job={job} />
          <EventLog job={job} />
        </aside>
        <div className="main-column">
          <PixelOffice job={job} />
          <ArtifactPanel job={job} />
        </div>
      </div>
    </main>
  )
}
