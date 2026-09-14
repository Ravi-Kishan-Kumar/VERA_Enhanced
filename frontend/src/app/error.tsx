"use client";
import { ErrorState } from "@/components/State";
export default function ErrorPage({ reset }: { reset: () => void }) { return <ErrorState message="This page encountered an unexpected error. Your submitted review may still be processing." retry={reset}/>; }
