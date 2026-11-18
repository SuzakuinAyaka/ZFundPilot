import { afterEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { LanguageProvider } from "@/i18n/LanguageContext"
import AIChat from "./AIChat"

vi.mock("@/lib/useApi", () => ({
  useApi: () => ({ data: { base_url: "https://example.com", model: "test" }, loading: false }),
}))

vi.mock("@/contexts/ChatContext", () => ({
  useChat: () => ({
    messages: [{
      role: "assistant",
      content: "[来源](https://example.com/source) [应用内](#/transactions) [邮箱](mailto:help@example.com)",
    }],
    archive: [],
    txStatus: {},
  }),
  extractToolCall: () => null,
  stripJsonBlock: (content: string) => content,
}))

afterEach(() => vi.unstubAllGlobals())

describe("AI 对话中的网页链接", () => {
  it("桌面端把外部网页交给系统浏览器入口", () => {
    vi.stubGlobal("isTauri", true)
    render(<LanguageProvider><AIChat /></LanguageProvider>)

    const external = screen.getByRole("link", { name: "来源" })
    expect(external).toHaveAttribute("href", "https://example.com/source")
    expect(external).toHaveAttribute("target", "_blank")
    expect(external).toHaveAttribute("rel", "noopener noreferrer")
    expect(screen.getByRole("link", { name: "应用内" })).not.toHaveAttribute("target")
    expect(screen.getByRole("link", { name: "邮箱" })).not.toHaveAttribute("target")
  })

  it("网页端保留普通链接", () => {
    render(<LanguageProvider><AIChat /></LanguageProvider>)

    expect(screen.getByRole("link", { name: "来源" })).not.toHaveAttribute("target")
  })
})
