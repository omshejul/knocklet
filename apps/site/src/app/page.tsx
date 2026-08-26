import { DownloadLink } from "@/components/download-link";

const steps = [
  ["01", "Add your list", "Upload CSV, Excel, or ODS"],
  ["02", "Choose people", "Select who you want to contact"],
  ["03", "Send requests", "Review your selection and send"],
  ["04", "See results", "View sent, pending, accepted, or failed"],
];

export default function Home() {
  return (
    <main>
      <header className="site-header">
        <a className="wordmark" href="#top" aria-label="Knocklet home">
          <svg viewBox="0 0 256 256" aria-hidden="true">
            <path d="M186.66 59.56C168.47 32.29 146.54 16 128 16S87.53 32.29 69.34 59.56C50.7 87.54 40 121.23 40 152a88 88 0 0 0 176 0c0-30.77-10.7-64.46-29.34-92.44ZM128 224a72.08 72.08 0 0 1-72-72c0-27.69 9.72-58.15 26.66-83.56C97.19 46.64 115.41 32 128 32c9.5 0 22.2 8.33 34.1 21.78L122 98.67a8 8 0 0 0 4 13.09l24.6 6.15-6.5 32.52a8 8 0 0 0 6.27 9.41A7.77 7.77 0 0 0 152 160a8 8 0 0 0 7.83-6.43l8-40a8 8 0 0 0-5.9-9.33l-19.16-4.79 29.33-32.85c.42.61.83 1.22 1.24 1.84C190.28 93.85 200 124.31 200 152a72.08 72.08 0 0 1-72 72Z" />
          </svg>
          Knocklet
        </a>
        <nav aria-label="Primary navigation">
          <a className="source-link" href="https://github.com/omshejul/knocklet">
            GitHub
          </a>
          <DownloadLink compact />
        </nav>
      </header>

      <section className="hero" id="top">
        <div className="hero-copy">
          <h1>Send LinkedIn connection requests from a list.</h1>
          <p>
            Import your contacts, choose who you want to reach, and send. See
            what happened with every request.
          </p>
          <div className="hero-action">
            <DownloadLink />
            <span>For M1 or newer Macs · macOS 13+</span>
          </div>
        </div>

        <div className="workflow" aria-label="How Knocklet works">
          <div className="workflow-title">
            <span>Send requests</span>
          </div>
          <ol>
            {steps.map(([number, title, detail]) => (
              <li key={number}>
                <span className="step-number">{number}</span>
                <span className="step-copy">
                  <strong>{title}</strong>
                  <span>{detail}</span>
                </span>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <footer>
        <span>Open source. MIT licensed.</span>
        <a href="https://github.com/omshejul/knocklet/releases">All downloads</a>
      </footer>
    </main>
  );
}
