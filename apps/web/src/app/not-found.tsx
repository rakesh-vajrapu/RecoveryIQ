import { ArrowLeft, FileQuestion } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return <div className="surface-panel mx-auto max-w-2xl rounded-3xl p-8 text-center sm:p-12"><span className="mx-auto grid size-14 place-items-center rounded-2xl bg-muted text-muted-foreground"><FileQuestion className="size-6" /></span><p className="eyebrow mt-5">404 · Not found</p><h1 className="mt-2 text-2xl font-bold">That RecoverIQ view does not exist.</h1><p className="mt-3 text-sm leading-6 text-muted-foreground">Return to the Command Center without changing any recovery state.</p><Button className="mt-6" nativeButton={false} render={<Link href="/" />}><ArrowLeft />Command Center</Button></div>;
}
