import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  Bot,
  BriefcaseBusiness,
  Check,
  ChevronDown,
  CircleHelp,
  Database,
  FileText,
  GitBranch,
  Layers3,
  LoaderCircle,
  MessageSquareText,
  Plus,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  Upload,
  Users,
  X,
} from 'lucide-react'
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  type FormEvent,
  useEffect,
  useMemo,
  useState,
} from 'react'
import { api, type ChatAnswer, type Citation, type Meeting } from './api'
import './App.css'

type Page = 'Dashboard' | 'Company Memory' | 'Meetings' | 'Knowledge Graph' | 'My Onboarding'
type GraphNode = Node<{ label: string; type: string; properties: Record<string, unknown> }>
type GraphEdge = Edge<{ relationship: string }>
type Stats = {
  meetings: number
  people: number
  projects: number
  systems: number
  decisions: number
  open_tasks: number
  recent_meetings: Meeting[]
  recent_decisions: Record<string, unknown>[]
  sample_employee: { id: string; name: string } | null
}
type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
  response?: ChatAnswer
}

const navItems: { label: Page; icon: typeof Activity }[] = [
  { label: 'Dashboard', icon: Layers3 },
  { label: 'Company Memory', icon: MessageSquareText },
  { label: 'Meetings', icon: FileText },
  { label: 'Knowledge Graph', icon: GitBranch },
  { label: 'My Onboarding', icon: BriefcaseBusiness },
]

const suggestedQuestions = [
  'Why did the team choose Kafka for payments?',
  'Who can help with OAuth2 and authentication?',
  'What action items are assigned to Riya?',
]

const defaultStats: Stats = {
  meetings: 0,
  people: 0,
  projects: 0,
  systems: 0,
  decisions: 0,
  open_tasks: 0,
  recent_meetings: [],
  recent_decisions: [],
  sample_employee: null,
}

function isUuid(value: string) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)
}

function formatDate(value?: string) {
  if (!value) return 'Date not provided'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function entityTitle(data: Record<string, unknown>) {
  return String(data.name ?? data.summary ?? data.content ?? data.description ?? data.title ?? 'Knowledge item')
}

function App() {
  const [page, setPage] = useState<Page>('Dashboard')
  const [stats, setStats] = useState<Stats>(defaultStats)
  const [statsError, setStatsError] = useState('')
  const [health, setHealth] = useState<{ database: string; demo_mode: boolean; gemini_configured: boolean } | null>(null)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [activeMeeting, setActiveMeeting] = useState<Meeting | null>(null)
  const [meetingEvidence, setMeetingEvidence] = useState<Record<string, unknown>[]>([])
  const [meetings, setMeetings] = useState<Meeting[]>([])
  const [meetingSearch, setMeetingSearch] = useState('')
  const [meetingError, setMeetingError] = useState('')
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([])
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([])
  const [graphError, setGraphError] = useState('')
  const [graphType, setGraphType] = useState('All types')
  const [graphSearch, setGraphSearch] = useState('')
  const [selectedGraphNode, setSelectedGraphNode] = useState<GraphNode | null>(null)
  const [graphLoading, setGraphLoading] = useState(false)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatDraft, setChatDraft] = useState('')
  const [chatBusy, setChatBusy] = useState(false)
  const [chatError, setChatError] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [onboarding, setOnboarding] = useState<Record<string, unknown> | null>(null)
  const [onboardingError, setOnboardingError] = useState('')
  const [toast, setToast] = useState('')

  async function refreshDashboard() {
    setStatsError('')
    try {
      const result = await api<Stats>('/api/dashboard/stats')
      setStats(result)
    } catch (error) {
      setStatsError(error instanceof Error ? error.message : 'Could not load dashboard data.')
    }
  }

  useEffect(() => {
    void refreshDashboard()
    void api<typeof health>('/health')
      .then(setHealth)
      .catch(() => setHealth({ database: 'unavailable', demo_mode: false, gemini_configured: false }))
  }, [])

  useEffect(() => {
    if (page !== 'Meetings') return
    setMeetingError('')
    void api<Meeting[]>('/api/meetings')
      .then(setMeetings)
      .catch((error: unknown) => setMeetingError(error instanceof Error ? error.message : 'Could not load meetings.'))
  }, [page])

  useEffect(() => {
    if (page !== 'Knowledge Graph') return
    setGraphLoading(true)
    setGraphError('')
    const query = new URLSearchParams({ limit: '250' })
    if (graphType !== 'All types') query.set('node_type', graphType)
    void api<{ nodes: { id: string; type: string; data: Record<string, unknown> }[]; edges: { id: string; source: string; target: string; label: string; data?: Record<string, unknown> }[] }>(`/api/graph?${query}`)
      .then((result) => {
        const nodes: GraphNode[] = result.nodes.map((node, index) => ({
          id: node.id,
          type: 'default',
          position: { x: (index % 5) * 220, y: Math.floor(index / 5) * 155 },
          data: { label: entityTitle(node.data), type: node.type, properties: node.data },
          className: `graph-node graph-${node.type.toLowerCase()}`,
        }))
        const nodeIds = new Set(nodes.map((node) => node.id))
        setGraphNodes(nodes)
        setGraphEdges(
          result.edges
            .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
            .map((edge) => ({
              id: edge.id,
              source: edge.source,
              target: edge.target,
              label: edge.label,
              data: { relationship: edge.label },
              animated: edge.label === 'SUPERSEDES',
              style: { stroke: edge.label === 'SUPERSEDES' ? '#9b72f2' : '#cbd2df' },
            })),
        )
      })
      .catch((error: unknown) => setGraphError(error instanceof Error ? error.message : 'Could not load the graph.'))
      .finally(() => setGraphLoading(false))
  }, [page, graphType])

  useEffect(() => {
    if (page !== 'My Onboarding') return
    setOnboardingError('')
    const employeeId = stats.sample_employee?.id ?? 'sample'
    void api<Record<string, unknown>>(`/api/onboarding/${encodeURIComponent(employeeId)}`)
      .then(setOnboarding)
      .catch((error: unknown) => setOnboardingError(error instanceof Error ? error.message : 'Could not load onboarding recommendations.'))
  }, [page, stats.sample_employee?.id])

  useEffect(() => {
    const saved = localStorage.getItem('onboardos-chat-session')
    const nextSession = saved && isUuid(saved) ? saved : crypto.randomUUID()
    localStorage.setItem('onboardos-chat-session', nextSession)
    setSessionId(nextSession)
    void api<{ messages: { role: 'user' | 'assistant'; content: string; metadata?: ChatAnswer }[] }>(
      `/api/chat/history?session_id=${encodeURIComponent(nextSession)}`,
    )
      .then((result) => {
        setChatMessages(
          result.messages.map((message) => ({
            role: message.role,
            content: message.content,
            response: message.role === 'assistant' ? message.metadata : undefined,
          })),
        )
      })
      .catch(() => undefined)
  }, [])

  const filteredMeetings = useMemo(
    () => meetings.filter((meeting) => meeting.title.toLowerCase().includes(meetingSearch.toLowerCase())),
    [meetings, meetingSearch],
  )

  const filteredGraphNodes = useMemo(
    () => graphNodes.filter((node) => node.data.label.toLowerCase().includes(graphSearch.toLowerCase())),
    [graphNodes, graphSearch],
  )
  const visibleGraphNodeIds = useMemo(() => new Set(filteredGraphNodes.map((node) => node.id)), [filteredGraphNodes])
  const filteredGraphEdges = useMemo(
    () => graphEdges.filter((edge) => visibleGraphNodeIds.has(edge.source) && visibleGraphNodeIds.has(edge.target)),
    [graphEdges, visibleGraphNodeIds],
  )

  async function openMeeting(meeting: Meeting) {
    setActiveMeeting(meeting)
    setMeetingEvidence([])
    try {
      const result = await api<{ evidence: Record<string, unknown>[] }>(`/api/meetings/${encodeURIComponent(meeting.id)}/evidence`)
      setMeetingEvidence(result.evidence)
    } catch (error) {
      setMeetingError(error instanceof Error ? error.message : 'Could not load meeting evidence.')
    }
  }

  async function startNewChat() {
    try {
      const result = await api<{ session_id: string }>('/api/chat/new', { method: 'POST' })
      localStorage.setItem('onboardos-chat-session', result.session_id)
      setSessionId(result.session_id)
      setChatMessages([])
      setChatError('')
    } catch (error) {
      setChatError(error instanceof Error ? error.message : 'Could not start a new chat.')
    }
  }

  async function sendQuestion(event?: FormEvent, suggested?: string) {
    event?.preventDefault()
    const question = (suggested ?? chatDraft).trim()
    if (!question || chatBusy) return
    if (question.length < 3) {
      setChatError('Please enter a question with at least 3 characters.')
      return
    }

    const nextSession = isUuid(sessionId) ? sessionId : crypto.randomUUID()
    if (nextSession !== sessionId) {
      setSessionId(nextSession)
      localStorage.setItem('onboardos-chat-session', nextSession)
    }

    setChatDraft('')
    setChatError('')
    setChatMessages((current) => [...current, { role: 'user', content: question }])
    setChatBusy(true)
    try {
      const response = await api<ChatAnswer>('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, session_id: nextSession }),
      })
      setSessionId(response.session_id)
      localStorage.setItem('onboardos-chat-session', response.session_id)
      setChatMessages((current) => [...current, { role: 'assistant', content: response.answer, response }])
    } catch (error) {
      setChatError(error instanceof Error ? error.message : 'Company memory could not answer right now.')
    } finally {
      setChatBusy(false)
    }
  }

  function navigate(next: Page) {
    setPage(next)
    setActiveMeeting(null)
    if (next === 'Company Memory') setChatError('')
  }

  const currentTitle = page === 'My Onboarding' ? 'My onboarding' : page

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-mark"><Layers3 size={19} strokeWidth={2.5} /></div>
          <div><strong>onboardOS</strong><span>COMPANY MEMORY</span></div>
        </div>
        <div className="workspace-switcher">
          <div className="workspace-icon">N</div>
          <div className="workspace-copy"><strong>Northstar Studio</strong><span>Workspace</span></div>
          <ChevronDown size={15} />
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav aria-label="Main navigation">
          {navItems.map(({ label, icon: Icon }) => (
            <button
              className={`nav-link ${page === label ? 'active' : ''}`}
              key={label}
              onClick={() => navigate(label)}
              type="button"
            >
              <Icon size={17} />
              <span>{label}</span>
              {label === 'Meetings' && stats.meetings > 0 && <span className="nav-count">{stats.meetings}</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className={`connection-card ${health?.database === 'connected' ? 'connected' : 'disconnected'}`}>
            <span className="connection-dot" />
            <div><strong>{health?.database === 'connected' ? 'Memory connected' : 'Memory offline'}</strong><small>FalkorDB graph</small></div>
            <Activity size={15} />
          </div>
          <button className="nav-link muted-link" type="button" onClick={() => setToast('Workspace settings are not configured in this MVP.')}>
            <Settings2 size={17} /><span>Settings</span>
          </button>
          <div className="profile-row">
            <div className="avatar avatar-purple">RS</div>
            <div className="profile-copy"><strong>Riya Sharma</strong><span>New team member</span></div>
            <CircleHelp size={17} className="help-icon" aria-label="Help" />
          </div>
        </div>
      </aside>

      <main className="main-shell">
        <header className="topbar">
          <div className="breadcrumb"><span>Workspace</span><span className="crumb-separator">/</span><strong>{currentTitle}</strong></div>
          <div className="topbar-actions">
            <div className={`mode-pill ${health?.demo_mode ? 'demo' : ''}`}>
              <span className="status-dot" />
              {health?.demo_mode ? 'DETERMINISTIC DEMO' : health?.gemini_configured ? 'GEMINI CONNECTED' : 'GEMINI NOT CONFIGURED'}
            </div>
            <button className="icon-button" type="button" aria-label="Help" onClick={() => setToast('Ask Company Memory for answers with source evidence.')}><CircleHelp size={17} /></button>
            <div className="avatar avatar-purple">RS</div>
          </div>
        </header>

        <div className="page-content">
          {page === 'Dashboard' && (
            <Dashboard
              stats={stats}
              error={statsError}
              onRefresh={() => void refreshDashboard()}
              onUpload={() => setUploadOpen(true)}
              onNavigate={navigate}
              onOpenMeeting={(meeting) => void openMeeting(meeting)}
            />
          )}
          {page === 'Company Memory' && (
            <ChatPage
              messages={chatMessages}
              draft={chatDraft}
              busy={chatBusy}
              error={chatError}
              onDraft={setChatDraft}
              onSend={sendQuestion}
              onNewChat={() => void startNewChat()}
              onOpenCitation={(citation) => void openMeeting({
                id: citation.meeting_id,
                title: citation.meeting_title,
                meeting_date: citation.meeting_date,
              })}
            />
          )}
          {page === 'Meetings' && (
            <MeetingsPage
              meetings={filteredMeetings}
              search={meetingSearch}
              error={meetingError}
              onSearch={setMeetingSearch}
              onUpload={() => setUploadOpen(true)}
              onOpen={(meeting) => void openMeeting(meeting)}
            />
          )}
          {page === 'Knowledge Graph' && (
            <GraphPage
              nodes={filteredGraphNodes}
              edges={filteredGraphEdges}
              allNodeCount={graphNodes.length}
              nodeType={graphType}
              search={graphSearch}
              selectedNode={selectedGraphNode}
              error={graphError}
              loading={graphLoading}
              onType={setGraphType}
              onSearch={setGraphSearch}
              onSelect={setSelectedGraphNode}
            />
          )}
          {page === 'My Onboarding' && (
            <OnboardingPage data={onboarding} error={onboardingError} />
          )}
        </div>
      </main>

      {uploadOpen && (
        <UploadDialog
          demoMode={Boolean(health?.demo_mode)}
          onClose={() => setUploadOpen(false)}
          onUploaded={(message) => {
            setUploadOpen(false)
            setToast(message)
            void refreshDashboard()
            if (page === 'Meetings') {
              void api<Meeting[]>('/api/meetings').then(setMeetings).catch(() => undefined)
            }
          }}
        />
      )}

      {activeMeeting && (
        <div className="drawer-backdrop" role="presentation" onClick={() => setActiveMeeting(null)}>
          <section className="meeting-drawer" role="dialog" aria-modal="true" aria-labelledby="meeting-drawer-title" onClick={(event) => event.stopPropagation()}>
            <div className="drawer-head">
              <div><span className="eyebrow">SOURCE MEETING</span><h2 id="meeting-drawer-title">{activeMeeting.title}</h2><p>{formatDate(activeMeeting.meeting_date)}</p></div>
              <button className="icon-button" type="button" aria-label="Close source meeting" onClick={() => setActiveMeeting(null)}><X size={18} /></button>
            </div>
            <div className="evidence-list">
              {meetingEvidence.length === 0 ? (
                <EmptyState title="No extracted evidence yet" detail={activeMeeting.processing_message ?? 'This source does not have indexed excerpts.'} />
              ) : meetingEvidence.map((item) => (
                <article className="evidence-item" key={String(item.id)}>
                  <div className="evidence-topline"><span className="entity-chip">{String(item.type)}</span><span>{String(item.source_section ?? 'Source excerpt')}</span></div>
                  <strong>{String(item.summary ?? item.description ?? item.content ?? 'Meeting evidence')}</strong>
                  <blockquote>{String(item.source_excerpt ?? '')}</blockquote>
                </article>
              ))}
            </div>
          </section>
        </div>
      )}

      {toast && (
        <div className="toast" role="status">
          <Check size={17} /> <span>{toast}</span>
          <button type="button" aria-label="Dismiss notification" onClick={() => setToast('')}><X size={15} /></button>
        </div>
      )}
    </div>
  )
}

function PageHeading({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children?: React.ReactNode }) {
  return (
    <div className="page-heading">
      <div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>
      {children && <div className="heading-actions">{children}</div>}
    </div>
  )
}

function Dashboard({
  stats, error, onRefresh, onUpload, onNavigate, onOpenMeeting,
}: {
  stats: Stats
  error: string
  onRefresh: () => void
  onUpload: () => void
  onNavigate: (page: Page) => void
  onOpenMeeting: (meeting: Meeting) => void
}) {
  const cards = [
    { label: 'Meetings processed', value: stats.meetings, icon: FileText, tone: 'violet', change: 'Across your workspace' },
    { label: 'People discovered', value: stats.people, icon: Users, tone: 'blue', change: 'Connected to company memory' },
    { label: 'Projects & systems', value: stats.projects + stats.systems, icon: Database, tone: 'green', change: `${stats.projects} projects · ${stats.systems} systems` },
    { label: 'Architecture decisions', value: stats.decisions, icon: ShieldCheck, tone: 'amber', change: `${stats.open_tasks} open action items` },
  ]
  return (
    <>
      <PageHeading eyebrow="THURSDAY, OCTOBER 16" title="Good morning, Riya" description="Your company memory is getting smarter with every conversation.">
        <button className="button button-secondary" type="button" onClick={() => onNavigate('Company Memory')}><MessageSquareText size={16} /> Ask company memory</button>
        <button className="button button-primary" type="button" onClick={onUpload}><Plus size={17} /> Upload transcript</button>
      </PageHeading>
      {error && <ErrorBanner message={error} onRetry={onRefresh} />}
      <section className="stat-grid" aria-label="Company memory statistics">
        {cards.map(({ label, value, icon: Icon, tone, change }) => (
          <article className="stat-card" key={label}>
            <div className={`stat-icon ${tone}`}><Icon size={18} /></div>
            <div className="stat-change"><ArrowDownRight size={13} /> LIVE</div>
            <p>{label}</p><strong>{value.toLocaleString()}</strong><small>{change}</small>
          </article>
        ))}
      </section>
      <section className="dashboard-grid">
        <div className="panel recent-panel">
          <div className="panel-heading"><div><span className="eyebrow">THE LATEST</span><h2>Recent meetings</h2></div><button className="text-button" type="button" onClick={() => onNavigate('Meetings')}>View all <ArrowRight size={14} /></button></div>
          {stats.recent_meetings.length === 0 ? (
            <EmptyState title="No meetings in memory yet" detail="Upload a transcript to begin building your company graph." action={<button className="button button-secondary compact" onClick={onUpload} type="button"><Upload size={14} /> Add a meeting</button>} />
          ) : stats.recent_meetings.map((meeting) => (
            <button className="meeting-row" key={meeting.id} type="button" onClick={() => onOpenMeeting(meeting)}>
              <div className="meeting-icon"><MessageSquareText size={17} /></div>
              <div className="meeting-row-main"><strong>{meeting.title}</strong><span>{formatDate(meeting.meeting_date)} <i /> {meeting.source_name ?? 'Transcript'}</span></div>
              <span className={`status-chip ${meeting.extraction_status === 'failed' ? 'warning' : ''}`}>{meeting.extraction_status ?? 'processed'}</span>
              <ArrowRight size={15} className="row-arrow" />
            </button>
          ))}
        </div>
        <div className="panel decision-panel">
          <div className="panel-heading"><div><span className="eyebrow">WHY WE BUILT IT THIS WAY</span><h2>Decision trail</h2></div><button className="text-button" type="button" onClick={() => onNavigate('Knowledge Graph')}>Explore graph <ArrowRight size={14} /></button></div>
          {stats.recent_decisions.length === 0 ? (
            <EmptyState title="No decisions yet" detail="Confirmed decisions and their rationale will appear here." />
          ) : stats.recent_decisions.map((decision, index) => (
            <article className="decision-row" key={String(decision.id ?? index)}>
              <span className={`decision-marker ${String(decision.status) === 'confirmed' ? 'confirmed' : ''}`} />
              <div><span className="decision-date">{formatDate(String(decision.created_at ?? ''))} · {String(decision.status ?? 'decision')}</span><h3>{String(decision.summary ?? 'Untitled decision')}</h3><p>{String(decision.rationale ?? 'Open the graph to inspect its supporting context.').slice(0, 128)}</p></div>
            </article>
          ))}
        </div>
      </section>
      <section className="bottom-grid">
        <div className="panel question-panel">
          <div className="panel-heading"><div><span className="eyebrow">ASK THE COMPANY</span><h2>Pick up where others left off</h2></div><Sparkles size={19} className="sparkle" /></div>
          <div className="suggested-question-list">
            {suggestedQuestions.map((question) => <button key={question} type="button" onClick={() => onNavigate('Company Memory')}><span>{question}</span><ArrowRight size={15} /></button>)}
          </div>
        </div>
        <div className="panel onboarding-callout">
          <div className="onboarding-graphic"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit-core"><Sparkles size={19} /></div></div>
          <div><span className="eyebrow">YOUR FIRST 90 DAYS</span><h2>Make your first sprint count.</h2><p>See the people, systems, and decisions that matter to your role.</p><button className="text-button" type="button" onClick={() => onNavigate('My Onboarding')}>Open your plan <ArrowRight size={14} /></button></div>
        </div>
      </section>
    </>
  )
}

function ChatPage({
  messages, draft, busy, error, onDraft, onSend, onNewChat, onOpenCitation,
}: {
  messages: ChatMessage[]
  draft: string
  busy: boolean
  error: string
  onDraft: (value: string) => void
  onSend: (event?: FormEvent, suggested?: string) => void
  onNewChat: () => void
  onOpenCitation: (citation: Citation) => void
}) {
  return (
    <>
      <PageHeading eyebrow="COMPANY MEMORY" title="Ask anything. Get the why." description="Answers come from real meetings, decisions, and the people behind them.">
        <button className="button button-secondary" type="button" onClick={onNewChat}><Plus size={16} /> New chat</button>
      </PageHeading>
      <div className={`chat-workspace ${messages.length ? 'has-messages' : ''}`}>
        {messages.length === 0 ? (
          <div className="chat-welcome">
            <div className="chat-welcome-icon"><Bot size={25} /></div>
            <span className="eyebrow">YOUR COMPANY, REMEMBERED</span>
            <h2>What would you like to know?</h2>
            <p>Ask about a decision, a teammate, or how the pieces fit together.</p>
            <div className="chat-suggestions">{suggestedQuestions.map((question) => <button key={question} type="button" onClick={() => onSend(undefined, question)}>{question}<ArrowRight size={14} /></button>)}</div>
          </div>
        ) : (
          <div className="chat-thread">
            {messages.map((message, index) => (
              <article className={`chat-message ${message.role}`} key={`${message.role}-${index}`}>
                <div className={`message-avatar ${message.role}`}>{message.role === 'user' ? 'RS' : <Sparkles size={15} />}</div>
                <div className="message-body">
                  <span className="message-author">{message.role === 'user' ? 'You' : 'Company memory'}</span>
                  <p>{message.content}</p>
                  {message.response && (
                    <>
                      {message.response.warning && <div className="inline-warning">{message.response.warning}</div>}
                      <div className="answer-meta"><span className={`evidence-strength strength-${message.response.evidence_strength}`}>{message.response.evidence_strength} evidence</span><span>{message.response.answer_provider === 'demo' ? 'Deterministic demo' : message.response.answer_provider === 'gemini' ? 'Gemini grounded answer' : 'Source-only answer'}</span></div>
                      {message.response.citations.length > 0 && (
                        <div className="citation-list">
                          <span className="citation-label">SOURCES</span>
                          {message.response.citations.map((citation) => (
                            <button className="citation-card" key={`${citation.meeting_id}-${citation.entity_id}`} type="button" onClick={() => onOpenCitation(citation)}>
                              <span className="citation-icon"><FileText size={15} /></span>
                              <span><strong>{citation.meeting_title}</strong><small>{formatDate(citation.meeting_date)}{citation.section ? ` · ${citation.section}` : ''}{citation.timestamp_start ? ` · ${citation.timestamp_start}${citation.timestamp_end ? `–${citation.timestamp_end}` : ''}` : ''}</small><em>“{citation.excerpt}”</em></span>
                              <ArrowRight size={14} />
                            </button>
                          ))}
                        </div>
                      )}
                      {message.response.related_entities.length > 0 && <div className="related-entities"><span>RELATED</span>{message.response.related_entities.slice(0, 5).map((entity) => <span className="entity-chip" key={entity.id}>{entity.label}: {entity.name}</span>)}</div>}
                    </>
                  )}
                </div>
              </article>
            ))}
            {busy && <div className="thinking-row"><LoaderCircle size={17} className="spin" /> Searching meetings and graph relationships…</div>}
            <div className="thread-end" />
          </div>
        )}
        {error && <div className="chat-error" role="alert">{error}</div>}
        <form className="chat-composer" onSubmit={(event) => onSend(event)}>
          <textarea aria-label="Ask company memory" value={draft} onChange={(event) => onDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void onSend() } }} placeholder="Ask a question about your company…" rows={1} />
          <div className="composer-footer"><span><ShieldCheck size={13} /> Answers cite source meetings · Enter to send</span><button className="send-button" type="submit" disabled={draft.trim().length < 3 || busy} aria-label="Send question"><Send size={16} /></button></div>
        </form>
        <p className="chat-disclaimer">Company memory can make mistakes. Always verify important decisions against the original source.</p>
      </div>
    </>
  )
}

function MeetingsPage({
  meetings, search, error, onSearch, onUpload, onOpen,
}: {
  meetings: Meeting[]
  search: string
  error: string
  onSearch: (value: string) => void
  onUpload: () => void
  onOpen: (meeting: Meeting) => void
}) {
  return (
    <>
      <PageHeading eyebrow="YOUR KNOWLEDGE BASE" title="Meetings" description="Original conversations, made searchable and connected.">
        <button className="button button-primary" type="button" onClick={onUpload}><Upload size={16} /> Upload transcript</button>
      </PageHeading>
      <div className="toolbar panel">
        <div className="search-field"><Search size={16} /><input value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Search meeting titles…" aria-label="Search meetings" /></div>
        <span className="toolbar-count">{meetings.length} {meetings.length === 1 ? 'meeting' : 'meetings'}</span>
      </div>
      {error && <ErrorBanner message={error} />}
      <section className="meeting-list">
        {meetings.length === 0 ? <div className="panel"><EmptyState title="No meetings found" detail={error ? 'Check the API and FalkorDB connection, then retry.' : 'Upload a transcript to create your first source-backed memory.'} action={<button className="button button-primary compact" type="button" onClick={onUpload}><Upload size={14} /> Upload transcript</button>} /></div> : meetings.map((meeting) => (
          <button className="meeting-card panel" key={meeting.id} type="button" onClick={() => onOpen(meeting)}>
            <div className="meeting-icon large"><MessageSquareText size={19} /></div>
            <div className="meeting-card-copy"><div className="meeting-title-line"><h2>{meeting.title}</h2>{meeting.synthetic && <span className="synthetic-chip">SYNTHETIC DEMO</span>}</div><p><span>{formatDate(meeting.meeting_date)}</span><i />{meeting.source_name ?? 'Transcript'}</p></div>
            <span className={`status-chip ${meeting.extraction_status === 'failed' ? 'warning' : ''}`}>{meeting.extraction_status ?? 'processed'}</span>
            <ArrowRight size={16} className="row-arrow" />
          </button>
        ))}
      </section>
    </>
  )
}

function GraphPage({
  nodes, edges, allNodeCount, nodeType, search, selectedNode, error, loading, onType, onSearch, onSelect,
}: {
  nodes: GraphNode[]
  edges: GraphEdge[]
  allNodeCount: number
  nodeType: string
  search: string
  selectedNode: GraphNode | null
  error: string
  loading: boolean
  onType: (value: string) => void
  onSearch: (value: string) => void
  onSelect: (node: GraphNode | null) => void
}) {
  return (
    <>
      <PageHeading eyebrow="CONNECTED COMPANY KNOWLEDGE" title="Knowledge graph" description="Explore how people, projects, systems, and decisions connect.">
        <div className="graph-total"><GitBranch size={15} /><strong>{allNodeCount}</strong> nodes in memory</div>
      </PageHeading>
      <div className="graph-toolbar panel">
        <div className="search-field graph-search"><Search size={16} /><input value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Find a person, project, system…" aria-label="Search graph entities" /></div>
        <label className="select-wrap"><span>Filter</span><select value={nodeType} onChange={(event) => onType(event.target.value)}><option>All types</option><option>Person</option><option>Project</option><option>System</option><option>Meeting</option><option>Decision</option><option>Task</option><option>Fact</option></select><ChevronDown size={14} /></label>
        <span className="toolbar-count">{nodes.length} visible</span>
      </div>
      {error && <ErrorBanner message={error} />}
      <div className="graph-layout">
        <div className="graph-canvas panel">
          {loading ? <div className="graph-message"><LoaderCircle className="spin" size={20} /> Loading FalkorDB graph…</div> : nodes.length === 0 ? <EmptyState title="No graph data available" detail="Start FalkorDB and load the synthetic transcript fixtures to explore the graph." /> : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              fitView
              fitViewOptions={{ padding: 0.25 }}
              onNodeClick={(_event, node) => onSelect(node as GraphNode)}
              onPaneClick={() => onSelect(null)}
              nodesDraggable
              nodesConnectable={false}
              elementsSelectable
              aria-label="Interactive company knowledge graph"
            >
              <Background color="#e5e9f0" gap={22} />
              <Controls />
              <MiniMap nodeColor={(node) => {
                const tone: Record<string, string> = { person: '#a58af4', project: '#63a9e8', system: '#66bd9a', meeting: '#efb86b', decision: '#ed8f83', task: '#86a8d5', fact: '#9babc4' }
                return tone[node.type?.replace('graph-', '') ?? ''] ?? '#cbd2df'
              }} />
            </ReactFlow>
          )}
        </div>
        <aside className="graph-inspector panel">
          {selectedNode ? (
            <>
              <div className="inspector-top"><span className="entity-chip">{selectedNode.data.type}</span><button className="icon-button small" type="button" aria-label="Clear selected node" onClick={() => onSelect(null)}><X size={15} /></button></div>
              <h2>{selectedNode.data.label}</h2>
              <p className="inspector-id">{selectedNode.id}</p>
              <div className="inspector-fields">{Object.entries(selectedNode.data.properties).filter(([key]) => !['id', 'storage_name', 'content_hash'].includes(key)).map(([key, value]) => (
                <div key={key}><span>{key.replaceAll('_', ' ')}</span><p>{String(value)}</p></div>
              ))}</div>
            </>
          ) : (
            <div className="inspector-empty"><div className="inspector-icon"><GitBranch size={18} /></div><h3>Select an entity</h3><p>Click a node to inspect its properties and connections.</p></div>
          )}
          <div className="graph-legend"><span>NODE TYPES</span><div><i className="legend-dot violet" />People<i className="legend-dot blue" />Projects<i className="legend-dot green" />Systems</div><div><i className="legend-dot amber" />Meetings<i className="legend-dot coral" />Decisions</div></div>
        </aside>
      </div>
    </>
  )
}

function OnboardingPage({ data, error }: { data: Record<string, unknown> | null; error: string }) {
  const employee = (data?.employee ?? {}) as Record<string, unknown>
  const recommendations = (data?.recommendations ?? []) as Record<string, unknown>[]
  const questions = (data?.suggested_questions ?? []) as string[]
  return (
    <>
      <PageHeading eyebrow="YOUR FIRST 90 DAYS" title="A thoughtful start." description="A grounded guide to the people, systems, and decisions around your work.">
        {Boolean(data?.is_sample_profile) && <span className="sample-profile-pill">SAMPLE PROFILE</span>}
      </PageHeading>
      {error && <ErrorBanner message={error} />}
      {data?.warning && <div className="inline-warning">{String(data.warning)}</div>}
      <section className="onboarding-hero panel">
        <div className="onboarding-person">
          <div className="avatar avatar-large avatar-purple">{String(employee.name ?? 'S').split(' ').map((part) => part[0]).join('').slice(0, 2)}</div>
          <div><span className="eyebrow">{data?.is_sample_profile ? 'SAMPLE TEAMMATE' : 'YOUR PROFILE'}</span><h2>{String(employee.name ?? 'Loading your profile…')}</h2><p>{String(employee.role ?? 'New team member')} {typeof employee.team === 'string' ? `· ${employee.team}` : ''}</p></div>
        </div>
        <div className="onboarding-progress"><span>ONBOARDING MOMENTUM</span><div className="progress-track"><i style={{ width: `${Math.min(recommendations.length * 12, 92)}%` }} /></div><small>{recommendations.length} evidence-backed recommendations</small></div>
      </section>
      <div className="onboarding-columns">
        <section className="panel recommendations-panel">
          <div className="panel-heading"><div><span className="eyebrow">YOUR NEXT STEPS</span><h2>What to focus on</h2></div><Sparkles size={18} className="sparkle" /></div>
          {recommendations.length === 0 ? <EmptyState title="Your graph is still growing" detail="Upload or seed meeting transcripts to generate recommendations grounded in team knowledge." /> : recommendations.map((item, index) => (
            <article className="recommendation-row" key={String(item.entity_id ?? index)}>
              <span className="step-number">{String(index + 1).padStart(2, '0')}</span>
              <div><h3>{String(item.title)}</h3><p>{String(item.description)}</p><small>{String(item.reason)}</small>
                {Boolean(item.citation) && <blockquote>{String((item.citation as Citation).excerpt)} <span>— {(item.citation as Citation).meeting_title}</span></blockquote>}
              </div>
            </article>
          ))}
        </section>
        <aside className="panel questions-panel">
          <span className="eyebrow">GOOD QUESTIONS TO ASK</span><h2>Curiosity is a superpower.</h2>
          {questions.map((question) => <div className="onboarding-question" key={question}><CircleHelp size={15} /><span>{question}</span></div>)}
          {Boolean(data?.ai_enhanced) && <span className="ai-plan-badge"><Sparkles size={13} /> Organized with Gemini · graph evidence retained</span>}
        </aside>
      </div>
    </>
  )
}

function UploadDialog({ demoMode, onClose, onUploaded }: { demoMode: boolean; onClose: () => void; onUploaded: (message: string) => void }) {
  const [title, setTitle] = useState('')
  const [meetingDate, setMeetingDate] = useState('')
  const [participants, setParticipants] = useState('')
  const [projectName, setProjectName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!file) {
      setError('Choose a .txt or .md transcript to continue.')
      return
    }
    setBusy(true)
    setError('')
    const form = new FormData()
    form.set('title', title)
    if (meetingDate) form.set('meeting_date', meetingDate)
    if (participants) form.set('participants', participants)
    if (projectName) form.set('project_name', projectName)
    form.set('file', file)
    try {
      const result = await api<{ status: string; message: string }>('/api/meetings/upload', { method: 'POST', body: form })
      onUploaded(result.message)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Upload failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className="upload-modal panel" role="dialog" aria-modal="true" aria-labelledby="upload-title" onClick={(event) => event.stopPropagation()}>
        <div className="modal-head"><div><span className="eyebrow">ADD TO COMPANY MEMORY</span><h2 id="upload-title">Upload a transcript</h2><p>Keep the original source. We’ll extract only what the conversation supports.</p></div><button className="icon-button" type="button" aria-label="Close upload form" onClick={onClose}><X size={18} /></button></div>
        {demoMode && <div className="demo-notice"><Sparkles size={15} /> Deterministic demo mode is on. This upload will be stored as section notes; Gemini will not be called.</div>}
        <form onSubmit={(event) => void submit(event)}>
          <label className="form-field"><span>Meeting title <b>*</b></span><input required maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="e.g. Payments architecture sync" /></label>
          <div className="form-row">
            <label className="form-field"><span>Meeting date</span><input type="date" value={meetingDate} onChange={(event) => setMeetingDate(event.target.value)} /></label>
            <label className="form-field"><span>Project</span><input maxLength={160} value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="Optional" /></label>
          </div>
          <label className="form-field"><span>Participants <small>Comma-separated; listed people are marked as attendees</small></span><input value={participants} onChange={(event) => setParticipants(event.target.value)} placeholder="Riya Sharma, Arjun Mehta" /></label>
          <label className="file-drop">
            <input type="file" accept=".txt,.md,text/plain,text/markdown" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
            <div className="file-drop-icon"><Upload size={19} /></div>
            <strong>{file ? file.name : 'Choose a transcript file'}</strong>
            <span>{file ? `${(file.size / 1024).toFixed(0)} KB · ready to upload` : 'Markdown or plain text · up to 2 MB'}</span>
          </label>
          {error && <div className="chat-error" role="alert">{error}</div>}
          <div className="modal-actions"><button className="button button-secondary" type="button" onClick={onClose}>Cancel</button><button className="button button-primary" type="submit" disabled={busy || !file}>{busy ? <><LoaderCircle size={15} className="spin" /> Processing…</> : <><Upload size={15} /> Upload & process</>}</button></div>
        </form>
      </section>
    </div>
  )
}

function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="error-banner" role="alert"><CircleHelp size={17} /><span>{message}</span>{onRetry && <button type="button" onClick={onRetry}>Retry</button>}</div>
}

function EmptyState({ title, detail, action }: { title: string; detail: string; action?: React.ReactNode }) {
  return <div className="empty-state"><div className="empty-icon"><FileText size={18} /></div><strong>{title}</strong><p>{detail}</p>{action}</div>
}

export default App
