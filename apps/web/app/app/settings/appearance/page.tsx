import { ThemeSwitcher } from "@/components/theme-switcher";

export default function AppearanceSettingsPage() {
  return (
    <section className="settings-card p-6 sm:p-8">
      <h2 className="text-lg font-semibold">Appearance</h2>
      <p className="mt-1 text-sm text-muted">
        Chọn giao diện Light / Dark / System, rồi bấm Lưu để áp dụng và lưu vào tài khoản.
      </p>
      <div className="mt-5">
        <ThemeSwitcher expanded />
      </div>
    </section>
  );
}
