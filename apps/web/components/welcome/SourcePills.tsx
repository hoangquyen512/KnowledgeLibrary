const TOOLS = [
  { id: "confluence", label: "Confluence", icon: ConfluenceIcon },
  { id: "jira", label: "Jira", icon: JiraIcon },
  { id: "files", label: "Files", icon: FilesIcon },
] as const;

export function SourcePills() {
  return (
    <div className="welcome-tools" id="help">
      <p className="welcome-tools-label">Works with your tools</p>
      <ul className="welcome-tools-list">
        {TOOLS.map((tool) => (
          <li key={tool.id} className="welcome-tool-chip">
            <tool.icon />
            <span>{tool.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ConfluenceIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#2684FF"
        d="M3.2 16.8c-.4.7-.1 1.5.6 1.9l3.2 1.8c.7.4 1.5.1 1.9-.6l5.4-9.4c.2-.3 0-.7-.4-.8l-3.7-1.1c-.3-.1-.7.1-.8.4L3.2 16.8z"
      />
      <path
        fill="#2684FF"
        d="M20.8 7.2c.4-.7.1-1.5-.6-1.9l-3.2-1.8c-.7-.4-1.5-.1-1.9.6l-5.4 9.4c-.2.3 0 .7.4.8l3.7 1.1c.3.1.7-.1.8-.4l6.2-7.8z"
        opacity="0.55"
      />
    </svg>
  );
}

function JiraIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#2684FF"
        d="M12.2 2H4.6c-.4 0-.6.5-.3.8l7.5 7.9c.4.4 1 .4 1.4 0l7.5-7.9c.3-.3.1-.8-.3-.8h-7.6a1 1 0 0 0-.6.2z"
      />
      <path
        fill="#2684FF"
        d="M12.2 9.2H4.6c-.4 0-.6.5-.3.8l7.5 7.9c.4.4 1 .4 1.4 0l7.5-7.9c.3-.3.1-.8-.3-.8h-7.6a1 1 0 0 0-.6.2z"
        opacity="0.7"
      />
      <path
        fill="#2684FF"
        d="M12.2 16.4H4.6c-.4 0-.6.5-.3.8l3.4 3.6c.4.4 1 .4 1.4 0l3.4-3.6c.3-.3.1-.8-.3-.8z"
        opacity="0.45"
      />
    </svg>
  );
}

function FilesIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M8 4h6l4 4v10a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"
        stroke="#9BB4FF"
        strokeWidth="1.6"
      />
      <path d="M14 4v4h4" stroke="#9BB4FF" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M9 12h6M9 15h4" stroke="#9BB4FF" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}
