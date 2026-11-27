import { Suspense } from "react"

import { Skeleton } from "@/components/ui/skeleton"
import { ChatAssistant } from "@/components/vera/chat-assistant"
import { pageMetadata } from "@/lib/metadata"

export const metadata = pageMetadata(
  "Audio Buying Assistant | VERA",
  "Conversational AI shopping advisor for headphones and earbuds powered by Gemini, acoustic benchmarks, and real-time Indian market pricing.",
  "/chat"
)

export default function ChatPage() {
  return (
    <Suspense fallback={<Skeleton className="h-[600px] w-full rounded-2xl" />}>
      <ChatAssistant />
    </Suspense>
  )
}
