import { Suspense } from "react";

import { AuthForm } from "@/components/auth/auth-form";

export default function SignupPage() {
  return (
    <>
      <p className="text-sm font-semibold text-primary">Get started</p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight">Create your AutoRAG account</h1>
      <p className="mt-2 text-slate-500">Your first document-grounded agent is minutes away.</p>
      <div className="mt-8">
        <Suspense><AuthForm mode="signup" /></Suspense>
      </div>
    </>
  );
}
