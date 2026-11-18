import { afterEach, describe, expect, it, vi } from "vitest"
import { api } from "./client"
import { clearToken, setToken } from "@/lib/auth"

afterEach(() => {
  clearToken()
  vi.unstubAllGlobals()
})

describe("文件下载", () => {
  it.each([
    [api.downloadTemplate, "/api/csv/template", /^transactions_template\.csv$/],
    [api.exportCsv, "/api/csv/export", /^transactions_.+\.csv$/],
    [api.exportZip, "/api/export/zip", /^zfundpilot_backup_.+\.zip$/],
  ] as const)("桌面端将已认证的响应交给系统保存", async (download, url, filename) => {
    setToken("session-token")
    const payload = new Uint8Array([0xef, 0xbb, 0xbf, 0x42]).buffer
    const fetchDownload = vi.fn().mockResolvedValue(new Response(payload))
    const save = vi.fn().mockResolvedValue(true)
    vi.stubGlobal("fetch", fetchDownload)
    vi.stubGlobal("zfundpilotSaveDownload", save)

    await expect(download()).resolves.toBe(true)
    expect(fetchDownload).toHaveBeenCalledWith(url, {
      headers: { Authorization: "Bearer session-token" },
    })
    expect(save).toHaveBeenCalledWith(expect.stringMatching(filename), payload)
  })

  it("取消另存为时不报告保存成功", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("csv")))
    vi.stubGlobal("zfundpilotSaveDownload", vi.fn().mockResolvedValue(false))

    await expect(api.downloadTemplate()).resolves.toBe(false)
  })

  it("浏览器仍通过下载链接保存文件", async () => {
    const anchor = document.createElement("a")
    const click = vi.spyOn(anchor, "click").mockImplementation(() => {})
    vi.spyOn(document, "createElement").mockReturnValue(anchor)
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("csv")))
    vi.stubGlobal("URL", Object.assign(class extends URL {}, {
      createObjectURL: vi.fn().mockReturnValue("blob:download"),
      revokeObjectURL: vi.fn(),
    }))

    await expect(api.downloadTemplate()).resolves.toBe(true)
    expect(click).toHaveBeenCalledOnce()
    expect(anchor.download).toBe("transactions_template.csv")
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:download")
  })
})
