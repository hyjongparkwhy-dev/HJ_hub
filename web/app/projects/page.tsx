import Image from "next/image";
import { PROJECTS, type Project } from "@/lib/projects";

function Card({ p }: { p: Project }) {
  return (
    <li>
      <a className="card" href={p.url} target="_blank" rel="noopener noreferrer" aria-label={`${p.name} 열기`}>
        <span className="card-title">
          <Image className="card-icon" src={p.icon} alt="" width={40} height={40} unoptimized />
          <span className="card-name">{p.name}</span>
        </span>
        <span className="card-desc">{p.description}</span>
        <span className="card-host">
          {p.host}
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M7 17 17 7M8 7h9v9" />
          </svg>
        </span>
      </a>
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
