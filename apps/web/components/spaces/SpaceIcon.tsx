import {
  BarChart3,
  BookOpen,
  Briefcase,
  Code2,
  FileText,
  Folder,
  Globe,
  Megaphone,
  Shield,
  Users,
} from "lucide-react";

const ICONS = {
  folder: Folder,
  book: BookOpen,
  users: Users,
  chart: BarChart3,
  code: Code2,
  megaphone: Megaphone,
  shield: Shield,
  globe: Globe,
  briefcase: Briefcase,
  "file-text": FileText,
} as const;

function accentTone(accent: string) {
  return accent === "cyan" || accent === "slate" ? "blue" : accent;
}

export function SpaceIcon({
  iconKey,
  accent,
  size = 16,
  className,
}: {
  iconKey: string;
  accent: string;
  size?: number;
  className?: string;
}) {
  const Icon = ICONS[iconKey as keyof typeof ICONS] || Folder;
  return (
    <span className={`stat-icon shrink-0 stat-${accentTone(accent)} ${className || ""}`}>
      <Icon size={size} />
    </span>
  );
}

export { ICONS as SPACE_ICONS };
