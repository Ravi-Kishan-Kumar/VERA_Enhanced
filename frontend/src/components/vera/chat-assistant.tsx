"use client"

import {
  ArrowRight,
  Battery,
  Bot,
  ExternalLink,
  Headphones,
  Info,
  Radio,
  RefreshCw,
  Send,
  Sparkles,
  User,
  Volume2,
} from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import type { ChatMessage, ChatResponse } from "@/lib/types"
import { cn } from "@/lib/utils"

let messageCounter = 0
function generateId(prefix: string): string {
  messageCounter += 1
  return `${prefix}-${messageCounter}`
}

function getFormattedTime(): string {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

const STARTER_PROMPTS = [
  { label: "Best ANC headphones under ₹10,000", query: "What are the best over-ear ANC headphones under ₹10,000 in India for long travel and office work?" },
  { label: "Punchy bass earbuds for gym (< ₹3,000)", query: "Recommend top TWS earbuds under ₹3,000 with deep bass, sweat resistance, and secure fit for gym workouts." },
  { label: "Best mic for Zoom & office calls", query: "Which wireless earbuds or headphones have the absolute clearest mic quality for office Zoom calls in noisy environments?" },
  { label: "AirPods Pro 2 vs Sony WF-1000XM5", query: "Compare Apple AirPods Pro 2 vs Sony WF-1000XM5 in sound quality, ANC, and Indian pricing." },
  { label: "Audiophile open-back under ₹15k", query: "Suggest the best audiophile headphones under ₹15,000 with natural soundstage and neutral sound profile." },
]

export function ChatAssistant() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "initial-welcome",
      role: "assistant",
      content:
        "Hello! I am **VERA Audio Advisor**, your dedicated acoustic shopping assistant powered by Gemini. Whether you're searching for punchy bass earbuds for workouts, over-ear ANC headphones for flights, or crystal-clear mics for work calls, tell me your budget (in ₹ INR) and use case, and I'll recommend the exact right audio gear for you!",
      timestamp: "Just now",
      follow_up_questions: [
        "Best wireless earbuds under ₹2,500 in India?",
        "Top over-ear noise-cancelling headphones under ₹8,000?",
        "What are the best earbuds with dual pairing multipoint?",
      ],
    },
  ])

  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  async function handleSend(queryText?: string) {
    const textToSend = (queryText || input).trim()
    if (!textToSend || loading) return

    setError(null)
    const userMessage: ChatMessage = {
      id: generateId("user"),
      role: "user",
      content: textToSend,
      timestamp: getFormattedTime(),
    }

    const updatedHistory = [...messages, userMessage]
    setMessages(updatedHistory)
    setInput("")
    setLoading(true)

    try {
      // Build conversation payload for backend
      const historyPayload = updatedHistory
        .filter((m) => m.id !== "initial-welcome")
        .map((m) => ({
          role: m.role,
          content: m.content,
        }))

      const response = await api<ChatResponse>("/chat/message", {
        method: "POST",
        body: JSON.stringify({
          message: textToSend,
          conversation_history: historyPayload,
        }),
      })

      const assistantMessage: ChatMessage = {
        id: generateId("ai"),
        role: "assistant",
        content: response.reply,
        timestamp: getFormattedTime(),
        suggested_products: response.suggested_products,
        follow_up_questions: response.follow_up_questions,
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Failed to get advice. Please try again."
      setError(errMsg)
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  function handleReset() {
    setMessages([
      {
        id: generateId("welcome-reset"),
        role: "assistant",
        content:
          "Conversation cleared! What kind of headphones or earbuds can I help you find today? Tell me your budget or musical preferences to start.",
        timestamp: "Just now",
        follow_up_questions: [
          "Best wireless earbuds under ₹2,500?",
          "Top over-ear ANC headphones under ₹8,000?",
          "Earbuds with best battery life?",
        ],
      },
    ])
    setError(null)
    setInput("")
  }

  // Full markdown renderer: headings, hr, ordered/unordered lists, bold, italic, inline code
  function renderFormattedText(content: string) {
    const lines = content.split("\n")
    // Group consecutive list items so we can wrap them in <ul>/<ol>
    type LineGroup =
      | { type: "heading"; level: number; text: string; key: number }
      | { type: "hr"; key: number }
      | { type: "ul"; items: string[]; key: number }
      | { type: "ol"; items: string[]; key: number }
      | { type: "blank"; key: number }
      | { type: "para"; text: string; key: number }

    const groups: LineGroup[] = []
    let i = 0
    while (i < lines.length) {
      const raw = lines[i]
      const trimmed = raw.trim()

      // Blank line
      if (!trimmed) {
        groups.push({ type: "blank", key: i })
        i++
        continue
      }

      // Headings: ### ## #
      const hMatch = trimmed.match(/^(#{1,6})\s+(.+)$/)
      if (hMatch) {
        groups.push({ type: "heading", level: hMatch[1].length, text: hMatch[2], key: i })
        i++
        continue
      }

      // Horizontal rule: --- or *** or ___
      if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
        groups.push({ type: "hr", key: i })
        i++
        continue
      }

      // Unordered list (collect consecutive)
      if (/^[•\-*]\s/.test(trimmed)) {
        const items: string[] = []
        while (i < lines.length && /^[•\-*]\s/.test(lines[i].trim())) {
          items.push(lines[i].replace(/^[\s•\-*]+/, ""))
          i++
        }
        groups.push({ type: "ul", items, key: i })
        continue
      }

      // Ordered list
      if (/^\d+[.)]\s/.test(trimmed)) {
        const items: string[] = []
        while (i < lines.length && /^\d+[.)]\s/.test(lines[i].trim())) {
          items.push(lines[i].replace(/^\s*\d+[.)]\s+/, ""))
          i++
        }
        groups.push({ type: "ol", items, key: i })
        continue
      }

      groups.push({ type: "para", text: trimmed, key: i })
      i++
    }

    // Inline formatter: **bold**, *italic*, `code`
    function inlineFormat(text: string) {
      const parts = text.split(/(\*\*[\s\S]*?\*\*|\*[\s\S]*?\*|`[^`]+`)/g)
      return parts.map((part, pIdx) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return <strong key={pIdx} className="font-semibold text-foreground">{part.slice(2, -2)}</strong>
        }
        if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
          return <em key={pIdx} className="italic">{part.slice(1, -1)}</em>
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return <code key={pIdx} className="rounded bg-muted px-1 py-0.5 font-mono text-[0.82rem] text-foreground">{part.slice(1, -1)}</code>
        }
        return part
      })
    }

    return groups.map((g) => {
      if (g.type === "blank") return <div key={g.key} className="h-2" />
      if (g.type === "hr") return <hr key={g.key} className="my-2 border-border/60" />
      if (g.type === "heading") {
        const cls = g.level <= 2
          ? "mt-3 mb-1 font-serif font-semibold text-foreground text-base leading-snug"
          : "mt-2 mb-0.5 font-semibold text-foreground text-[0.9rem] leading-snug"
        return <p key={g.key} className={cls}>{inlineFormat(g.text)}</p>
      }
      if (g.type === "ul") {
        return (
          <ul key={g.key} className="mt-1 mb-1 space-y-0.5 pl-0">
            {g.items.map((item, iIdx) => (
              <li key={iIdx} className="flex items-start gap-1.5 text-[0.93rem] leading-relaxed">
                <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary/60" />
                <span>{inlineFormat(item)}</span>
              </li>
            ))}
          </ul>
        )
      }
      if (g.type === "ol") {
        return (
          <ol key={g.key} className="mt-1 mb-1 space-y-0.5 pl-0">
            {g.items.map((item, iIdx) => (
              <li key={iIdx} className="flex items-start gap-2 text-[0.93rem] leading-relaxed">
                <span className="mt-0.5 shrink-0 rounded bg-primary/10 px-1.5 py-0.5 text-[0.75rem] font-semibold text-primary">{iIdx + 1}</span>
                <span>{inlineFormat(item)}</span>
              </li>
            ))}
          </ol>
        )
      }
      // para
      return <p key={g.key} className="text-[0.93rem] leading-relaxed mt-1">{inlineFormat(g.text)}</p>
    })
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 py-6 px-4 sm:px-6">
      {/* Top Header */}
      <div className="flex flex-col gap-2 border-b border-border/80 pb-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
              <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Gemini 2.5 Flash Acoustic Engine
            </span>
            <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] font-mono text-muted-foreground">
              v2.0
            </span>
          </div>
          <h1 className="mt-1 font-serif text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
            Audio Buying Assistant
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Ask anything about headphones and earbuds. Get unbiased acoustic recommendations, specs breakdowns, and real-time Indian pricing.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={handleReset}
          className="self-start gap-1.5 text-xs text-muted-foreground hover:text-foreground sm:self-auto"
        >
          <RefreshCw className="size-3.5" />
          New Chat
        </Button>
      </div>

      {/* Quick Prompt Pills */}
      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
          <Sparkles className="size-3.5 text-amber-500" />
          Popular Audio Queries
        </span>
        <div className="flex flex-wrap gap-2">
          {STARTER_PROMPTS.map((prompt) => (
            <button
              key={prompt.label}
              type="button"
              disabled={loading}
              onClick={() => handleSend(prompt.query)}
              className="inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-card/60 px-3 py-1.5 text-xs font-medium text-foreground transition-all hover:border-primary/40 hover:bg-accent hover:text-accent-foreground disabled:opacity-50 cursor-pointer"
            >
              <span>{prompt.label}</span>
              <ArrowRight className="size-3 text-muted-foreground" />
            </button>
          ))}
        </div>
      </div>

      {/* Chat Messages Container */}
      <div className="flex flex-col gap-4 rounded-xl border border-border bg-card/50 p-4 sm:p-6 shadow-sm min-h-[480px]">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              "flex gap-3",
              msg.role === "user" ? "flex-row-reverse self-end max-w-[85%] sm:max-w-[75%]" : "flex-row self-start max-w-full"
            )}
          >
            {/* Avatar */}
            <div
              className={cn(
                "flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                msg.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20"
              )}
            >
              {msg.role === "user" ? <User className="size-4" /> : <Bot className="size-4" />}
            </div>

            {/* Bubble Content */}
            <div className="flex flex-col gap-2 w-full">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-foreground">
                  {msg.role === "user" ? "You" : "VERA Advisor"}
                </span>
                <span className="text-[10px] text-muted-foreground">{msg.timestamp}</span>
              </div>

              <div
                className={cn(
                  "rounded-2xl px-4 py-3 text-sm leading-relaxed",
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground rounded-tr-sm"
                    : "bg-muted/70 text-foreground border border-border/60 rounded-tl-sm shadow-xs"
                )}
              >
                {renderFormattedText(msg.content)}
              </div>

              {/* Product Cards Attachment */}
              {msg.suggested_products && msg.suggested_products.length > 0 && (
                <div className="mt-2 flex flex-col gap-3">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
                    <Headphones className="size-3.5 text-primary" />
                    Recommended Products in India:
                  </div>

                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                    {msg.suggested_products.map((prod, pIdx) => (
                      <div
                        key={pIdx}
                        className="flex flex-col justify-between rounded-xl border border-border/80 bg-background/90 p-4 shadow-sm hover:border-primary/50 transition-colors"
                      >
                        <div className="flex flex-col gap-2">
                          <div className="flex items-start justify-between gap-2">
                            <span className="inline-block rounded-md bg-muted px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                              {prod.category === "headphones" ? "Over-Ear Headphones" : "TWS Earbuds"}
                            </span>
                            <span className="font-semibold text-emerald-600 dark:text-emerald-400 text-sm">
                              {prod.price_str}
                            </span>
                          </div>

                          <h3 className="font-semibold text-sm leading-snug text-foreground line-clamp-2">
                            {prod.name}
                          </h3>

                          {prod.specs && (
                            <div className="mt-1 flex flex-col gap-1 text-[11px] text-muted-foreground">
                              {prod.specs.driver && (
                                <div className="flex items-center gap-1">
                                  <Volume2 className="size-3 text-primary shrink-0" />
                                  <span className="truncate">{prod.specs.driver}</span>
                                </div>
                              )}
                              {prod.specs.battery && (
                                <div className="flex items-center gap-1">
                                  <Battery className="size-3 text-emerald-500 shrink-0" />
                                  <span className="truncate">{prod.specs.battery}</span>
                                </div>
                              )}
                              {prod.specs.anc && (
                                <div className="flex items-center gap-1">
                                  <Radio className="size-3 text-sky-500 shrink-0" />
                                  <span className="truncate">{prod.specs.anc}</span>
                                </div>
                              )}
                            </div>
                          )}

                          {prod.pros && prod.pros.length > 0 && (
                            <div className="mt-1 flex flex-wrap gap-1">
                              {prod.pros.slice(0, 2).map((pro, prIdx) => (
                                <span
                                  key={prIdx}
                                  className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-600 dark:text-emerald-400 font-medium"
                                >
                                  ✓ {pro}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>

                        {prod.url && (
                          <div className="mt-3 pt-3 border-t border-border/50 flex items-center justify-between">
                            <span className="text-[11px] text-muted-foreground">
                              Available on {prod.merchant || "Amazon.in"}
                            </span>
                            <a
                              href={prod.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
                            >
                              View Deal
                              <ExternalLink className="size-3" />
                            </a>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Follow-up Questions Pills */}
              {msg.follow_up_questions && msg.follow_up_questions.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {msg.follow_up_questions.map((question, qIdx) => (
                    <button
                      key={qIdx}
                      type="button"
                      disabled={loading}
                      onClick={() => handleSend(question)}
                      className="rounded-lg border border-border/80 bg-background px-2.5 py-1 text-xs text-muted-foreground hover:border-primary/40 hover:text-foreground transition-all disabled:opacity-50 text-left cursor-pointer"
                    >
                      💬 {question}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Loading Indicator */}
        {loading && (
          <div className="flex gap-3 self-start">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-amber-500/10 text-amber-600 border border-amber-500/20 text-xs">
              <Bot className="size-4 animate-spin" />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs font-semibold text-foreground">VERA Advisor is thinking...</span>
              <div className="rounded-2xl rounded-tl-sm border border-border/60 bg-muted/60 px-4 py-3 flex items-center gap-1.5">
                <span className="size-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="size-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="size-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: "300ms" }} />
                <span className="ml-2 text-xs text-muted-foreground">Analyzing acoustics, driver specs & market pricing</span>
              </div>
            </div>
          </div>
        )}

        {/* Error Notification */}
        {error && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive flex items-center gap-2">
            <Info className="size-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Input Bar */}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          handleSend()
        }}
        className="sticky bottom-4 z-20 flex gap-2 rounded-xl border border-border bg-background/95 p-2 shadow-lg backdrop-blur-md"
      >
        <input
          ref={inputRef}
          type="text"
          value={input}
          disabled={loading}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask e.g. 'Best wireless headphones under ₹5,000 with strong bass for gym'..."
          className="flex-1 rounded-lg bg-transparent px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-0 disabled:opacity-50"
        />

        <Button
          type="submit"
          disabled={!input.trim() || loading}
          className="gap-1.5 px-4"
        >
          <span>Send</span>
          <Send className="size-3.5" />
        </Button>
      </form>
    </div>
  )
}
