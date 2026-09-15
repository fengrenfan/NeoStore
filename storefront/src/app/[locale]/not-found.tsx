import Link from "next/link";

export default function NotFound() {
  return (
    <div className="surface mx-auto max-w-lg space-y-4 p-10 text-center">
      <p className="text-5xl font-bold neon-text">404</p>
      <p className="text-sm text-slate-400">
        We could not find that page. / 没有找到这个页面。
      </p>
      <Link className="btn-ghost" href="/">
        Back to the shop
      </Link>
    </div>
  );
}
