import { FlipDiskMatrix } from "@/components/ui/flip-disk-matrix";

// ONLY DEFAULT EXPORT WILL BE TREATED AS A DEMO
export default function DemoOne() {
  return (
    <main className="min-h-screen w-full flex flex-col items-center justify-center p-4 md:p-8 font-sans relative overflow-hidden bg-neutral-50 text-neutral-900 dark:bg-[#050505] dark:text-neutral-100 transition-colors duration-500">
      {/* Subtle Ambient Glow (Dark mode only) */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-[#E5FD52]/5 blur-[150px] rounded-full pointer-events-none hidden dark:block" />

      {/* Main Display Container */}
      <div className="flex flex-col items-center justify-center gap-6 md:gap-10 relative z-10 w-full max-w-5xl">
        <header className="flex flex-col items-center gap-2 text-center">
          <div className="text-[10px] md:text-xs font-mono tracking-[0.4em] uppercase text-neutral-500 dark:text-[#E5FD52]/70">
            Responsive Matrix
          </div>
          <h1 className="text-3xl md:text-4xl font-light tracking-tight text-neutral-800 dark:text-neutral-200">
            Electromechanical Clock
          </h1>
        </header>

        {/* The Matrix */}
        <div className="w-full flex justify-center">
          <FlipDiskMatrix />
        </div>
      </div>
    </main>
  );
}
