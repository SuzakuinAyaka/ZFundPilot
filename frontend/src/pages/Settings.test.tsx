import { afterEach, describe, expect, it, vi } from "vitest"
import { render, screen, within } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { LanguageProvider } from "@/i18n/LanguageContext"
import Settings from "./Settings"

vi.mock("@/lib/useApi", () => ({
  useApi: () => ({ data: null, loading: false, error: null, reload: vi.fn() }),
}))

afterEach(() => vi.unstubAllGlobals())

function renderSettings() {
  localStorage.setItem("zfundpilot_lang", "zh")
  render(
    <MemoryRouter initialEntries={["/settings?tab=about"]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <LanguageProvider>
        <Settings />
      </LanguageProvider>
    </MemoryRouter>,
  )
}

describe("桌面端关于设置", () => {
  it("按发行版本展示关于页，并将当前仓库放在首位", () => {
    vi.stubGlobal("zfundpilotDesktopVersion", "0.28.1-r2")
    renderSettings()

    const tabs = screen.getAllByRole("tab")
    const aboutTab = screen.getByRole("tab", { name: "关于", selected: true })
    expect(tabs.slice(-2)[0]).toHaveTextContent("偏好设置")
    expect(tabs.slice(-1)[0]).toBe(aboutTab)
    const panel = screen.getByRole("tabpanel", { name: "关于" })
    expect(within(panel).getByRole("heading", { name: "ZFundPilot" })).toBeVisible()
    expect(within(panel).getByText("0.28.1-r2")).toBeVisible()

    const links = within(panel).getAllByRole("link")
    expect(links[0]).toHaveAccessibleName(/当前仓库/)
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      "https://github.com/SuzakuinAyaka/ZFundPilot",
      "https://github.com/SuzakuinAyaka/ZFundPilot/releases",
      "https://github.com/Euzohn/ZFundPilot",
      "https://github.com/Euzohn/ZFundPilot/issues",
    ])
    for (const link of links) {
      expect(link).toHaveAttribute("target", "_blank")
      expect(link).toHaveAttribute("rel", "noopener noreferrer")
    }
  })

  it("在网页版访问关于链接时回到默认标签", () => {
    renderSettings()

    expect(screen.queryByRole("tab", { name: "关于" })).not.toBeInTheDocument()
    expect(screen.getByRole("tab", { selected: true })).toHaveTextContent("AI 投顾")
  })
})
