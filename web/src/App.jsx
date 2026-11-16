import { useEffect, useMemo, useState } from "react";

const ago = (iso) => {
  const h = Math.max(0, (Date.now() - new Date(iso)) / 36e5);
  return h < 24 ? `${Math.round(h)}h ago` : `${Math.round(h / 24)}d ago`;
};

export default function App() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");
  const [src, setSrc] = useState("");

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}news.json`)
      .then((r) => r.json()).then(setData).catch((e) => setErr(String(e)));
  }, []);

  const stories = data?.stories ?? [];
  const names = useMemo(
    () => [...new Set(stories.flatMap((s) => s.sources.map((x) => x.name)))].sort(), [stories]);
  const list = useMemo(() => stories.filter((s) =>
    (!src || s.sources.some((x) => x.name === src)) &&
    `${s.title} ${s.summary}`.toLowerCase().includes(q.toLowerCase())), [stories, q, src]);

  let lastDay = "";
  return (
    <div className="min-h-screen bg-white text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <main className="mx-auto max-w-2xl px-4 py-6">
        <h1 className="text-2xl font-bold">AI News</h1>
        <p className="text-sm text-slate-500">
          {data?.generated ? `Updated ${ago(data.generated)}` : "No data yet"} · {list.length} stories
        </p>
        <div className="my-4 flex gap-2">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search"
            className="min-w-0 flex-1 rounded border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700" />
          <select value={src} onChange={(e) => setSrc(e.target.value)}
            className="max-w-[40%] rounded border border-slate-300 bg-transparent px-2 dark:border-slate-700 dark:bg-slate-950">
            <option value="">All sources</option>
            {names.map((n) => <option key={n}>{n}</option>)}
          </select>
        </div>
        {err && <p className="text-red-500">{err}</p>}
        {list.map((s) => {
          const day = s.published.slice(0, 10);
          const head = day !== lastDay ? <h2 className="mt-6 mb-2 text-sm font-semibold text-slate-500">{day}</h2> : null;
          lastDay = day;
          return (
            <div key={s.id}>
              {head}
              <article className="border-b border-slate-200 py-3 dark:border-slate-800">
                <h3 className="font-semibold">{s.title}</h3>
                {s.summary && <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{s.summary}</p>}
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {s.sources.map((x) => (
                    <a key={x.url} href={x.url} target="_blank" rel="noreferrer"
                      className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-blue-700 dark:bg-slate-800 dark:text-blue-300">
                      {x.name} · {ago(x.published)}
                    </a>
                  ))}
                </div>
              </article>
            </div>
          );
        })}
      </main>
    </div>
  );
}
