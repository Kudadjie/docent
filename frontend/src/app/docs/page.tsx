'use client';

import Sidebar from '@/components/Sidebar';
import StatusBanner from '@/components/StatusBanner';
import { useDarkMode } from '@/hooks/useDarkMode';

type Section = {
  id: string;
  label: string;
};

const SECTIONS: Section[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'studio', label: 'Studio' },
  { id: 'reading-queue', label: 'Reading Queue' },
  { id: 'cli', label: 'CLI Reference' },
  { id: 'mcp', label: 'MCP Setup' },
  { id: 'settings', label: 'Settings' },
];

function SectionHeading({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2
      id={id}
      style={{
        fontFamily: 'var(--sans)',
        fontWeight: 600,
        fontSize: 15,
        color: 'var(--fg1)',
        margin: '0 0 16px 0',
        paddingBottom: 10,
        borderBottom: '1px solid var(--border)',
      }}
    >
      {children}
    </h2>
  );
}

function SubHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3
      style={{
        fontFamily: 'var(--sans)',
        fontWeight: 500,
        fontSize: 13,
        color: 'var(--fg1)',
        margin: '20px 0 8px 0',
      }}
    >
      {children}
    </h3>
  );
}

function Prose({ children }: { children: React.ReactNode }) {
  return (
    <p style={{
      fontFamily: 'var(--sans)',
      fontSize: 13,
      lineHeight: 1.7,
      color: 'var(--fg2)',
      margin: '0 0 12px 0',
    }}>
      {children}
    </p>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <code style={{
      fontFamily: 'var(--mono)',
      fontSize: 12,
      background: 'var(--gray100)',
      color: 'var(--fg1)',
      padding: '1px 5px',
      borderRadius: 4,
      border: '1px solid var(--border)',
    }}>
      {children}
    </code>
  );
}

function CodeBlock({ children }: { children: React.ReactNode }) {
  return (
    <pre style={{
      fontFamily: 'var(--mono)',
      fontSize: 12,
      lineHeight: 1.6,
      background: 'var(--gray100)',
      border: '1px solid var(--border)',
      borderRadius: 8,
      padding: '12px 16px',
      margin: '8px 0 16px 0',
      overflowX: 'auto',
      color: 'var(--fg2)',
    }}>
      {children}
    </pre>
  );
}

function CommandTable({ rows }: { rows: { cmd: string; desc: string }[] }) {
  return (
    <div style={{
      border: '1px solid var(--border)',
      borderRadius: 8,
      overflow: 'hidden',
      marginBottom: 20,
    }}>
      {rows.map((row, i) => (
        <div
          key={i}
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1.6fr',
            borderBottom: i < rows.length - 1 ? '1px solid var(--border)' : 'none',
          }}
        >
          <div style={{
            padding: '9px 14px',
            fontFamily: 'var(--mono)',
            fontSize: 12,
            color: 'var(--fg1)',
            background: 'var(--gray100)',
            borderRight: '1px solid var(--border)',
          }}>
            {row.cmd}
          </div>
          <div style={{
            padding: '9px 14px',
            fontFamily: 'var(--sans)',
            fontSize: 12,
            color: 'var(--fg2)',
            lineHeight: 1.5,
          }}>
            {row.desc}
          </div>
        </div>
      ))}
    </div>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 10,
      padding: '24px 28px',
      marginBottom: 20,
    }}>
      {children}
    </div>
  );
}

export default function DocsPage() {
  const { dark, toggleDark } = useDarkMode();

  function scrollTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <Sidebar active="docs" queueCount={0} dark={dark} />

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        <StatusBanner dark={dark} onToggleDark={toggleDark} />

        {/* Body — two-column: TOC left, content right */}
        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>

          {/* TOC */}
          <div style={{
            width: 176,
            flexShrink: 0,
            borderRight: '1px solid var(--border)',
            padding: '24px 0',
            overflow: 'auto',
          }}>
            <div style={{
              fontFamily: 'var(--sans)',
              fontSize: 10,
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.6px',
              color: 'var(--fg4)',
              padding: '0 18px 8px',
            }}>
              On this page
            </div>
            {SECTIONS.map((s) => (
              <button
                key={s.id}
                onClick={() => scrollTo(s.id)}
                style={{
                  display: 'block',
                  width: '100%',
                  textAlign: 'left',
                  padding: '5px 18px',
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  fontFamily: 'var(--sans)',
                  fontSize: 12,
                  color: 'var(--fg3)',
                }}
              >
                {s.label}
              </button>
            ))}
          </div>

          {/* Content — hero wash bleeding from the top via background-image */}
          <div style={{ flex: 1, padding: '28px 40px', overflow: 'auto', maxWidth: 820,
            backgroundImage: 'var(--hero-grad)',
            backgroundRepeat: 'no-repeat',
            backgroundSize: '100% 320px',
            backgroundAttachment: 'local',
          }}>

            {/* Overview */}
            <Card>
              <SectionHeading id="overview">Overview</SectionHeading>
              <Prose>
                Docent is a CLI-based control center for grad-school workflows. It exposes a plugin
                architecture — each tool (currently <strong>Reading Queue</strong>) registers actions
                that are callable from the terminal, from Claude via MCP, or from this UI.
              </Prose>
              <Prose>
                Documents live in <strong>Mendeley</strong>. Docent syncs from a named Mendeley collection
                and maintains a lightweight local queue. You never add documents directly in Docent — you
                add them to Mendeley first, then pull.
              </Prose>
              <SubHeading>How it fits together</SubHeading>
              <CodeBlock>{`Mendeley desktop  →  "Docent-Queue" collection
       ↓
docent reading sync-from-mendeley   (pulls metadata + order)
       ↓
Reading queue  →  next / start / done / export …
       ↓
docent serve  →  Claude MCP  (or this UI)`}</CodeBlock>
            </Card>

            {/* Studio */}
            <Card>
              <SectionHeading id="studio">Studio</SectionHeading>
              <Prose>
                The Studio is Docent&apos;s research engine. Choose an action, fill in a topic or artifact,
                select a backend, and run. Results stream live — you can see each phase as it progresses.
                Use the UI at <Code>localhost:7432</Code> or call commands directly from the terminal.
              </Prose>

              <SubHeading>Research actions</SubHeading>
              <CommandTable rows={[
                { cmd: 'docent studio deep-research --topic "…"', desc: 'Multi-source synthesis: search → fetch → write → verify → review. Best for broad topic briefs.' },
                { cmd: 'docent studio lit --topic "…"', desc: 'Literature review: search academic databases and compile a structured review.' },
                { cmd: 'docent studio review --artifact <arXiv/PDF/URL>', desc: 'Peer-review critique of a single paper.' },
                { cmd: 'docent studio compare --artifact-a <A> --artifact-b <B>', desc: 'Side-by-side analysis of two papers — shared findings, divergent claims, contradictions.' },
                { cmd: 'docent studio draft --topic "…"', desc: 'Draft a section or writeup from gathered sources.' },
                { cmd: 'docent studio replicate --artifact <arXiv/PDF>', desc: 'Replication protocol: what experiments, what data, what tools.' },
                { cmd: 'docent studio audit --artifact <arXiv/PDF>', desc: 'Methods and evidence audit: data availability, statistical validity, reproducibility.' },
              ]} />

              <SubHeading>Utility actions</SubHeading>
              <CommandTable rows={[
                { cmd: 'docent studio search-papers --query "…"', desc: 'Search arXiv for papers matching a query.' },
                { cmd: 'docent studio scholarly-search --query "…"', desc: 'Search Semantic Scholar.' },
                { cmd: 'docent studio get-paper --arxiv-id 2401.12345', desc: 'Fetch full metadata and abstract for an arXiv paper.' },
                { cmd: 'docent studio to-notebook', desc: 'Push research output and sources into a NotebookLM notebook.' },
              ]} />

              <SubHeading>Backends</SubHeading>
              <CommandTable rows={[
                { cmd: '--backend free', desc: 'Default. Tavily web search + Semantic Scholar academic search. No AI synthesis, no API key required.' },
                { cmd: '--backend feynman', desc: 'Autonomous deep-research via Feynman CLI agent. Requires feynman installed and an LLM API key.' },
                { cmd: '--backend docent', desc: 'Native 6-stage pipeline (planner → search → fetch → write → verify → review). Requires OpenCode server.' },
                { cmd: '--backend groq / gemini / openrouter / …', desc: 'LLM-powered synthesis using your configured API key for that provider.' },
              ]} />

              <SubHeading>Output destinations</SubHeading>
              <CommandTable rows={[
                { cmd: '--output local', desc: 'Default. Save to ~/.docent/research/ (or configured output_dir).' },
                { cmd: '--output notebook', desc: 'Upload output and sources to your NotebookLM notebook.' },
              ]} />

              <SubHeading>Guide files</SubHeading>
              <Prose>
                Attach PDFs or text files to steer the research. Pass one or more with{' '}
                <Code>--guide-files path/to/file.pdf</Code>. In the Studio UI, use the{' '}
                Browse button to pick files from your machine, or drag and drop onto the form.
              </Prose>

              <SubHeading>Config keys</SubHeading>
              <CommandTable rows={[
                { cmd: 'docent studio config-set --key output_dir --value "~/research"', desc: 'Set the directory where research output files are saved.' },
                { cmd: 'docent studio config-set --key tavily_api_key --value tvly-…', desc: 'Set Tavily API key for web search.' },
                { cmd: 'docent studio config-set --key groq_api_key --value gsk_…', desc: 'Set Groq API key for fast AI synthesis.' },
                { cmd: 'docent studio config-show', desc: 'Show all current studio config values (API keys masked).' },
              ]} />
            </Card>

            {/* Reading Queue */}
            <Card>
              <SectionHeading id="reading-queue">Reading Queue</SectionHeading>
              <Prose>
                Manage your reading list. Each entry is a document from Mendeley — a paper, book, or
                book chapter. All state lives in{' '}
                <Code>~/.docent/data/reading/queue.json</Code>. Metadata is always authoritative from
                Mendeley — Docent caches it locally for fast reads.
              </Prose>

              <SubHeading>Adding &amp; syncing documents</SubHeading>
              <CommandTable rows={[
                { cmd: 'docent reading sync-from-mendeley', desc: 'Pull documents from your configured Mendeley collection into the queue. Adds new entries, removes deleted ones.' },
                { cmd: 'docent reading sync-from-mendeley --dry-run', desc: 'Preview what would be added or removed without making changes.' },
                { cmd: 'docent reading add', desc: 'Shows guidance on how to add documents (via Mendeley — Docent does not accept direct adds).' },
              ]} />

              <SubHeading>Moving through the queue</SubHeading>
              <CommandTable rows={[
                { cmd: 'docent reading next', desc: 'Show the next entry to read (lowest order, status = queued).' },
                { cmd: 'docent reading next --category <name>', desc: 'Filter next entry by category prefix.' },
                { cmd: 'docent reading start <id>', desc: 'Mark an entry as currently reading. Stamps started_at timestamp.' },
                { cmd: 'docent reading done <id>', desc: 'Mark an entry as done. Stamps finished_at timestamp.' },
                { cmd: 'docent reading show <id>', desc: 'Show full details for an entry.' },
              ]} />

              <SubHeading>Editing &amp; organising</SubHeading>
              <CommandTable rows={[
                { cmd: 'docent reading edit <id> --notes "…"', desc: 'Update notes for an entry.' },
                { cmd: 'docent reading edit --id <id> --category "CVEN 601"', desc: 'Override the category path for an entry.' },
                { cmd: 'docent reading edit <id> --type book_chapter', desc: 'Set type: paper, book, or book_chapter.' },
                { cmd: 'docent reading set-deadline --id <id> --deadline 2026-06-01', desc: 'Set a reading deadline. Docent warns at startup when a deadline is approaching.' },
                { cmd: 'docent reading set-deadline --id <id> --deadline ""', desc: 'Clear a deadline.' },
                { cmd: 'docent reading move-up <id>', desc: 'Move an entry one position up in the queue.' },
                { cmd: 'docent reading move-down <id>', desc: 'Move an entry one position down.' },
                { cmd: 'docent reading move-to <id> --position <n>', desc: 'Move an entry to an absolute queue position.' },
              ]} />

              <SubHeading>Search &amp; stats</SubHeading>
              <CommandTable rows={[
                { cmd: 'docent reading search <query>', desc: 'Full-text search across titles, authors, notes, categories, IDs, and tags.' },
                { cmd: 'docent reading stats', desc: 'Show queue size, status breakdown, category breakdown, and upcoming deadlines.' },
              ]} />

              <SubHeading>Export &amp; maintenance</SubHeading>
              <CommandTable rows={[
                { cmd: 'docent reading export', desc: 'Export the full queue to a styled HTML document with a print dialog for PDF output.' },
                { cmd: 'docent reading remove <id>', desc: 'Remove an entry from the local queue (does not delete from Mendeley).' },
                { cmd: 'docent reading queue-clear --yes', desc: 'Wipe the entire local queue. Irreversible without a re-sync.' },
                { cmd: 'docent reading sync-status', desc: 'Check queue size vs PDF count in your database directory.' },
              ]} />
            </Card>

            {/* CLI Reference */}
            <Card>
              <SectionHeading id="cli">CLI Reference</SectionHeading>
              <Prose>All commands follow the pattern <Code>docent &lt;tool&gt; &lt;action&gt; [options]</Code>.</Prose>

              <SubHeading>Top-level commands</SubHeading>
              <CommandTable rows={[
                { cmd: 'docent --version', desc: 'Print the installed Docent version.' },
                { cmd: 'docent list', desc: 'List all registered tools and their available actions.' },
                { cmd: 'docent info <tool>', desc: 'Show detailed info and action list for a tool.' },
                { cmd: 'docent serve', desc: 'Start the MCP stdio server. Wire this into Claude\'s .mcp.json.' },
                { cmd: 'docent update', desc: 'Upgrade Docent to the latest version on PyPI. Reminds you to restart Claude if using MCP.' },
              ]} />

              <SubHeading>Config commands (per-tool)</SubHeading>
              <CommandTable rows={[
                { cmd: 'docent reading config-show', desc: 'Display all reading config values (database_dir, queue_collection, etc.).' },
                { cmd: 'docent reading config-set --key <k> --value <v>', desc: 'Set a single config value.' },
              ]} />

              <SubHeading>Config keys — Reading tool</SubHeading>
              <CommandTable rows={[
                { cmd: 'database_dir', desc: 'Absolute path to the folder where your PDFs are stored.' },
                { cmd: 'queue_collection', desc: 'Name of the Mendeley collection to sync from. Default: Docent-Queue.' },
              ]} />
            </Card>

            {/* MCP Setup */}
            <Card>
              <SectionHeading id="mcp">MCP Setup</SectionHeading>
              <Prose>
                Docent exposes all registered tool actions as MCP tools, so you can call them
                directly from Claude (or any MCP-compatible client) without leaving your conversation.
              </Prose>

              <SubHeading>1. Start the server</SubHeading>
              <Prose>
                Run <Code>docent serve</Code>. It starts a stdio MCP server — keep it running while
                you use Claude, or wire it into your MCP config so Claude starts it automatically.
              </Prose>

              <SubHeading>2. Configure Claude</SubHeading>
              <Prose>
                Add a <Code>.mcp.json</Code> at your project root (or in <Code>~/.claude/</Code> for
                global access):
              </Prose>
              <CodeBlock>{`{
  "mcpServers": {
    "docent": {
      "command": "docent",
      "args": ["serve"]
    }
  }
}`}</CodeBlock>
              <Prose>
                Claude will then have access to all Docent tools. Action names follow the pattern{' '}
                <Code>reading__next</Code>, <Code>reading__done</Code>, etc. (tool name + double
                underscore + action name).
              </Prose>

              <SubHeading>Tool naming convention</SubHeading>
              <CodeBlock>{`reading__add
reading__next
reading__start
reading__done
reading__show
reading__search
reading__stats
reading__edit
reading__set_deadline
reading__move_up
reading__move_down
reading__move_to
reading__export
reading__remove
reading__queue_clear
reading__sync_from_mendeley
reading__sync_status
reading__config_show
reading__config_set`}</CodeBlock>
            </Card>

            {/* Settings */}
            <Card>
              <SectionHeading id="settings">Settings</SectionHeading>
              <Prose>
                All settings are stored in <Code>~/.docent/config.toml</Code>. You can edit this
                file directly or use <Code>docent reading config-set</Code> from the terminal, or
                the Settings page in this UI.
              </Prose>

              <SubHeading>Config file location</SubHeading>
              <CodeBlock>{`~/.docent/config.toml`}</CodeBlock>

              <SubHeading>Example config</SubHeading>
              <CodeBlock>{`[reading]
database_dir = "/Users/you/Documents/Papers"
queue_collection = "Docent-Queue"
`}</CodeBlock>

              <SubHeading>Environment variable overrides</SubHeading>
              <Prose>
                All config values can be overridden with environment variables prefixed{' '}
                <Code>DOCENT_</Code>. See <Code>.env.example</Code> in the repo for the full list.
              </Prose>
            </Card>

          </div>
        </div>
      </main>
    </div>
  );
}
