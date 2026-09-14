"use client"

import { Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"
import { useSyncExternalStore } from "react"

import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const mounted = useSyncExternalStore(
    () => () => undefined,
    () => true,
    () => false,
  )
  const dark = mounted && resolvedTheme === "dark"

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-11 rounded-[10px] text-muted-foreground hover:text-foreground"
          onClick={() => setTheme(dark ? "light" : "dark")}
          aria-label={mounted ? `Switch to ${dark ? "light" : "dark"} theme` : "Change color theme"}
        >
          {dark ? <Sun strokeWidth={1.5} /> : <Moon strokeWidth={1.5} />}
        </Button>
      </TooltipTrigger>
      <TooltipContent side="bottom">{dark ? "Light theme" : "Dark theme"}</TooltipContent>
    </Tooltip>
  )
}
