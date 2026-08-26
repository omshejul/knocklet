import { LoginPanel } from "@/components/login-panel";

export default function Home() {
  return (
    <main className="grid min-h-screen place-items-center px-5 py-12">
      <div className="w-full max-w-2xl">
        <h1 className="font-heading text-3xl font-semibold tracking-tight">
          LinkedIn CLI
        </h1>
        <LoginPanel />
      </div>
    </main>
  );
}
