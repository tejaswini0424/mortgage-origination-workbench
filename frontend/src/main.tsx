import { useEffect, useState, type FormEvent } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  NavLink,
  Route,
  Routes,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  ArrowRight,
  Building2,
  FileText,
  FolderOpen,
  Menu,
  Settings,
  UploadCloud,
} from "lucide-react";
import { catalog, caseTools } from "./catalog";
import "./style.css";

type MortgageCase = {
  id: string;
  title: string;
  borrower: string;
  status: string;
  owner: string;
};
type Field = {
  key: string;
  value: string;
  page: number;
  source: string;
  reviewed: boolean;
};
type Document = {
  id: string;
  name: string;
  kind: string;
  status: string;
  fields: Field[];
  error?: string;
};
type Detail = MortgageCase & {
  documents: Document[];
  checks: string[];
  events: string[];
  exports: { id: string; created_at: string; reviewer: string }[];
  calculation?: { dti: number; ltv: number };
  worksheets: Record<string, { name: string; amount?: string; notes: string }>;
};
type User = {
  username: string;
  role: string;
  organization: string;
  active: boolean;
};
async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch("/api/v1" + path, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : "Request failed (" + response.status + ")",
    );
  }
  return response.json();
}
const json = (data: unknown, method = "POST") => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
});
function App() {
  const [registering, setRegistering] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [user, setUser] = useState<User | null>(null),
    [ready, setReady] = useState(false),
    [menu, setMenu] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    api<User>("/session")
      .then(setUser)
      .catch(() => {})
      .finally(() => setReady(true));
  }, []);
  async function login(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    setSubmitting(true);
    try {
      setUser(await api<User>(registering ? "/signup" : "/session", json(Object.fromEntries(data))));
      setRegistering(false);
      setError("");
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  }
  if (!ready) return <main className="login">Connecting to workbench…</main>;
  if (!user)
    return (
      <main className="login">
        <form className="panel" onSubmit={login}>
          <Brand />
          <h1>{registering ? "Create account" : "Sign in"}</h1>
          <p>{registering ? "Create your mortgage processing workspace." : "Access your mortgage processing workspace."}</p>
          <label>
            Username
            <input name="username" autoComplete="username" required />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              autoComplete={registering ? "new-password" : "current-password"}
              required
            />
          </label>
          <button disabled={submitting}>
            {registering ? "Create account" : "Sign in"} <ArrowRight size={16} />
          </button>
          <p><button type="button" className="secondary" disabled={submitting} onClick={() => {
            setRegistering(!registering);
            setError("");
          }}>{registering ? "Back to sign in" : "Create account"}</button></p>
          {error && <p role="alert">{error}</p>}
        </form>
      </main>
    );
  return (
    <div className="shell">
      <aside className={menu ? "open" : ""}>
        <Brand />
        {catalog.map((group) => (
          <section key={group.name}>
            <small>{group.name}</small>
            {group.items.map(([path, label]) => (
              <NavLink key={path} to={path} end onClick={() => setMenu(false)}>
                <FolderOpen size={16} />
                {label}
              </NavLink>
            ))}
          </section>
        ))}
      </aside>
      <div className="workspace">
        <header>
          <button
            className="toggle secondary"
            aria-label="Toggle navigation"
            onClick={() => setMenu(!menu)}
          >
            <Menu size={20} />
          </button>
          <span>Operations workspace</span>
          <div className="account">
            {user.username} · {user.role} · {user.organization}
            <button
              className="secondary"
              onClick={() =>
                api("/session", { method: "DELETE" })
                  .then(() => setUser(null))
                  .catch((e) => setError(String(e)))
              }
            >
              Sign out
            </button>
          </div>
        </header>
        {error && <p role="alert">{error}</p>}
        <main>
          <Routes>
            <Route path="/" element={<Cases dashboard />} />
            <Route path="/cases" element={<Cases />} />
            <Route path="/review" element={<Cases review />} />
            <Route path="/new" element={<NewCase />} />
            <Route path="/cases/:id" element={<CaseRoute user={user} />} />
            {caseTools.map(([key, label]) => (
              <Route
                key={key}
                path={"/tools/" + key}
                element={
                  <CaseTool key={key} user={user} section={key} label={label} />
                }
              />
            ))}
            <Route
              path="/workflow"
              element={
                <>
                  <h1>Workflow overview</h1>
                  <div className="panel">
                    <ol>
                      <li>Create a case for a synthetic borrower.</li>
                      <li>
                        Upload supporting documents and monitor processing.
                      </li>
                      <li>Verify evidence and correct extracted fields.</li>
                      <li>
                        Review discrepancies and download the case packet.
                      </li>
                    </ol>
                  </div>
                </>
              }
            />
            <Route path="/research" element={<Benchmark />} />
            <Route path="/benchmark-datasets" element={<DatasetPage />} />
            <Route
              path="/model-comparison"
              element={<Benchmark view="comparison" />}
            />
            <Route
              path="/robustness"
              element={<Benchmark view="robustness" />}
            />
            <Route path="/audit" element={<Audit />} />
            <Route path="/users" element={<Users user={user} />} />
            <Route
              path="/settings"
              element={<ProcessingSettings user={user} />}
            />
            <Route path="/api-documentation" element={<ApiDocs />} />
            <Route path="/health" element={<Health />} />
            <Route path="*" element={<h1>Page not found</h1>} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
function Brand() {
  return (
    <div className="brand">
      <div>
        <Building2 size={22} />
      </div>
      <span>
        Mortgage<span className="brand-sub">Origination Workbench</span>
      </span>
    </div>
  );
}
function Health() {
  const result = useLoad<{
    status: string;
    database: string;
    worker: string;
    heartbeat_age_seconds: number | null;
  }>("/health");
  return (
    <>
      <h1>System health</h1>
      <section className="panel">
        {result.error ? (
          <p role="alert">{result.error}</p>
        ) : result.data ? (
          <>
            <p>{result.data.status}</p>
            <p>Database · {result.data.database}</p>
            <p>
              Worker · {result.data.worker}
              {result.data.heartbeat_age_seconds == null
                ? ""
                : " · " +
                  result.data.heartbeat_age_seconds +
                  " seconds since heartbeat"}
            </p>
          </>
        ) : (
          <p>Checking services…</p>
        )}
        <button className="secondary" onClick={result.reload}>
          Refresh health
        </button>
      </section>
    </>
  );
}
function Cases({
  dashboard = false,
  review = false,
}: {
  dashboard?: boolean;
  review?: boolean;
}) {
  const [cases, setCases] = useState<MortgageCase[] | null>(null),
    [error, setError] = useState(""),
    [search, setSearch] = useState("");
  useEffect(() => {
    api<MortgageCase[]>("/cases")
      .then(setCases)
      .catch((e) => setError(String(e)));
  }, []);
  const list = cases?.filter(
    (c) =>
      (!review || c.status === "needs_review") &&
      (c.title + " " + c.borrower).toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <>
      <div className="heading">
        <div>
          <div className="eyebrow">LOAN OPERATIONS</div>
          <h1>
            {dashboard
              ? "Portfolio overview"
              : review
                ? "Review queue"
                : "Mortgage cases"}
          </h1>
          <p>Track document intake, review, and case preparation.</p>
        </div>
        <NavLink className="button" to="/new">
          New case <ArrowRight size={16} />
        </NavLink>
      </div>
      {dashboard && (
        <div className="metrics">
          {[
            ["Total cases", cases?.length],
            [
              "In processing",
              cases?.filter((c) => c.status === "processing").length,
            ],
            [
              "Needs review",
              cases?.filter((c) => c.status === "needs_review").length,
            ],
            ["Exported", cases?.filter((c) => c.status === "exported").length],
          ].map(([label, value]) => (
            <div className="panel" key={label}>
              <small>{label}</small>
              <strong>{value ?? "—"}</strong>
            </div>
          ))}
        </div>
      )}
      <section className="panel">
        <div className="heading">
          <h2>{dashboard ? "Case activity" : "Cases"}</h2>
          <input
            aria-label="Search cases"
            placeholder="Search cases"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {error ? (
          <p role="alert">{error}</p>
        ) : !list ? (
          <p>Loading cases…</p>
        ) : !list.length ? (
          <p>No matching cases.</p>
        ) : (
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th>Case</th>
                  <th>Borrower</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {list.map((c) => (
                  <tr key={c.id}>
                    <td>{c.title}</td>
                    <td>{c.borrower}</td>
                    <td>
                      <Badge value={c.status} />
                    </td>
                    <td>
                      <NavLink to={"/cases/" + c.id}>
                        Open <ArrowRight size={13} />
                      </NavLink>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
function Badge({ value }: { value: string }) {
  return <span className={"badge " + value}>{value.replaceAll("_", " ")}</span>;
}
function NewCase() {
  const nav = useNavigate(),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    try {
      const c = await api<MortgageCase>(
        "/cases",
        json(Object.fromEntries(new FormData(e.currentTarget))),
      );
      nav("/cases/" + c.id);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <h1>New mortgage case</h1>
      <p>Use fictional borrower information for this demonstration.</p>
      <form className="panel form" onSubmit={submit}>
        <label>
          Case title
          <input name="title" required maxLength={120} />
        </label>
        <label>
          Borrower name
          <input name="borrower" required maxLength={120} />
        </label>
        <button disabled={busy}>
          Create case <ArrowRight size={16} />
        </button>
        {error && <p role="alert">{error}</p>}
      </form>
    </>
  );
}
function CaseRoute({ user }: { user: User }) {
  const { id } = useParams();
  return id ? <CaseView key={id} user={user} id={id} /> : null;
}
function CaseTool({
  user,
  section,
  label,
}: {
  user: User;
  section: string;
  label: string;
}) {
  const [query, setQuery] = useSearchParams(),
    cases = useLoad<MortgageCase[]>("/cases");
  const id = query.get("case") ?? "";
  return (
    <>
      <h1>{label}</h1>
      <div className="panel">
        <label>
          Select a case
          <select
            value={id}
            onChange={(e) =>
              setQuery(e.target.value ? { case: e.target.value } : {})
            }
          >
            <option value="">Choose an accessible case</option>
            {cases.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
        </label>
        {cases.error && <p role="alert">{cases.error}</p>}
        {cases.data?.length === 0 && (
          <p>
            No accessible cases. <NavLink to="/new">Create a case</NavLink>.
          </p>
        )}
      </div>
      {id && (
        <CaseView key={id + section} id={id} user={user} section={section} />
      )}
    </>
  );
}
function CaseView({
  user,
  id,
  section = "workspace",
}: {
  user: User;
  id: string;
  section?: string;
}) {
  const path = "/cases/" + id;
  const [page, setPage] = useState(1),
    [data, setData] = useState<Detail | null>(null),
    [selected, setSelected] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [calc, setCalc] = useState<{ dti: number; ltv: number } | null>(null);
  useEffect(() => {
    let active = true;
    const refresh = () =>
      api<Detail>(path)
        .then((d) => {
          if (active) setData(d);
        })
        .catch((e) => {
          if (active) setError(String(e));
        });
    refresh();
    const timer = setInterval(refresh, 2000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [path]);
  async function act(task: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await task();
      setData(await api<Detail>(path));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  if (!data)
    return <p role={error ? "alert" : undefined}>{error || "Loading case…"}</p>;
  const ratios = calc ?? data.calculation;
  const show = (...sections: string[]) =>
    section === "workspace" || sections.includes(section);
  const uploads = show("upload"),
    docList = show(
      "documents",
      "viewer",
      "classification",
      "fields",
      "field-review",
    );
  const showDocuments = uploads || docList;
  const doc =
      data.documents.find((d) => d.id === selected) ?? data.documents[0],
    canReview = user.role !== "processor";
  return (
    <>
      <NavLink to="/cases">← All cases</NavLink>
      <div className="heading">
        <div>
          <h1>{data.title}</h1>
          <p>{data.borrower}</p>
        </div>
        <Badge value={data.status} />
      </div>
      {error && <p role="alert">{error}</p>}
      <div className="split">
        {showDocuments && (
          <section className="panel">
            <h2>Documents</h2>
            {uploads && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const form = e.currentTarget;
                  const body = new FormData(form);
                  act(async () => {
                    const d = await api<Document>(path + "/documents", {
                      method: "POST",
                      body,
                    });
                    setSelected(d.id);
                    setPage(1);
                    form.reset();
                  });
                }}
              >
                <label>
                  Upload PDF, PNG, or JPEG
                  <input
                    type="file"
                    name="file"
                    accept=".pdf,.png,.jpg,.jpeg"
                    required
                  />
                </label>
                <button disabled={busy}>
                  <UploadCloud size={16} /> Upload document
                </button>
              </form>
            )}
            {docList && (
              <div className="documents">
                {data.documents.map((d) => (
                  <button
                    className={
                      "secondary " + (d.id === doc?.id ? "selected" : "")
                    }
                    key={d.id}
                    onClick={() => {
                      setSelected(d.id);
                      setPage(1);
                    }}
                  >
                    <FileText size={15} />
                    {d.name}
                    <Badge value={d.status} />
                  </button>
                ))}
              </div>
            )}
            {doc && docList && (
              <>
                <p>Type · {doc.kind.replaceAll("_", " ")}</p>
                <p>{doc.error}</p>
                {doc.status === "failed" && (
                  <button
                    disabled={busy}
                    onClick={() =>
                      act(() =>
                        api("/documents/" + doc.id + "/retry", {
                          method: "POST",
                        }),
                      )
                    }
                  >
                    Retry processing
                  </button>
                )}
                {doc.status === "completed" && (
                  <>
                    {show("viewer", "fields", "field-review") && (
                      <>
                        <label>
                          Source page
                          <input
                            type="number"
                            min="1"
                            max="30"
                            value={page}
                            onChange={(e) =>
                              setPage(Number(e.target.value) || 1)
                            }
                          />
                        </label>
                        <img
                          className="source-page"
                          alt={"Document page " + page}
                          src={"/api/v1/documents/" + doc.id + "/pages/" + page}
                        />
                      </>
                    )}
                    {canReview && show("classification") && (
                      <form
                        className="field"
                        onSubmit={(e) => {
                          e.preventDefault();
                          const kind = new FormData(e.currentTarget).get(
                            "kind",
                          );
                          act(() =>
                            api(
                              "/documents/" + doc.id + "/classification",
                              json({ kind }, "PUT"),
                            ),
                          );
                        }}
                      >
                        <label>
                          Correct classification
                          <select
                            name="kind"
                            key={doc.id + doc.kind}
                            defaultValue={
                              doc.kind === "unknown" ? "" : doc.kind
                            }
                            required
                          >
                            <option value="">Select a document type</option>
                            {[
                              "pay_stub",
                              "bank_statement",
                              "identity",
                              "purchase_agreement",
                            ].map((kind) => (
                              <option key={kind} value={kind}>
                                {kind.replaceAll("_", " ")}
                              </option>
                            ))}
                          </select>
                        </label>
                        <button className="secondary" disabled={busy}>
                          Reprocess as selected type
                        </button>
                      </form>
                    )}
                  </>
                )}
              </>
            )}
          </section>
        )}
        {show("fields", "field-review") && (
          <section className="panel">
            <h2>Extracted evidence</h2>
            {!doc?.fields.length && (
              <p>
                Fields appear after processing. Documents with missing evidence
                can be reviewed manually.
              </p>
            )}
            {doc?.fields.map((f) => (
              <form
                className="field"
                key={doc.id + f.key + f.value + f.reviewed}
                onSubmit={(e) => {
                  e.preventDefault();
                  const value = new FormData(e.currentTarget).get("value");
                  act(() =>
                    api(
                      "/documents/" + doc.id + "/fields/" + f.key,
                      json({ value }, "PUT"),
                    ),
                  );
                }}
              >
                <label>
                  {f.key.replaceAll("_", " ")}
                  <input
                    name="value"
                    defaultValue={f.value}
                    required
                    readOnly={!canReview || !show("field-review")}
                  />
                </label>
                <small>
                  {f.source ? (
                    <>
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => setPage(f.page)}
                      >
                        View page {f.page}
                      </button>{" "}
                      {f.source}
                    </>
                  ) : (
                    "Source evidence missing"
                  )}
                </small>
                {canReview && show("field-review") && (
                  <button className="secondary" disabled={busy}>
                    {f.reviewed ? "Update correction" : "Confirm or correct"}
                  </button>
                )}
              </form>
            ))}
          </section>
        )}
      </div>
      <div className="split">
        {show(
          "checklist",
          "discrepancies",
          "timeline",
          "review-history",
          "summary",
          "exports",
        ) && (
          <section className="panel">
            {section === "summary" && (
              <>
                <h2>Reviewed case summary</h2>
                <p>
                  {
                    data.documents.filter((d) => d.status === "completed")
                      .length
                  }{" "}
                  completed documents ·{" "}
                  {
                    data.documents
                      .flatMap((d) => d.fields)
                      .filter((f) => f.reviewed).length
                  }{" "}
                  confirmed fields
                </p>
                {Object.entries(data.worksheets ?? {}).length > 0 && (
                  <dl>
                    {Object.entries(data.worksheets).map(
                      ([section, values]) => (
                        <div key={section}>
                          <dt>{section}</dt>
                          <dd>
                            {[values.name, values.amount, values.notes]
                              .filter(Boolean)
                              .join(" · ")}
                          </dd>
                        </div>
                      ),
                    )}
                  </dl>
                )}
                {ratios && (
                  <p>
                    DTI {ratios.dti.toFixed(2)}% · LTV {ratios.ltv.toFixed(2)}%
                  </p>
                )}
              </>
            )}
            {show("checklist", "discrepancies", "summary") && (
              <>
                <h2>Document checks</h2>
                {(section === "discrepancies"
                  ? data.checks.filter((c) =>
                      /differs|conflicting|expired/i.test(c),
                    )
                  : data.checks
                ).length ? (
                  <ul>
                    {(section === "discrepancies"
                      ? data.checks.filter((c) =>
                          /differs|conflicting|expired/i.test(c),
                        )
                      : data.checks
                    ).map((c) => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                ) : (
                  <p>No outstanding checks.</p>
                )}
              </>
            )}
            {canReview && show("summary", "exports") && (
              <button
                disabled={busy}
                onClick={() => {
                  const note = window.prompt(
                    "Record your review decision and explain any outstanding checks.",
                  );
                  if (note?.trim())
                    act(() => api(path + "/release", json({ note })));
                }}
              >
                Release reviewed case
              </button>
            )}
            {show("summary", "exports") &&
              (data.status === "ready_for_export" ||
                data.status === "exported") && (
                <p>
                  <a href={"/api/v1" + path + "/exports/latest"}>
                    Download reviewed packet
                  </a>
                </p>
              )}
            {show("exports") && data.exports?.length === 0 && (
              <p>No released packets.</p>
            )}
            {show("exports") && data.exports?.length > 0 && (
              <>
                <h3>Export history</h3>
                <ul>
                  {data.exports.map((version) => (
                    <li key={version.id}>
                      <a href={"/api/v1" + path + "/exports/" + version.id}>
                        {new Date(version.created_at).toLocaleString()} ·{" "}
                        {version.reviewer}
                      </a>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {show("timeline", "review-history") && (
              <>
                <h3>
                  {section === "review-history"
                    ? "Review history"
                    : "Case timeline"}
                </h3>
                <ul>
                  {data.events
                    .filter(
                      (event) =>
                        section !== "review-history" ||
                        /reviewed|released/i.test(event),
                    )
                    .map((event, i) => (
                      <li key={i}>{event}</li>
                    ))}
                </ul>
              </>
            )}
          </section>
        )}
        {show("scenario") && (
          <section className="panel">
            <h2>Indicative loan scenario</h2>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const values = Object.fromEntries(
                  new FormData(e.currentTarget),
                );
                act(async () =>
                  setCalc(await api(path + "/calculations", json(values))),
                );
              }}
            >
              {[
                ["monthly_income", "Gross monthly income"],
                ["monthly_debt", "Monthly debt including proposed payment"],
                ["loan_amount", "Loan amount"],
                ["property_value", "Property value"],
              ].map(([key, label]) => (
                <label key={key}>
                  {label}
                  <input name={key} type="number" min="0" step=".01" required />
                </label>
              ))}
              <button disabled={busy}>Calculate ratios</button>
            </form>
            {ratios && (
              <p>
                Debt-to-income {ratios.dti.toFixed(2)}% · Loan-to-value{" "}
                {ratios.ltv.toFixed(2)}%
              </p>
            )}
          </section>
        )}
      </div>
      {section === "workspace" &&
        (user.role === "admin" || user.username === data.owner) && (
          <CaseAccess path={path} />
        )}{" "}
      {["borrowers", "income", "assets", "liabilities"].includes(section) && (
        <WorksheetForm
          section={section}
          data={data}
          save={(values) =>
            act(() => api(path + "/worksheets/" + section, json(values, "PUT")))
          }
        />
      )}
    </>
  );
}
type BenchmarkRow = {
  documents: number;
  correct_types: number;
  correct: number;
  expected: number;
  unsupported: number;
  processing_errors: number;
  macro_f1: number;
  field_accuracy: number | null;
  coverage: number | null;
  conflict_recall: number | null;
  mean_ms: number | null;
};
type BenchmarkResult = {
  id: string;
  created_at: string;
  status: string;
  report: {
    seed: number;
    fixture_count?: number;
    modes?: Record<string, Record<string, BenchmarkRow>>;
    error?: string;
  };
};
function Benchmark({
  view = "runs",
}: {
  view?: "runs" | "comparison" | "robustness";
}) {
  const history =
    useLoad<{ id: string; created_at: string; seed: number; status: string }[]>(
      "/benchmark/runs",
    );
  const metadata = useLoad<{ vision_enabled: boolean }>("/benchmark");
  const [runId, setRunId] = useState(""),
    [result, setResult] = useState<BenchmarkResult | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const selected = runId || history.data?.[0]?.id;
  useEffect(() => {
    if (!selected) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const report = await api<BenchmarkResult>(
          "/benchmark/runs/" + selected,
        );
        if (!active) return;
        setResult(report);
        if (report.status === "queued" || report.status === "running")
          timer = setTimeout(refresh, 1800);
      } catch (e) {
        if (active) setError(String(e));
      }
    }
    void refresh();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [selected]);
  async function run(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const values = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const report = await api<BenchmarkResult>(
        "/benchmark/runs",
        json({
          seed: Number(values.get("seed")),
          vision: values.has("vision"),
        }),
      );
      setRunId(report.id);
      setResult(report);
      history.reload();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  const complete = result?.status === "completed";
  const running = result?.status === "queued" || result?.status === "running";
  const modes = Object.entries(result?.report.modes ?? {});
  const conditions = Object.keys(modes[0]?.[1] ?? {});
  const percent = (n: number | null) =>
    n == null ? "—" : (100 * n).toFixed(1) + "%";
  const title = {
    runs: "Evaluation runs",
    comparison: "Model comparison",
    robustness: "Robustness analysis",
  }[view];
  return (
    <>
      <h1>{title}</h1>
      <p>
        Compare extraction, evidence coverage, and abstention on identical
        synthetic mortgage fixtures.
      </p>
      {view === "runs" && (
        <form className="panel form" onSubmit={run}>
          <label>
            Reproducibility seed
            <input
              type="number"
              name="seed"
              min="0"
              max="2147483647"
              defaultValue="81"
              required
            />
          </label>
          {metadata.data?.vision_enabled && (
            <label>
              <span>
                <input type="checkbox" name="vision" /> Include configured
                vision model
              </span>
            </label>
          )}
          <button disabled={busy || running}>
            {busy || running ? "Evaluating fixtures…" : "Run evaluation"}
          </button>
        </form>
      )}
      <section className="panel">
        <label>
          Saved evaluation
          <select
            value={selected ?? ""}
            onChange={(e) => {
              setResult(null);
              setError("");
              setRunId(e.target.value);
            }}
          >
            <option value="" disabled>
              Select a run
            </option>
            {history.data?.map((run) => (
              <option key={run.id} value={run.id}>
                {new Date(run.created_at).toLocaleString()} · seed {run.seed}
              </option>
            ))}
          </select>
        </label>
        {(error || history.error) && (
          <p role="alert">{error || history.error}</p>
        )}
        {!selected && <p>Run an evaluation to populate this view.</p>}
        {selected && !result && !error && <p>Loading evaluation…</p>}
        {running && <p role="status">Evaluation {result?.status}.</p>}
        {result?.report.error && <p role="alert">{result.report.error}</p>}
        {complete && (
          <p>
            {result.report.fixture_count} paired fixtures · seed{" "}
            {result.report.seed} ·{" "}
            <a
              href={"/api/v1/benchmark/runs/" + result.id}
              download={"benchmark-" + result.id + ".json"}
            >
              Download report
            </a>
          </p>
        )}
      </section>
      {complete && view === "comparison" && (
        <section className="panel scroll">
          <h2>Aggregate performance</h2>
          <table>
            <thead>
              <tr>
                <th>Pipeline</th>
                <th>Field accuracy</th>
                <th>Classification macro-F1</th>
                <th>Unsupported fields</th>
                <th>Mean milliseconds</th>
              </tr>
            </thead>
            <tbody>
              {modes.map(([mode, data]) => {
                const rows = Object.values(data);
                const total = rows.reduce((a, r) => a + r.expected, 0);
                return (
                  <tr key={mode}>
                    <td>{mode}</td>
                    <td>
                      {percent(
                        total
                          ? rows.reduce((a, r) => a + r.correct, 0) / total
                          : null,
                      )}
                    </td>
                    <td>
                      {percent(
                        rows.reduce((a, r) => a + r.macro_f1, 0) / rows.length,
                      )}
                    </td>
                    <td>{rows.reduce((a, r) => a + r.unsupported, 0)}</td>
                    <td>
                      {Math.round(
                        rows.reduce((a, r) => a + (r.mean_ms ?? 0), 0) /
                          rows.length,
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}
      {complete && view !== "comparison" && (
        <section className="panel scroll">
          <h2>Results by condition</h2>
          <table>
            <thead>
              <tr>
                <th>Condition</th>
                <th>Pipeline</th>
                <th>Field accuracy</th>
                <th>Coverage</th>
                <th>Unsupported</th>
                <th>Conflict recall</th>
                <th>Errors</th>
              </tr>
            </thead>
            <tbody>
              {conditions.map((condition) =>
                modes.map(([mode, data]) => {
                  const row = data[condition];
                  return (
                    <tr key={condition + mode}>
                      <td>{condition.replaceAll("_", " ")}</td>
                      <td>{mode}</td>
                      <td>{percent(row.field_accuracy)}</td>
                      <td>{percent(row.coverage)}</td>
                      <td>{row.unsupported}</td>
                      <td>{percent(row.conflict_recall)}</td>
                      <td>{row.processing_errors}</td>
                    </tr>
                  );
                }),
              )}
            </tbody>
          </table>
        </section>
      )}
    </>
  );
}
createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <App />
  </BrowserRouter>,
);
function useLoad<T>(path: string) {
  const [data, setData] = useState<T | null>(null),
    [error, setError] = useState(""),
    [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    api<T>(path)
      .then((result) => {
        if (active) {
          setData(result);
          setError("");
        }
      })
      .catch((e) => {
        if (active) setError(String(e));
      });
    return () => {
      active = false;
    };
  }, [path, revision]);
  return { data, error, reload: () => setRevision((n) => n + 1) };
}
function CaseAccess({ path }: { path: string }) {
  const access = useLoad<string[]>(path + "/access"),
    [error, setError] = useState("");
  async function update(username: string, method: string) {
    try {
      await api(path + "/access/" + encodeURIComponent(username), { method });
      access.reload();
      setError("");
    } catch (e) {
      setError(String(e));
    }
  }
  return (
    <section className="panel">
      <h2>Case access</h2>
      <p>Assign a processor or reviewer in your organization.</p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const form = e.currentTarget;
          const name = String(new FormData(form).get("username"));
          void update(name, "PUT");
        }}
      >
        <label>
          Account username
          <input name="username" required />
        </label>
        <button>Assign case access</button>
      </form>
      {access.data?.map((username) => (
        <p key={username}>
          {username}{" "}
          <button
            className="secondary"
            onClick={() => update(username, "DELETE")}
          >
            Revoke access for {username}
          </button>
        </p>
      ))}
      {(error || access.error) && <p role="alert">{error || access.error}</p>}
    </section>
  );
}
function WorksheetForm({
  section,
  data,
  save,
}: {
  section: string;
  data: Detail;
  save: (values: unknown) => Promise<void>;
}) {
  const current = data.worksheets?.[section],
    labels: Record<string, string> = {
      income: "Verified gross monthly income",
      assets: "Verified eligible assets",
      liabilities: "Monthly liabilities",
    };
  const evidence = data.documents.flatMap((d) =>
    d.fields
      .filter(
        (f) =>
          f.value &&
          ((section === "income" && f.key === "gross_pay") ||
            (section === "assets" && f.key === "ending_balance") ||
            (section === "borrowers" && /name|holder/.test(f.key))),
      )
      .map((f) => ({ name: d.name, ...f })),
  );
  return (
    <section className="panel">
      <h2>{section === "borrowers" ? "Case parties" : "Worksheet inputs"}</h2>
      {section === "borrowers" && <p>Primary borrower · {data.borrower}</p>}
      {evidence.length > 0 && (
        <ul>
          {evidence.map((f, i) => (
            <li key={i}>
              {f.name} · {f.value} ·{" "}
              {f.reviewed ? "reviewed" : "pending review"}
            </li>
          ))}
        </ul>
      )}
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const values = Object.fromEntries(new FormData(e.currentTarget));
          await save(values);
        }}
      >
        {section === "borrowers" ? (
          <label>
            Co-borrower name
            <input name="name" maxLength={120} defaultValue={current?.name} />
          </label>
        ) : (
          <label>
            {labels[section]}
            <input
              name="amount"
              type="number"
              step=".01"
              min="0"
              required
              defaultValue={current?.amount}
            />
          </label>
        )}
        <label>
          Notes
          <textarea
            name="notes"
            maxLength={1000}
            defaultValue={current?.notes}
          />
        </label>
        <button>Save worksheet</button>
      </form>
    </section>
  );
}
function Users({ user }: { user: User }) {
  if (user.role !== "admin")
    return (
      <>
        <h1>User management</h1>
        <p>Organization administrator access is required.</p>
      </>
    );
  return <UserDirectory administrator={user.username} />;
}
function UserDirectory({ administrator }: { administrator: string }) {
  const users = useLoad<User[]>("/users"),
    [message, setMessage] = useState("");
  return (
    <>
      <h1>User management</h1>
      <section className="panel">
        <h2>Organization accounts</h2>
        <div className="documents">
          {users.data?.map((account) =>
            account.username === administrator ? (
              <p key={account.username}>
                {account.username} · administrator (current account)
              </p>
            ) : (
              <form
                className="field"
                key={account.username + account.role + account.active}
                onSubmit={async (e) => {
                  e.preventDefault();
                  const values = new FormData(e.currentTarget);
                  try {
                    await api(
                      "/users/" + encodeURIComponent(account.username),
                      json(
                        {
                          role: values.get("role"),
                          active: values.has("active"),
                        },
                        "PUT",
                      ),
                    );
                    users.reload();
                    setMessage("Account updated.");
                  } catch (error) {
                    setMessage(String(error));
                  }
                }}
              >
                <strong>{account.username}</strong>
                <label>
                  Role for {account.username}
                  <select name="role" defaultValue={account.role}>
                    <option>processor</option>
                    <option>reviewer</option>
                    <option>admin</option>
                  </select>
                </label>
                <label>
                  <span>
                    <input
                      type="checkbox"
                      name="active"
                      defaultChecked={account.active}
                    />{" "}
                    Active account
                  </span>
                </label>
                <button className="secondary">Save account changes</button>
              </form>
            ),
          )}
        </div>
        {message && <p role="status">{message}</p>}
        {users.error && <p role="alert">{users.error}</p>}
      </section>
      <form
        className="panel form"
        onSubmit={async (e) => {
          e.preventDefault();
          const form = e.currentTarget;
          try {
            await api("/users", json(Object.fromEntries(new FormData(form))));
            form.reset();
            users.reload();
            setMessage("Account created.");
          } catch (e) {
            setMessage(String(e));
          }
        }}
      >
        <h2>Create account</h2>
        <label>
          Username
          <input name="username" required />
        </label>
        <label>
          Role
          <select name="role">
            <option>processor</option>
            <option>reviewer</option>
            <option>admin</option>
          </select>
        </label>
        <label>
          Password
          <input name="password" type="password" minLength={12} required />
        </label>
        <button>Create account</button>
      </form>
    </>
  );
}
function Audit() {
  const rows =
      useLoad<{ case_id: string; title: string; event: string }[]>("/audit"),
    [search, setSearch] = useState("");
  const filtered = rows.data?.filter((row) =>
    (row.title + " " + row.event).toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <>
      <h1>Audit log</h1>
      <section className="panel">
        <label>
          Filter events
          <input value={search} onChange={(e) => setSearch(e.target.value)} />
        </label>
        {rows.error && <p role="alert">{rows.error}</p>}
        {filtered?.length === 0 && <p>No matching events.</p>}
        <ul>
          {filtered?.map((row, i) => (
            <li key={i}>
              <NavLink to={"/cases/" + row.case_id}>{row.title}</NavLink> ·{" "}
              {row.event}
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
function ProcessingSettings({ user }: { user: User }) {
  const result =
    useLoad<Record<string, string | number | boolean>>("/settings");
  const [message, setMessage] = useState("");
  return (
    <>
      <h1>Settings</h1>
      <section className="panel">
        <h2>Effective processing configuration</h2>
        {result.error && <p role="alert">{result.error}</p>}
        <dl>
          {Object.entries(result.data ?? {}).map(([key, value]) => (
            <div key={key}>
              <dt>{key.replaceAll("_", " ")}</dt>
              <dd>
                {typeof value === "boolean"
                  ? value
                    ? "Enabled"
                    : "Disabled"
                  : value}
              </dd>
            </div>
          ))}
        </dl>
        {user.role === "admin" && result.data && (
          <form
            key={String(result.data.document_vision)}
            onSubmit={async (e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              try {
                await api(
                  "/settings",
                  json({ document_vision: data.has("document_vision") }, "PUT"),
                );
                result.reload();
                setMessage("Processing preference saved.");
              } catch (error) {
                setMessage(String(error));
              }
            }}
          >
            <label>
              <span>
                <input
                  name="document_vision"
                  type="checkbox"
                  defaultChecked={Boolean(result.data.document_vision)}
                />{" "}
                Use the configured vision provider for case documents
              </span>
            </label>
            <button>Save processing preference</button>
          </form>
        )}
        {message && <p role="status">{message}</p>}
      </section>
    </>
  );
}
function ApiDocs() {
  return (
    <>
      <h1>API documentation</h1>
      <section className="panel">
        <p>
          Inspect the session, case, access, document, and evaluation endpoints.
        </p>
        <a href="/docs">Open interactive Swagger documentation</a>
        <p>
          <a href="/openapi.json" download>
            Download the OpenAPI specification
          </a>
        </p>
      </section>
    </>
  );
}
function DatasetPage() {
  const metadata = useLoad<{
    conditions: string[];
    document_types: string[];
    modes: string[];
  }>("/benchmark");
  return (
    <>
      <h1>Benchmark datasets</h1>
      <section className="panel">
        <h2>Seeded synthetic mortgage documents</h2>
        <p>
          Each run uses the same ground truth and fixtures for every selected
          pipeline. Fixtures contain fictional borrowers.
        </p>
        {metadata.error && <p role="alert">{metadata.error}</p>}
        <h3>Document types</h3>
        <ul>
          {metadata.data?.document_types.map((type) => (
            <li key={type}>{type.replaceAll("_", " ")}</li>
          ))}
        </ul>
        <h3>Conditions</h3>
        <ul>
          {metadata.data?.conditions.map((condition) => (
            <li key={condition}>{condition.replaceAll("_", " ")}</li>
          ))}
        </ul>
        <NavLink to="/research">Run an evaluation</NavLink>
      </section>
    </>
  );
}
