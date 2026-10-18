import { PROJECTS, type Project } from "@/lib/projects";

function Card({ p }: { p: Project }) {
  const body = (
    <>
      <span className="card-name">{p.name}</span>
      <span className="card-desc">{p.description}</span>
      <span className="card-host">
        {p.host}
        {p.url ? (
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M7 17 17 7M8 7h9v9" />
          </svg>
        ) : null}
      </span>
    </>
  );
  return (
    <li>
      {p.url ? (
        <a className="card" href={p.url} target="_blank" rel="noopener noreferrer" aria-label={`${p.name} 열기`}>
          {body}
        </a>
      ) : (
        <div className="card card-off">{body}</div>
      )}
    </li>
  );
}

export default function ProjectsPage() {
  return (
    <main>
      <header className="page-head">
        <h1>
          <small>내가 만든 앱</small>
          프로젝트
        </h1>
      </header>
      <ul className="cards">
        {PROJECTS.map((p) => (
          <Card key={p.name} p={p} />
        ))}
      </ul>
    </main>
  );
}
