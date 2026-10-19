"use client";

import { useEffect, useRef, useState } from "react";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronRight,
  FileText,
  FlaskConical,
  GitCompareArrows,
  LayoutDashboard,
  LoaderCircle,
  LogOut,
  MessageSquare,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Upload,
  X,
  ChartNoAxesCombined,
  Download,
  ArrowUp,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { PdfViewer } from "@/components/PdfViewer";
import {
  api,
  streamResearch,
  type Citation,
  type Experiment,
  type Library,
  type Paper,
  type ResearchAnswer,
} from "@/lib/api";

const pages = [
  {
    id: "dashboard",
    name: "概览",
    en: "Workspace overview",
    icon: LayoutDashboard,
  },
  { id: "library", name: "论文库", en: "Paper library", icon: BookOpen },
  { id: "chat", name: "研究对话", en: "Research chat", icon: MessageSquare },
  {
    id: "experiments",
    name: "实验探索",
    en: "Experiment explorer",
    icon: FlaskConical,
  },
  {
    id: "comparison",
    name: "实验比较",
    en: "Experiment comparison",
    icon: GitCompareArrows,
  },
  { id: "reports", name: "研究报告", en: "Research reports", icon: FileText },
  {
    id: "evaluation",
    name: "评测",
    en: "Evaluation lab",
    icon: ChartNoAxesCombined,
  },
  { id: "settings", name: "设置", en: "Workspace settings", icon: Settings },
];
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});
const show = (value: unknown) =>
  value === null || value === undefined || value === ""
    ? "未知"
    : typeof value === "object"
      ? JSON.stringify(value)
      : String(value);
function Badge({ children }: { children: React.ReactNode }) {
  return <span className="badge">{children}</span>;
}
function Empty({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="empty">
      <BookOpen size={30} />
      <h3>{title}</h3>
      <p>{detail}</p>
    </div>
  );
}
export default function Home() {
  return (
    <QueryClientProvider client={queryClient}>
      <Workspace />
    </QueryClientProvider>
  );
}

function Workspace() {
  const cache = useQueryClient();
  const [token, setToken] = useState(""),
    [ready, setReady] = useState(false),
    [page, setPage] = useState("dashboard"),
    [libraryId, setLibraryId] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [mode, setMode] = useState("hybrid");
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [register, setRegister] = useState(false);
  const [newLibrary, setNewLibrary] = useState(false),
    [libraryName, setLibraryName] = useState("");
  const [selected, setSelected] = useState<string[]>([]),
    [comparison, setComparison] = useState<Record<string, unknown>[]>([]);
  const [filters, setFilters] = useState({
      model_name: "",
      dataset_name: "",
      metric_name: "",
      method_name: "",
      average_bits: "",
      bit_width: "",
      paper_id: "",
    }),
    [detail, setDetail] = useState<Experiment | null>(null),
    [edit, setEdit] = useState(""),
    [reason, setReason] = useState(""),
    [confirmedFields, setConfirmedFields] = useState(""),
    [audit, setAudit] = useState<Record<string, unknown> | null>(null);
  const [experimentOffset, setExperimentOffset] = useState(0);
  useEffect(() => setExperimentOffset(0), [filters, libraryId]);
  const [citation, setCitation] = useState<Citation | null>(null),
    [pdfUrl, setPdfUrl] = useState(""),
    [paperDetail, setPaperDetail] = useState<Paper | null>(null);
  const [extractionOffset, setExtractionOffset] = useState(0),
    [extractionLimit, setExtractionLimit] = useState(5);
  const [query, setQuery] = useState(""),
    [answer, setAnswer] = useState<ResearchAnswer | null>(null),
    [streamText, setStreamText] = useState(""),
    [steps, setSteps] = useState<string[]>([]),
    [conversationId, setConversationId] = useState<string | undefined>(),
    [chatPaper, setChatPaper] = useState("");
  const [history, setHistory] = useState<
      { role: string; content: string; details?: Record<string, unknown> }[]
    >([]),
    [publicQuery, setPublicQuery] = useState(""),
    [publicResults, setPublicResults] = useState<Record<string, unknown>[]>([]),
    [evalJson, setEvalJson] = useState("[]"),
    [evalResult, setEvalResult] = useState<Record<string, unknown> | null>(
      null,
    );
  const controller = useRef<AbortController | null>(null),
    fileInput = useRef<HTMLInputElement | null>(null);
  const authEpoch = useRef(0);
  useEffect(() => {
    setToken(sessionStorage.getItem("papermind_token") || "");
    setReady(true);
  }, []);
  useEffect(() => {
    controller.current?.abort();
    authEpoch.current++;
    setBusy(false);
    setSelected([]);
    setComparison([]);
    setConversationId(undefined);
    setAnswer(null);
    setHistory([]);
    setStreamText("");
    setSteps([]);
    setChatPaper("");
    setCitation(null);
    setPdfUrl("");
    setDetail(null);
    setPaperDetail(null);
    setFilters((f) => ({ ...f, paper_id: "" }));
  }, [libraryId]);
  const libraries = useQuery({
    queryKey: ["libraries", token],
    queryFn: () => api<{ items: Library[] }>("/libraries", token),
    enabled: !!token,
  });
  useEffect(() => {
    if (
      libraries.data?.items.length &&
      !libraries.data.items.some((l) => l.id === libraryId)
    )
      setLibraryId(libraries.data.items[0].id);
  }, [libraries.data, libraryId]);
  const papers = useQuery({
    queryKey: ["papers", token, libraryId],
    queryFn: () =>
      api<{ items: Paper[] }>(
        `/papers?library_id=${libraryId}&limit=100`,
        token,
      ),
    enabled: !!token && !!libraryId,
    refetchInterval: 5000,
  });
  const experiments = useQuery({
    queryKey: ["experiments", token, libraryId, filters, experimentOffset],
    queryFn: () =>
      api<{ items: Experiment[]; next_offset: number | null }>(
        `/search/experiments?offset=${experimentOffset}&limit=50`,
        token,
        {
          method: "POST",
          body: JSON.stringify({
            library_id: libraryId,
            ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)),
          }),
        },
      ),
    enabled: !!token && !!libraryId,
    refetchInterval: page === "experiments" ? 3000 : false,
  });
  const stats = useQuery({
    queryKey: ["stats", token],
    queryFn: () => api<Record<string, number>>("/stats", token),
    enabled: !!token,
    refetchInterval: 10000,
  });
  const settings = useQuery({
    queryKey: ["settings", token],
    queryFn: () => api<Record<string, unknown>>("/settings", token),
    enabled: !!token,
  });
  const conversations = useQuery({
    queryKey: ["conversations", token, libraryId],
    queryFn: () =>
      api<{ items: { id: string; title: string }[] }>(
        `/research/conversations?library_id=${libraryId}`,
        token,
      ),
    enabled: !!token && !!libraryId,
  });
  const runs = useQuery({
    queryKey: ["runs", token],
    queryFn: () =>
      api<{ items: { id: string; status: string }[] }>(
        "/evaluation/runs",
        token,
      ),
    enabled: !!token && page === "evaluation",
  });
  const references = useQuery({
    queryKey: ["references", token, libraryId],
    queryFn: () =>
      api<{ items: { id: string; metadata: Record<string, unknown> }[] }>(
        `/public/references?library_id=${libraryId}`,
        token,
      ),
    enabled: !!token && !!libraryId && page === "library",
  });
  const active = pages.find((p) => p.id === page)!;
  async function action(work: () => Promise<void>) {
    const requestEpoch = authEpoch.current;
    setBusy(true);
    setNotice("");
    try {
      await work();
      await cache.invalidateQueries();
    } catch (e) {
      if (requestEpoch === authEpoch.current)
        setNotice(e instanceof Error ? e.message : String(e));
    } finally {
      if (requestEpoch === authEpoch.current) setBusy(false);
    }
  }
  async function auth(event: React.FormEvent) {
    event.preventDefault();
    await action(async () => {
      const result = await api<{ access_token: string }>(
        register ? "/auth/register" : "/auth/login",
        "",
        { method: "POST", body: JSON.stringify({ email, password }) },
      );
      sessionStorage.setItem("papermind_token", result.access_token);
      setToken(result.access_token);
      setPassword("");
    });
  }
  async function upload(file: File) {
    if (!libraryId) {
      setNotice("请先创建知识库");
      return;
    }
    await action(async () => {
      const data = new FormData();
      data.set("library_id", libraryId);
      data.set("file", file);
      const result = await api<Paper & { duplicate?: boolean }>(
        "/papers/upload",
        token,
        { method: "POST", body: data },
      );
      setNotice(
        result.duplicate
          ? "这篇论文已在知识库中"
          : "论文已上传，正在后台处理。可在状态中查看详细结果。",
      );
    });
  }
  async function openPaperStatus(p: Paper) {
    await action(async () => {
      const r = await api<{
        jobs: {
          details: {
            next_batch?: number;
            extraction?: { next_batch?: number };
          };
        }[];
      }>(`/papers/${p.id}/status`, token);
      setPaperDetail({ ...p, metadata: r });
      setExtractionOffset(
        r.jobs[0]?.details.next_batch ??
          r.jobs[0]?.details.extraction?.next_batch ??
          0,
      );
    });
  }
  async function openCitation(c: Citation) {
    const requestEpoch = authEpoch.current;
    setCitation(c);
    setPdfUrl("");
    try {
      const response = await fetch(`/api/v1/papers/${c.paper_id}/file`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error("无法读取论文");
      const blob = await response.blob();
      if (requestEpoch !== authEpoch.current) return;
      const url = URL.createObjectURL(blob);
      setPdfUrl(url);
    } catch (e) {
      setNotice(String(e));
    }
  }
  useEffect(
    () => () => {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    },
    [pdfUrl],
  );
  useEffect(() => () => controller.current?.abort(), []);
  async function research(event: React.FormEvent, report = false) {
    event.preventDefault();
    if (!query.trim() || !libraryId) return;
    setBusy(true);
    setNotice("");
    setAnswer(null);
    setStreamText("");
    setSteps([]);
    setHistory((h) => [...h, { role: "user", content: query }]);
    const question = query;
    setQuery("");
    controller.current = new AbortController();
    const requestEpoch = authEpoch.current;
    try {
      await streamResearch(
        token,
        {
          query: question,
          library_id: libraryId,
          mode,
          conversation_id: conversationId,
          report,
          paper_id: chatPaper || null,
        },
        (type, data) => {
          if (requestEpoch !== authEpoch.current) return;
          if (type === "status") setSteps((s) => [...s, String(data.node)]);
          if (type === "token") setStreamText((s) => s + String(data.text));
          if (type === "done") {
            setStreamText("");
            const result = data as unknown as ResearchAnswer;
            setAnswer(result);
            setConversationId(result.conversation_id);
            setHistory((h) => [
              ...h,
              { role: "assistant", content: result.answer },
            ]);
          }
          if (type === "error") throw new Error(String(data.message));
        },
        controller.current.signal,
      );
      await cache.invalidateQueries({ queryKey: ["conversations"] });
    } catch (e) {
      if (requestEpoch === authEpoch.current)
        setNotice(e instanceof Error ? e.message : String(e));
    } finally {
      if (requestEpoch === authEpoch.current) setBusy(false);
    }
  }
  function markdown(text: string) {
    const linked = text.replace(
      /\[([0-9a-f-]{36})\]/g,
      "[↗ 证据](#evidence-$1)",
    );
    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <a
              href={href}
              onClick={(e) => {
                if (href?.startsWith("#evidence-")) {
                  e.preventDefault();
                  const c = answer?.citations.find(
                    (c) => c.id === href.slice(10),
                  );
                  if (c) void openCitation(c);
                  else
                    void action(async () => {
                      const item = await api<Citation>(
                        `/evidence/${href.slice(10)}`,
                        token,
                      );
                      await openCitation(item);
                    });
                }
              }}
              target={href?.startsWith("http") ? "_blank" : undefined}
              rel="noreferrer"
            >
              {children}
            </a>
          ),
        }}
      >
        {linked}
      </ReactMarkdown>
    );
  }
  function exportReport() {
    if (!answer) return;
    const content = `# PaperMind Research Report\n\nLibrary: ${libraries.data?.items.find((l) => l.id === libraryId)?.name}\n\n${answer.answer}\n\n## Evidence\n\n${answer.citations.map((c) => `- ${c.id}: paper ${c.paper_id}, page ${c.page ?? "unknown"}\n\n${c.text}`).join("\n\n")}\n\n## Verification and usage\n\n${JSON.stringify({ verification: answer.verification, usage: answer.usage }, null, 2)}`;
    const url = URL.createObjectURL(
      new Blob([content], { type: "text/markdown" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "papermind-report.md";
    link.click();
    URL.revokeObjectURL(url);
  }
  if (!ready)
    return (
      <div className="loading">
        <LoaderCircle className="spin" />
        载入工作台
      </div>
    );
  if (!token)
    return (
      <main className="auth-layout">
        <section className="auth-story">
          <div className="brand">
            <span className="brand-icon">
              <BookOpen size={24} />
            </span>
            PaperMind<span className="brand-dot">.</span>
          </div>
          <div>
            <span className="eyebrow">EVIDENCE BEFORE ANSWERS</span>
            <h1>
              让研究结论，
              <br />
              有据可循。
            </h1>
            <p>从论文原文到实验条件，连接每一条科研证据。</p>
            <div className="auth-points">
              <span>
                <FlaskConical /> 实验感知检索
              </span>
              <span>
                <GitCompareArrows /> 可解释条件比较
              </span>
              <span>
                <ShieldCheck /> 声明与证据校验
              </span>
            </div>
          </div>
          <small>PaperMind · Research Intelligence Workspace</small>
        </section>
        <section className="auth-form">
          <form onSubmit={auth}>
            <span className="eyebrow">YOUR RESEARCH STARTS HERE</span>
            <h2>{register ? "创建研究账户" : "欢迎回来"}</h2>
            <p>登录后访问你的私人论文与实验知识库。</p>
            <label>
              邮箱
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@university.edu"
              />
            </label>
            <label>
              密码
              <input
                type="password"
                required
                minLength={10}
                maxLength={128}
                autoComplete={register ? "new-password" : "current-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="至少 10 个字符"
              />
            </label>
            {notice && (
              <div role="alert" className="notice">
                {notice}
              </div>
            )}
            <button className="primary wide" disabled={busy}>
              {busy ? (
                <LoaderCircle className="spin" size={18} />
              ) : (
                <ArrowUpRight size={18} />
              )}{" "}
              {register ? "创建账户" : "进入工作台"}
            </button>
            <button
              type="button"
              className="text-button wide"
              onClick={() => setRegister(!register)}
            >
              {register ? "已有账户？登录" : "还没有账户？注册"}
            </button>
          </form>
        </section>
      </main>
    );
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-icon">
            <BookOpen size={22} />
          </span>
          PaperMind<span className="brand-dot">.</span>
        </div>
        <div className="workspace-label">RESEARCH WORKSPACE</div>
        <div className="library-select">
          <BookOpen size={15} />
          <select
            aria-label="当前知识库"
            value={libraryId}
            onChange={(e) => setLibraryId(e.target.value)}
          >
            <option value="">选择知识库</option>
            {libraries.data?.items.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
          <button
            title="新建知识库"
            aria-label="新建知识库"
            onClick={() => setNewLibrary(true)}
          >
            <Plus size={16} />
          </button>
        </div>
        <nav>
          {pages.map((p) => (
            <button
              key={p.id}
              className={page === p.id ? "nav-item active" : "nav-item"}
              onClick={() => setPage(p.id)}
            >
              <p.icon size={18} />
              <span>{p.name}</span>
              {page === p.id && <span className="nav-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="evidence-note">
            <ShieldCheck size={18} />
            <div>
              Evidence grounded<small>结论始终连接原文</small>
            </div>
          </div>
          <button
            className="nav-item"
            onClick={() => {
              controller.current?.abort();
              authEpoch.current++;
              sessionStorage.removeItem("papermind_token");
              setRegister(false);
              setToken("");
              setLibraryId("");
              setPage("dashboard");
              setEmail("");
              setPassword("");
              setAnswer(null);
              setHistory([]);
              setConversationId(undefined);
              setQuery("");
              setStreamText("");
              setSelected([]);
              setComparison([]);
              setDetail(null);
              setCitation(null);
              setPdfUrl("");
              setPaperDetail(null);
              setAudit(null);
              setEdit("");
              setReason("");
              setChatPaper("");
              setPublicResults([]);
              setEvalResult(null);
              setEvalJson("[]");
              setNotice("");
              setBusy(false);
              setPublicQuery("");
              setNewLibrary(false);
              setLibraryName("");
              setFilters({
                model_name: "",
                dataset_name: "",
                metric_name: "",
                method_name: "",
                average_bits: "",
                bit_width: "",
                paper_id: "",
              });
              cache.clear();
            }}
          >
            <LogOut size={17} />
            退出账户
          </button>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <span className="muted">工作台</span>
            <ChevronRight size={14} />
            <span>{active.name}</span>
          </div>
          <div className="topbar-right">
            <span className="status-dot" /> 私人研究空间{" "}
            <span className="avatar">PM</span>
          </div>
        </header>
        <div className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">PAPERMIND / {page.toUpperCase()}</div>
              <h1>{active.en}</h1>
              <p>
                {page === "dashboard"
                  ? "整理论文，探索实验，让每个发现都有证据。"
                  : page === "experiments"
                    ? "检索结构化实验记录，核查数值与原始条件。"
                    : "你的研究，始于可靠的证据。"}
              </p>
            </div>
            {["dashboard", "library"].includes(page) && (
              <button
                className="primary"
                onClick={() => fileInput.current?.click()}
                disabled={busy || !libraryId}
              >
                <Upload size={16} />
                上传论文
              </button>
            )}
          </div>
          <input
            ref={fileInput}
            type="file"
            accept="application/pdf"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void upload(f);
              e.target.value = "";
            }}
          />
          {(notice || libraries.error || papers.error || experiments.error) && (
            <div className="notice" role="alert">
              {notice ||
                libraries.error?.message ||
                papers.error?.message ||
                experiments.error?.message}
              <button aria-label="关闭提示" onClick={() => setNotice("")}>
                <X size={15} />
              </button>
            </div>
          )}
          {!libraries.data?.items.length && page !== "settings" && (
            <div className="setup-banner">
              <BookOpen />
              <div>
                <strong>创建你的第一个科研知识库</strong>
                <p>上传真实论文后，检索、实验提取与研究对话将可用。</p>
              </div>
              <button className="primary" onClick={() => setNewLibrary(true)}>
                <Plus size={16} />
                创建知识库
              </button>
            </div>
          )}
          {page === "dashboard" && (
            <>
              <div className="stats-grid">
                {[
                  { label: "论文", key: "papers", icon: FileText },
                  { label: "知识库", key: "libraries", icon: BookOpen },
                  { label: "实验记录", key: "experiments", icon: FlaskConical },
                  {
                    label: "研究对话",
                    key: "conversations",
                    icon: MessageSquare,
                  },
                ].map((s) => (
                  <div className="stat" key={s.key}>
                    <div>
                      <span>{s.label}</span>
                      <s.icon size={18} />
                    </div>
                    <strong>
                      {stats.isLoading ? "—" : (stats.data?.[s.key] ?? 0)}
                    </strong>
                    <small>你的私人空间</small>
                  </div>
                ))}
              </div>
              <section className="research-banner">
                <div>
                  <span className="eyebrow">ASK. COMPARE. VERIFY.</span>
                  <h2>从一个好问题开始。</h2>
                  <p>在论文之间发现联系，在实验条件中验证差异。</p>
                  <button onClick={() => setPage("chat")}>
                    开始研究 <ArrowUpRight size={16} />
                  </button>
                </div>
                <div className="banner-graphic">
                  <div className="orbit one" />
                  <div className="orbit two" />
                  <div className="orbit three" />
                  <div className="graphic-core">
                    <FlaskConical size={36} />
                  </div>
                  <span className="float-label top">
                    <FileText size={14} /> Paper
                  </span>
                  <span className="float-label bottom">
                    <Check size={14} /> Evidence
                  </span>
                </div>
              </section>
              <div className="section-title">
                <h2>
                  最近论文 <span>RECENT PAPERS</span>
                </h2>
                <button
                  className="text-button"
                  onClick={() => setPage("library")}
                >
                  查看全部 <ArrowUpRight size={14} />
                </button>
              </div>
              <PaperList
                items={papers.data?.items.slice(0, 5) || []}
                onOpen={(p) =>
                  void openCitation({
                    id: "",
                    paper_id: p.id,
                    page: 1,
                    text: p.title,
                  })
                }
                onStatus={(p) => void openPaperStatus(p)}
              />
              <div className="section-title">
                <h2>最近研究任务</h2>
              </div>
              {conversations.data?.items.length ? (
                <div className="task-list">
                  {conversations.data.items.slice(0, 5).map((c) => (
                    <button
                      key={c.id}
                      onClick={() =>
                        void action(async () => {
                          const r = await api<{ items: typeof history }>(
                            `/research/conversations/${c.id}`,
                            token,
                          );
                          setHistory(r.items);
                          setConversationId(c.id);
                          setPage("chat");
                        })
                      }
                    >
                      <MessageSquare size={18} />
                      {c.title}
                      <ArrowUpRight size={16} />
                    </button>
                  ))}
                </div>
              ) : (
                <p className="muted">研究对话完成后会自动保存在这里。</p>
              )}
            </>
          )}
          {page === "library" && (
            <>
              <div className="toolbar">
                <span>
                  <BookOpen size={17} />{" "}
                  {libraries.data?.items.find((l) => l.id === libraryId)
                    ?.name || "尚未选择知识库"}
                </span>
                <div>
                  <button
                    onClick={() => {
                      setLibraryName(
                        libraries.data?.items.find((l) => l.id === libraryId)
                          ?.name || "",
                      );
                      setNewLibrary(true);
                    }}
                  >
                    新建知识库
                  </button>
                  {libraryId && (
                    <button
                      className="danger"
                      onClick={() => {
                        if (confirm("删除该知识库及其中的论文、实验与对话？"))
                          void action(async () => {
                            await api(`/libraries/${libraryId}`, token, {
                              method: "DELETE",
                            });
                            setLibraryId("");
                          });
                      }}
                    >
                      删除知识库
                    </button>
                  )}
                </div>
              </div>
              <PaperList
                items={papers.data?.items || []}
                onOpen={(p) =>
                  void openCitation({
                    id: "",
                    paper_id: p.id,
                    page: 1,
                    text: p.title,
                  })
                }
                onStatus={(p) => void openPaperStatus(p)}
                onDelete={(p) => {
                  if (confirm(`删除论文「${p.title}」及关联数据？`))
                    void action(async () => {
                      await api(`/papers/${p.id}`, token, { method: "DELETE" });
                    });
                }}
                onRetry={(p) =>
                  void action(async () => {
                    await api(`/papers/${p.id}/retry`, token, {
                      method: "POST",
                    });
                  })
                }
              />
              <div className="section-title">
                <h2>
                  在线论文检索 <span>OPENALEX</span>
                </h2>
              </div>
              <form
                className="search-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  void action(async () => {
                    const r = await api<{ items: Record<string, unknown>[] }>(
                      `/public/papers?q=${encodeURIComponent(publicQuery)}`,
                      token,
                    );
                    setPublicResults(r.items);
                  });
                }}
              >
                <Search size={18} />
                <input
                  aria-label="在线论文关键词"
                  value={publicQuery}
                  onChange={(e) => setPublicQuery(e.target.value)}
                  placeholder="标题、作者、关键词或 DOI"
                  minLength={2}
                  required
                />
                <button className="primary" disabled={busy}>
                  搜索
                </button>
              </form>
              {publicResults.map((r) => (
                <div className="public-paper" key={String(r.id)}>
                  <strong>{show(r.title)}</strong>
                  <p>
                    {show(r.year)} · {show(r.authors)}
                  </p>
                  <Badge>仅元数据 · 未导入全文</Badge>
                  <button
                    className="text-button"
                    disabled={busy || !libraryId}
                    onClick={() =>
                      void action(async () => {
                        await api("/public/import", token, {
                          method: "POST",
                          body: JSON.stringify({
                            library_id: libraryId,
                            openalex_id: r.id,
                          }),
                        });
                        setNotice("元数据已保存；全文尚未上传或索引。");
                      })
                    }
                  >
                    保存元数据 <Plus size={14} />
                  </button>
                  {typeof r.landing_page === "string" &&
                    /^https:\/\//.test(r.landing_page) && (
                      <a href={r.landing_page} target="_blank" rel="noreferrer">
                        查看来源 <ArrowUpRight size={14} />
                      </a>
                    )}
                </div>
              ))}
              {!!references.data?.items.length && (
                <>
                  <div className="section-title">
                    <h2>已保存的文献元数据</h2>
                  </div>
                  {references.data.items.map((r) => (
                    <div className="public-paper" key={r.id}>
                      <strong>{show(r.metadata.title)}</strong>
                      <p>{show(r.metadata.year)} · 仅元数据 · 未索引全文</p>
                      <button
                        className="text-button danger"
                        disabled={busy}
                        onClick={() =>
                          void action(async () => {
                            await api(`/public/references/${r.id}`, token, {
                              method: "DELETE",
                            });
                          })
                        }
                      >
                        移除元数据
                      </button>
                    </div>
                  ))}
                </>
              )}
            </>
          )}
          {(page === "chat" || page === "reports") && (
            <div className="chat-layout">
              <aside className="conversation-list">
                <button
                  className="outline wide"
                  onClick={() => {
                    setConversationId(undefined);
                    setHistory([]);
                    setAnswer(null);
                    setStreamText("");
                  }}
                >
                  <Plus size={15} />
                  新建研究
                </button>
                {conversations.data?.items.map((c) => (
                  <button
                    key={c.id}
                    className={c.id === conversationId ? "selected" : ""}
                    onClick={() =>
                      void action(async () => {
                        const r = await api<{ items: typeof history }>(
                          `/research/conversations/${c.id}`,
                          token,
                        );
                        setHistory(r.items);
                        setConversationId(c.id);
                        setAnswer(null);
                        setStreamText("");
                      })
                    }
                  >
                    <MessageSquare size={14} />
                    {c.title}
                  </button>
                ))}
              </aside>
              <section className="chat-panel">
                <div className="chat-options">
                  <span>
                    <ShieldCheck size={16} /> 证据核验已启用
                  </span>
                  <select
                    aria-label="检索模式"
                    value={mode}
                    onChange={(e) => setMode(e.target.value)}
                  >
                    <option value="hybrid">Hybrid · Dense + BM25</option>
                    <option value="dense">Dense</option>
                    <option value="bm25">BM25</option>
                    <option value="rerank">Hybrid + Reranker</option>
                  </select>
                  <select
                    aria-label="限定论文"
                    value={chatPaper}
                    onChange={(e) => setChatPaper(e.target.value)}
                  >
                    <option value="">全部论文</option>
                    {papers.data?.items.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.title}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="chat-messages">
                  {!history.length && !streamText && (
                    <div className="chat-welcome">
                      <span className="large-mark">
                        <Sparkles size={30} />
                      </span>
                      <h2>
                        {page === "reports"
                          ? "整理一份有据可查的研究报告"
                          : "今天，想探索什么？"}
                      </h2>
                      <p>提问、查找实验，或比较不同论文的研究条件。</p>
                      <div className="suggestions">
                        {[
                          "这篇论文使用了什么量化策略？",
                          "比较论文库中的 PIQA 实验结果",
                          "总结已有方法的证据与局限性",
                        ].map((q) => (
                          <button key={q} onClick={() => setQuery(q)}>
                            {q}
                            <ArrowUpRight size={14} />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {history.map((m, i) => (
                    <article className={`message ${m.role}`} key={i}>
                      <div className="message-role">
                        {m.role === "user" ? "YOU" : "PAPERMIND"}
                      </div>
                      <div className="prose">{markdown(m.content)}</div>
                    </article>
                  ))}
                  {busy && steps.length > 0 && (
                    <div className="agent-steps">
                      <LoaderCircle className="spin" size={14} />
                      {steps.join(" → ")}
                    </div>
                  )}
                  {busy && streamText && (
                    <div className="prose">{markdown(streamText)}</div>
                  )}
                  {answer && (
                    <>
                      <div className="citation-grid">
                        {answer.citations.map((c) => (
                          <button
                            key={c.id}
                            onClick={() => void openCitation(c)}
                          >
                            <FileText size={17} />
                            <div>
                              <strong>
                                原始证据 · 第 {c.page ?? "未知"} 页
                              </strong>
                              <p>{c.text.slice(0, 90)}</p>
                            </div>
                            <ArrowUpRight size={15} />
                          </button>
                        ))}
                      </div>
                      <details className="trace">
                        <summary>
                          查看执行轨迹与核验结果 ·{" "}
                          {answer.usage?.input_tokens ?? 0} input tokens
                        </summary>
                        <pre>
                          {JSON.stringify(
                            {
                              trace: answer.trace,
                              verification: answer.verification,
                              usage: answer.usage,
                              errors: answer.errors,
                            },
                            null,
                            2,
                          )}
                        </pre>
                      </details>
                      {page === "reports" && (
                        <button className="outline" onClick={exportReport}>
                          <Download size={15} />
                          导出 Markdown
                        </button>
                      )}
                    </>
                  )}
                </div>
                <form
                  className="composer"
                  onSubmit={(e) => void research(e, page === "reports")}
                >
                  <textarea
                    aria-label="研究问题"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="向你的论文库提问…"
                    maxLength={2000}
                    required
                  />
                  <div>
                    <span>回答仅基于当前知识库 · 点击引用可查看原文</span>
                    {busy ? (
                      <button
                        type="button"
                        onClick={() => controller.current?.abort()}
                      >
                        停止
                      </button>
                    ) : (
                      <button
                        aria-label="发送研究问题"
                        className="primary"
                        disabled={!libraryId || !query.trim()}
                      >
                        <ArrowUp size={18} />
                      </button>
                    )}
                  </div>
                </form>
              </section>
            </div>
          )}
          {page === "experiments" && (
            <>
              <div className="toolbar">
                <div className="filter-inputs">
                  {Object.entries(filters)
                    .filter(([key]) => key !== "paper_id")
                    .map(([key, value]) => (
                      <input
                        key={key}
                        aria-label={key}
                        placeholder={
                          (
                            {
                              model_name: "模型名称",
                              dataset_name: "数据集",
                              metric_name: "指标",
                              method_name: "方法",
                              average_bits: "平均位宽",
                              bit_width: "固定精度",
                            } as Record<string, string>
                          )[key]
                        }
                        type={
                          key.endsWith("bits") || key === "bit_width"
                            ? "number"
                            : "text"
                        }
                        step="any"
                        min={
                          key.endsWith("bits") || key === "bit_width"
                            ? 0
                            : undefined
                        }
                        max={
                          key.endsWith("bits") || key === "bit_width"
                            ? 64
                            : undefined
                        }
                        value={value}
                        onChange={(e) =>
                          setFilters({ ...filters, [key]: e.target.value })
                        }
                      />
                    ))}
                  <select
                    aria-label="按论文筛选实验"
                    value={filters.paper_id}
                    onChange={(e) =>
                      setFilters({ ...filters, paper_id: e.target.value })
                    }
                  >
                    <option value="">全部论文</option>
                    {papers.data?.items.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.title}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  className="primary"
                  disabled={selected.length < 2 || busy}
                  onClick={() =>
                    void action(async () => {
                      const r = await api<{ items: Record<string, unknown>[] }>(
                        "/experiments/compare",
                        token,
                        {
                          method: "POST",
                          body: JSON.stringify({ experiment_ids: selected }),
                        },
                      );
                      setComparison(r.items);
                      setPage("comparison");
                    })
                  }
                >
                  <GitCompareArrows size={16} />
                  比较所选 ({selected.length})
                </button>
              </div>
              {experiments.isLoading ? (
                <div className="loading">
                  <LoaderCircle className="spin" />
                </div>
              ) : !experiments.data?.items.length ? (
                <Empty
                  title="尚无实验记录"
                  detail="上传包含实验结果的论文，并配置服务端提取模型。状态页会列出提取限制。"
                />
              ) : (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th />
                        <th>方法 / 模型</th>
                        <th>数据集</th>
                        <th>指标 / 结果</th>
                        <th>平均精度</th>
                        <th>证据状态</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {experiments.data.items.map((e) => (
                        <tr key={e.id}>
                          <td>
                            <input
                              type="checkbox"
                              aria-label={`选择实验 ${e.id}`}
                              checked={selected.includes(e.id)}
                              onChange={(ev) =>
                                setSelected((s) =>
                                  ev.target.checked
                                    ? [...s, e.id]
                                    : s.filter((i) => i !== e.id),
                                )
                              }
                            />
                          </td>
                          <td>
                            <strong>{show(e.record.method_name)}</strong>
                            <small>{show(e.record.model_name)}</small>
                          </td>
                          <td>{show(e.record.dataset_name)}</td>
                          <td>
                            <strong>
                              {show(e.record.metric_value)}{" "}
                              {e.record.metric_unit === "percent" ? "%" : ""}
                            </strong>
                            <small>{show(e.record.metric_name)}</small>
                          </td>
                          <td>{show(e.record.average_bits)} bits</td>
                          <td>
                            <Badge>{show(e.record.verification_status)}</Badge>
                          </td>
                          <td>
                            <button
                              className="text-button"
                              onClick={() =>
                                void action(async () => {
                                  const r = await api<
                                    Experiment & {
                                      original_record: unknown;
                                      revisions: unknown[];
                                    }
                                  >(`/experiments/${e.id}`, token);
                                  setDetail(r);
                                  setConfirmedFields("");
                                  setEdit(JSON.stringify(r.record, null, 2));
                                  setAudit({
                                    original_record: r.original_record,
                                    revisions: r.revisions,
                                  });
                                })
                              }
                            >
                              检查 <ArrowUpRight size={14} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="toolbar">
                <button
                  className="outline"
                  disabled={experimentOffset === 0 || experiments.isFetching}
                  onClick={() =>
                    setExperimentOffset((n) => Math.max(0, n - 50))
                  }
                >
                  上一页
                </button>
                <span>第 {Math.floor(experimentOffset / 50) + 1} 页</span>
                <button
                  className="outline"
                  disabled={
                    experiments.data?.next_offset == null ||
                    experiments.isFetching
                  }
                  onClick={() =>
                    setExperimentOffset(experiments.data!.next_offset!)
                  }
                >
                  下一页
                </button>
              </div>
              <p className="footnote">
                每页最多 50
                条匹配记录。证据状态仅说明测量值；实验条件需逐项核验。未知字段保留为
                null。
              </p>
            </>
          )}
          {page === "comparison" && (
            <>
              {!comparison.length ? (
                <Empty
                  title="选择需要比较的实验"
                  detail="在实验探索中选择至少两条记录，系统将逐项核对实验条件。"
                />
              ) : (
                comparison.map((result, i) => (
                  <section className="comparison-card" key={i}>
                    <div className="section-title">
                      <h2>比较 {i + 1}</h2>
                      <Badge>{show(result.status)}</Badge>
                    </div>
                    <p>{show(result.explanation)}</p>
                    <div className="warnings">
                      {(result.warnings as string[]).map((w) => (
                        <p key={w}>{w}</p>
                      ))}
                    </div>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>实验条件</th>
                            <th>实验 A</th>
                            <th>实验 B</th>
                            <th>校验结果</th>
                            <th>来源</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(
                            result.conditions as {
                              field: string;
                              left: unknown;
                              right: unknown;
                              status: string;
                              left_evidence: string[];
                              right_evidence: string[];
                            }[]
                          ).map((c) => (
                            <tr key={c.field}>
                              <td>{c.field}</td>
                              <td>{show(c.left)}</td>
                              <td>{show(c.right)}</td>
                              <td>
                                <Badge>{c.status}</Badge>
                              </td>
                              <td>
                                {[
                                  ...new Set([
                                    ...c.left_evidence,
                                    ...c.right_evidence,
                                  ]),
                                ].map((id) => (
                                  <button
                                    key={id}
                                    className="text-button"
                                    onClick={() =>
                                      void action(async () => {
                                        const e = await api<Citation>(
                                          `/evidence/${id}`,
                                          token,
                                        );
                                        await openCitation(e);
                                      })
                                    }
                                  >
                                    <ArrowUpRight size={14} />
                                  </button>
                                ))}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                ))
              )}
              <button
                className="outline"
                onClick={() => setPage("experiments")}
              >
                返回实验探索
              </button>
            </>
          )}
          {page === "evaluation" && (
            <section className="panel">
              <h2>Retrieval evaluation</h2>
              <p className="muted">
                输入真实检索问题与当前知识库的证据
                ID。相关性标签由你核查；系统不会自动编造标准答案。
              </p>
              <label>
                问题与相关证据 JSON
                <textarea
                  className="code-input"
                  value={evalJson}
                  onChange={(e) => setEvalJson(e.target.value)}
                  aria-label="评测问题 JSON"
                  placeholder={'[{"query":"…","relevant_ids":["…"]}]'}
                />
              </label>
              <button
                className="primary"
                disabled={busy || !libraryId}
                onClick={() =>
                  void action(async () => {
                    const r = await api<Record<string, unknown>>(
                      "/evaluation/run",
                      token,
                      {
                        method: "POST",
                        body: JSON.stringify({
                          library_id: libraryId,
                          questions: JSON.parse(evalJson),
                          modes: ["bm25", "hybrid", "rerank"],
                        }),
                      },
                    );
                    setEvalResult(r);
                  })
                }
              >
                <ChartNoAxesCombined size={16} />
                运行检索评测
              </button>
              {evalResult && <pre>{JSON.stringify(evalResult, null, 2)}</pre>}
              <h3>历史评测</h3>
              {runs.data?.items.map((r) => (
                <button
                  className="outline"
                  key={r.id}
                  onClick={() =>
                    void action(async () => {
                      setEvalResult(
                        await api(`/evaluation/runs/${r.id}`, token),
                      );
                    })
                  }
                >
                  {r.id.slice(0, 8)} · {r.status}
                </button>
              ))}
            </section>
          )}
          {page === "settings" && (
            <div className="settings-grid">
              <section className="panel">
                <h2>模型与解析服务</h2>
                <p className="muted">模型凭据由服务端环境变量管理。</p>
                {settings.data &&
                  Object.entries(settings.data).map(([k, v]) => (
                    <div className="setting-row" key={k}>
                      <span>{k}</span>
                      <strong>{show(v)}</strong>
                    </div>
                  ))}
                {settings.error && <p role="alert">{settings.error.message}</p>}
              </section>
              <section className="panel">
                <h2>检索偏好</h2>
                <label>
                  当前检索模式
                  <select
                    value={mode}
                    onChange={(e) => setMode(e.target.value)}
                  >
                    <option value="hybrid">Hybrid</option>
                    <option value="dense">Dense</option>
                    <option value="bm25">BM25</option>
                    <option value="rerank">Hybrid + Reranker</option>
                  </select>
                </label>
                <p className="muted">
                  偏好应用于当前会话。改变模型配置后，应为已有论文重新构建对应索引。
                </p>
                <h3>使用统计</h3>
                {stats.data &&
                  Object.entries(stats.data).map(([k, v]) => (
                    <div className="setting-row" key={k}>
                      <span>{k}</span>
                      <strong>{v}</strong>
                    </div>
                  ))}
              </section>
            </div>
          )}
        </div>
        <footer>
          PaperMind <span>Every result deserves a source.</span>
        </footer>
      </main>
      {newLibrary && (
        <div className="modal-backdrop">
          <form
            className="modal small"
            onSubmit={(e) => {
              e.preventDefault();
              void action(async () => {
                const r = await api<Library>("/libraries", token, {
                  method: "POST",
                  body: JSON.stringify({ name: libraryName }),
                });
                setLibraryId(r.id);
                setNewLibrary(false);
                setLibraryName("");
              });
            }}
          >
            <div className="section-title">
              <h2>新建知识库</h2>
              <button
                type="button"
                aria-label="关闭"
                onClick={() => setNewLibrary(false)}
              >
                <X />
              </button>
            </div>
            <label>
              知识库名称
              <input
                autoFocus
                required
                maxLength={200}
                value={libraryName}
                onChange={(e) => setLibraryName(e.target.value)}
                placeholder="LLM & MoE Quantization Research"
              />
            </label>
            <button className="primary wide" disabled={busy}>
              创建知识库
            </button>
          </form>
        </div>
      )}
      {citation && (
        <div className="modal-backdrop">
          <section className="modal pdf-modal">
            <div className="section-title">
              <div>
                <h2>原始论文证据</h2>
                <small>
                  页码：{citation.page ?? "未知"} · 不显示未经验证的区域高亮
                </small>
              </div>
              <button
                aria-label="关闭引用"
                onClick={() => {
                  setCitation(null);
                  setPdfUrl("");
                }}
              >
                <X />
              </button>
            </div>
            <div className="pdf-body">
              <div className="source-snippet">
                <Badge>{citation.id || "PDF"}</Badge>
                <p>{citation.text}</p>
              </div>
              {pdfUrl ? (
                <PdfViewer url={pdfUrl} initialPage={citation.page || 1} />
              ) : (
                <div className="empty">
                  正在加载 PDF；加载失败时请查看顶部提示。
                </div>
              )}
            </div>
          </section>
        </div>
      )}
      {detail && (
        <div className="modal-backdrop">
          <section className="modal">
            <div className="section-title">
              <h2>实验记录与修订</h2>
              <button aria-label="关闭实验详情" onClick={() => setDetail(null)}>
                <X />
              </button>
            </div>
            <p className="muted">
              原始值、条件和证据指针均可检查；保存会重新校验来源并记录审计历史。
            </p>
            <div className="toolbar">
              {detail.record.provenance.evidence_ids.map((id) => (
                <button
                  className="outline"
                  key={id}
                  onClick={() =>
                    void action(async () => {
                      const c = await api<Citation>(`/evidence/${id}`, token);
                      await openCitation(c);
                    })
                  }
                >
                  查看原始证据 <ArrowUpRight size={14} />
                </button>
              ))}
            </div>
            <textarea
              className="code-input tall"
              aria-label="实验记录 JSON"
              value={edit}
              onChange={(e) => setEdit(e.target.value)}
            />
            <label>
              已逐项核对的条件字段（英文名，逗号分隔）
              <input
                aria-label="已核对条件字段"
                value={confirmedFields}
                onChange={(e) => setConfirmedFields(e.target.value)}
                placeholder="例如 model_version, average_bits"
              />
              <span className="muted">
                仅填写已打开原文并核对的条件；保存 JSON 不会自动认证其他条件。
              </span>
            </label>
            <label>
              修订原因
              <input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                minLength={3}
                placeholder="说明本次更改的依据"
              />
            </label>
            <button
              className="primary"
              disabled={busy || reason.length < 3}
              onClick={() =>
                void action(async () => {
                  await api(`/experiments/${detail.id}`, token, {
                    method: "PATCH",
                    body: JSON.stringify({
                      record: JSON.parse(edit),
                      reason,
                      version: detail.version,
                      confirmed_fields: confirmedFields
                        .split(",")
                        .map((f) => f.trim())
                        .filter(Boolean),
                    }),
                  });
                  setDetail(null);
                  setReason("");
                })
              }
            >
              保存并记录修订
            </button>
            <details>
              <summary>AI 原始提取与历史修订</summary>
              <pre>{JSON.stringify(audit, null, 2)}</pre>
            </details>
          </section>
        </div>
      )}
      {paperDetail && (
        <div className="modal-backdrop">
          <section className="modal">
            <div className="section-title">
              <h2>处理状态</h2>
              <button
                aria-label="关闭论文状态"
                onClick={() => setPaperDetail(null)}
              >
                <X />
              </button>
            </div>
            <h3>{paperDetail.title}</h3>
            {notice && (
              <p className="notice" role="alert">
                {notice}
              </p>
            )}
            {paperDetail.status === "ready" && (
              <div className="panel">
                <p>
                  按批次继续或重试提取。已有记录与人工修订保持不变；批次从 0
                  开始，每批最多 6 个数值单元格。
                </p>
                <div className="filter-inputs">
                  <label>
                    起始批次
                    <input
                      type="number"
                      min={0}
                      value={extractionOffset}
                      onChange={(e) =>
                        setExtractionOffset(Number(e.target.value))
                      }
                    />
                  </label>
                  <label>
                    本次批次数
                    <input
                      type="number"
                      min={1}
                      max={20}
                      value={extractionLimit}
                      onChange={(e) =>
                        setExtractionLimit(Number(e.target.value))
                      }
                    />
                  </label>
                </div>
                <button
                  className="primary"
                  disabled={busy}
                  onClick={() =>
                    void action(async () => {
                      await api(`/papers/${paperDetail.id}/extract`, token, {
                        method: "POST",
                        body: JSON.stringify({
                          offset: extractionOffset,
                          limit: extractionLimit,
                        }),
                      });
                      setPaperDetail(null);
                      setNotice(
                        "提取批次已排队；可重新打开状态查看下一批次和失败批次。",
                      );
                    })
                  }
                >
                  继续实验提取
                </button>
              </div>
            )}
            <pre>{JSON.stringify(paperDetail.metadata, null, 2)}</pre>
          </section>
        </div>
      )}
    </div>
  );
}

function PaperList({
  items,
  onOpen,
  onStatus,
  onDelete,
  onRetry,
}: {
  items: Paper[];
  onOpen: (p: Paper) => void;
  onStatus: (p: Paper) => void;
  onDelete?: (p: Paper) => void;
  onRetry?: (p: Paper) => void;
}) {
  return items.length ? (
    <div className="paper-list">
      {items.map((p) => (
        <article className="paper-row" key={p.id}>
          <span className="paper-icon">
            <FileText size={22} />
          </span>
          <div className="paper-info">
            <button onClick={() => onOpen(p)}>{p.title}</button>
            <span>{p.filename}</span>
          </div>
          <Badge>{p.status}</Badge>
          <button className="text-button" onClick={() => onStatus(p)}>
            状态
          </button>
          {p.status === "failed" && onRetry && (
            <button className="text-button" onClick={() => onRetry(p)}>
              重试
            </button>
          )}
          {onDelete && (
            <button className="text-button danger" onClick={() => onDelete(p)}>
              删除
            </button>
          )}
          <button aria-label={`打开 ${p.title}`} onClick={() => onOpen(p)}>
            <ArrowUpRight size={17} />
          </button>
        </article>
      ))}
    </div>
  ) : (
    <Empty
      title="你的下一项发现，从这里开始"
      detail="上传一篇 PDF 论文，系统将解析正文、提取实验并建立证据索引。"
    />
  );
}
