import { ArrowUpRight, Download, GitFork, Github, MessageSquare } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { useLang } from "@/i18n/LanguageContext"
import "./DesktopAbout.css"

declare global {
  interface Window {
    readonly zfundpilotDesktopVersion?: string
  }
}

const DESKTOP_REPO = "https://github.com/SuzakuinAyaka/ZFundPilot"
const UPSTREAM_REPO = "https://github.com/Euzohn/ZFundPilot"

export default function DesktopAbout({ version }: { version: string }) {
  const { t } = useLang()
  const links = [
    { label: t.settings.aboutReleases, href: `${DESKTOP_REPO}/releases`, icon: Download },
    { label: t.settings.aboutUpstream, href: UPSTREAM_REPO, icon: GitFork },
    { label: t.settings.aboutIssues, href: `${UPSTREAM_REPO}/issues`, icon: MessageSquare },
  ]

  return (
    <div className="space-y-4">
      <Card className="about-hero space-y-7 bg-[#1343d3] p-5 text-white motion-safe:animate-in motion-safe:fade-in sm:p-8">
        <div className="flex flex-wrap items-center gap-4">
          <img src="/favicon.svg" alt="" width={48} height={48} className="size-12 shrink-0 rounded-xl ring-1 ring-white/25" />
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">ZFundPilot</h2>
            <p className="mt-1 flex flex-wrap items-baseline gap-x-2 text-sm">
              <span className="text-sky-100">{t.settings.version}</span>
              <span className="font-mono font-medium">{version}</span>
            </p>
          </div>
        </div>
        <Button
          asChild
          className="h-auto min-h-11 max-w-full cursor-pointer justify-start gap-3 whitespace-normal bg-sky-50 px-4 py-2 text-start text-slate-900 hover:bg-sky-100 focus-visible:ring-white focus-visible:ring-offset-[#1343d3]"
        >
          <a href={DESKTOP_REPO} target="_blank" rel="noopener noreferrer">
            <Github aria-hidden className="size-5 shrink-0" />
            <span className="min-w-0">
              <span className="block">{t.settings.aboutCurrentRepo}</span>
              <span className="block break-words text-xs font-normal">{new URL(DESKTOP_REPO).pathname.slice(1)}</span>
            </span>
            <ArrowUpRight aria-hidden className="size-4 shrink-0" />
          </a>
        </Button>
      </Card>
      <Card className="divide-y">
        {links.map(({ label, href, icon: Icon }) => (
          <a
            key={href}
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="flex min-h-11 cursor-pointer items-center gap-3 px-5 py-3 text-sm font-medium transition-colors first:rounded-t-xl last:rounded-b-xl hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
          >
            <Icon aria-hidden className="size-4 shrink-0 text-muted-foreground" />
            <span className="flex-1">{label}</span>
            <ArrowUpRight aria-hidden className="size-4 shrink-0 text-muted-foreground" />
          </a>
        ))}
      </Card>
    </div>
  )
}
