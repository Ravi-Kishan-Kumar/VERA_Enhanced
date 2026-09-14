import Link from "next/link";
export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="notice error-state" role="alert"><span className="status-mark" aria-hidden="true">!</span><div><h3>Unable to load this data</h3><p>{message}</p>{retry && <button className="button secondary" onClick={retry}>Try again <span aria-hidden="true">↻</span></button>}</div></div>;
}
export function EmptyState({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="empty-state"><div className="empty-symbol" aria-hidden="true">◇</div><h3>{title}</h3><p>{children}</p><Link href="/" className="text-link">Analyze a review <span aria-hidden="true">↗</span></Link></div>;
}
export function LoadingState({ label = "Loading data" }: { label?: string }) {
  return <div className="loading-state" role="status"><span className="loader" aria-hidden="true"/>{label}…</div>;
}
