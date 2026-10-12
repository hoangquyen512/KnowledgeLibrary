"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { clientApi, type ThemePreference, type UserSettings } from "@/lib/api";
import { toast } from "sonner";

const choices = [
  { value: "LIGHT", label: "Light", icon: Sun },
  { value: "DARK", label: "Dark", icon: Moon },
  { value: "SYSTEM", label: "System", icon: Monitor },
] as const;

function toPreference(value: string | undefined): ThemePreference {
  const upper = (value || "system").toUpperCase();
  if (upper === "LIGHT" || upper === "DARK" || upper === "SYSTEM") return upper;
  return "SYSTEM";
}

export function ThemeSwitcher({ expanded = false }: { expanded?: boolean }) {
  const { setTheme, theme } = useTheme();
  const queryClient = useQueryClient();
  const [mounted, setMounted] = useState(false);
  const [draft, setDraft] = useState<ThemePreference>("SYSTEM");
  const [saving, setSaving] = useState(false);
  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => clientApi<UserSettings>("/me/settings"),
    staleTime: Infinity,
  });

  useEffect(() => setMounted(true), []);

  // Sync draft only when saved preference loads/changes — do not overwrite local picks.
  useEffect(() => {
    if (settings?.theme) setDraft(toPreference(settings.theme));
  }, [settings?.theme]);

  useEffect(() => {
    if (!mounted || settings?.theme || !theme) return;
    setDraft(toPreference(theme));
  }, [mounted, settings?.theme, theme]);

  const saved = toPreference(settings?.theme ?? theme);
  const dirty = draft !== saved;

  async function save() {
    if (!dirty || saving) return;
    setSaving(true);
    try {
      setTheme(draft.toLowerCase());
      const updated = await clientApi<UserSettings>("/me/settings", {
        method: "PATCH",
        body: JSON.stringify({ theme: draft }),
      });
      queryClient.setQueryData(["settings"], updated);
      toast.success("Đã lưu giao diện");
    } catch {
      toast.error("Không thể lưu giao diện.");
    } finally {
      setSaving(false);
    }
  }

  if (!mounted) return <div className="h-9 w-24" />;

  if (expanded) {
    return (
      <div className="space-y-4">
        <div className="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label="Theme">
          {choices.map(({ value, label, icon: Icon }) => {
            const active = draft === value;
            return (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => setDraft(value)}
                className={`choice-card ${active ? "choice-card-active" : ""}`}
              >
                <Icon size={18} /> {label}
              </button>
            );
          })}
        </div>
        <div className="flex items-center justify-end gap-3">
          {dirty ? (
            <p className="mr-auto text-xs text-muted">Bạn chưa lưu thay đổi.</p>
          ) : null}
          <button
            type="button"
            onClick={() => void save()}
            disabled={!dirty || saving}
            className="min-w-[7rem] rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:pointer-events-none disabled:opacity-50"
          >
            {saving ? "Đang lưu…" : "Lưu"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex rounded-lg border border-border bg-surface-muted p-1">
      {choices.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          type="button"
          title={label}
          aria-label={label}
          onClick={() => setDraft(value)}
          className={`rounded-md p-1.5 ${
            draft === value
              ? "bg-surface text-primary shadow-sm"
              : "text-muted hover:text-foreground"
          }`}
        >
          <Icon size={16} />
        </button>
      ))}
    </div>
  );
}
