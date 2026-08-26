const downloadUrl =
  "https://github.com/omshejul/knocklet/releases/download/v0.2.1/Knocklet-0.2.1-arm64.dmg";

export function DownloadLink({ compact = false }: { compact?: boolean }) {
  return (
    <a
      className={compact ? "download-link download-link-compact" : "download-link"}
      href={downloadUrl}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3v12m0 0 4-4m-4 4-4-4M5 20h14" />
      </svg>
      Download for Mac
    </a>
  );
}
