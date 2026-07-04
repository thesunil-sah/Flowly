import Link from "next/link";

export default function Home() {
  return (
    <main className="flex flex-1 items-center justify-center p-8">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight">Flowly</h1>
        <p className="mt-3 text-lg text-zinc-500">
          Privacy-first, cookieless web analytics — coming soon.
        </p>
        <p className="mt-6 text-sm text-zinc-500">
          <Link href="/privacy" className="underline">
            How we keep it private
          </Link>
        </p>
      </div>
    </main>
  );
}
