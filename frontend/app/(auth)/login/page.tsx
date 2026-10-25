import { Suspense } from "react";

import { AuthForm } from "@/components/auth/auth-form";

export default function LoginPage() {
  return (
    <>
      <p className="text-sm font-semibold text-primary">Welcome back</p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight">Sign in to your workspace</h1>
      <p className="mt-2 text-slate-500">Manage your agents, documents, and deployments.</p>
      <div className="mt-8">
        <Suspense><AuthForm mode="login" /></Suspense>
      </div>
    </>
  );
}
