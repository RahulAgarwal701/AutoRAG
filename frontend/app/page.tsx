import Link from "next/link";
import { ArrowRight, Bot, FileSearch, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";

const features = [
  { icon: FileSearch, title: "Grounded answers", text: "Every response is based on your documents and includes citations." },
  { icon: ShieldCheck, title: "Secure by design", text: "Tenant isolation, authenticated APIs, and controlled access to your data." },
  { icon: Bot, title: "Deploy anywhere", text: "Use the REST API or add the chat widget to any website." },
];

export default function HomePage() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <section className="mx-auto flex max-w-6xl flex-col items-center px-6 py-24 text-center sm:py-32">
        <span className="rounded-full border bg-white px-4 py-1.5 text-sm font-medium text-slate-600 shadow-sm">
          Your documents. Your AI agent.
        </span>
        <h1 className="mt-8 max-w-4xl text-balance text-5xl font-bold tracking-tight sm:text-7xl">
          Build trustworthy AI agents in minutes.
        </h1>
        <p className="mt-6 max-w-2xl text-pretty text-lg leading-8 text-slate-600">
          Upload your knowledge, configure your agent, and ship a citation-backed assistant through an API or embeddable widget.
        </p>
        <Button className="mt-10" size="lg" asChild>
          <Link href="/signup">Start building <ArrowRight className="ml-2 size-4" /></Link>
        </Button>
        <div className="mt-24 grid w-full gap-6 text-left md:grid-cols-3">
          {features.map(({ icon: Icon, title, text }) => (
            <article key={title} className="rounded-2xl border bg-white p-6 shadow-sm">
              <Icon className="size-6 text-primary" />
              <h2 className="mt-5 text-lg font-semibold">{title}</h2>
              <p className="mt-2 leading-7 text-slate-600">{text}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

